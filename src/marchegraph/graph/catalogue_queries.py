"""Exécution du catalogue : fragments Cypher fixes, paramètres liés, agrégation exacte.

Aucune valeur saisie n'entre dans le texte de la requête : les filtres
choisissent des fragments écrits ici, et les valeurs passent en paramètres.
Les agrégats suivent les règles de l'epic 3 (uid distincts, valeurs multiples
exclues et comptées, montants en Decimal).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from neo4j import Session

from marchegraph.graph import queries as reference_queries
from marchegraph.graph.contracts import (
    CatalogueRow,
    EvidenceReference,
    QueryResponse,
    QueryRow,
)
from marchegraph.queries.catalogue import CatalogueQuery, validate

# Hors des dix questions de référence.
CATALOGUE_QUESTION_ID = 0
MAX_EVIDENCE_MARKETS = 25

FILTER_FRAGMENTS = {
    "year": "market.annee = $year",
    "region_code": (
        "size(coalesce(market.acheteur_region_code_values, [])) = 1 "
        "AND market.acheteur_region_code_values[0] = $region_code"
    ),
    "buyer_id": "market.acheteur_id = $buyer_id",
    "holder": (
        "EXISTS { MATCH (market)-[:A_TITULAIRE]->(:Titulaire {source_id: $source_id, "
        "identifier_type: $holder_type, identifier_value: $holder_value}) }"
    ),
    "procedure": "$procedure IN coalesce(market.procedure_values, [])",
    "nature": "$nature IN coalesce(market.nature_values, [])",
    "theme": (
        "any(text_value IN coalesce(market.objet_values, []) "
        "WHERE toLower(text_value) CONTAINS toLower($theme))"
    ),
}

BUYER_NAMES = (
    "head([(market)-[:A_ACHETEUR]->(buyer:Acheteur) | "
    "coalesce(buyer.nom_values, [])]) AS buyer_names"
)
HOLDERS = (
    "[(market)-[:A_TITULAIRE]->(holder:Titulaire) | {type: holder.identifier_type, "
    "value: holder.identifier_value, names: coalesce(holder.nom_values, [])}] AS holders"
)
MODIFICATIONS = (
    "COUNT { (version:Modification)-[:MODIFICATION_DE]->(market) } "
    "AS modification_count"
)


def build_cypher(query: CatalogueQuery, source_id: str) -> tuple[str, dict]:
    """Requête et paramètres ; seuls des fragments de ce module composent le texte."""
    validate(query)
    conditions: list[str] = []
    parameters: dict = {"source_id": source_id}
    if query.grouping != "annee":
        conditions.append(FILTER_FRAGMENTS["year"])
        parameters["year"] = query.year
    for name in ("region_code", "buyer_id", "procedure", "nature", "theme"):
        value = getattr(query, name)
        if value is not None:
            conditions.append(FILTER_FRAGMENTS[name])
            parameters[name] = value.strip()
    if query.holder_type is not None:
        conditions.append(FILTER_FRAGMENTS["holder"])
        parameters["holder_type"] = query.holder_type.strip()
        parameters["holder_value"] = query.holder_value.strip()

    returned = [
        "market.uid AS uid",
        "market.annee AS annee",
        "market.acheteur_id AS buyer_id",
        "coalesce(market.acheteur_region_code_values, []) AS regions",
        "coalesce(market.codeCPV_values, []) AS cpv_values",
        "coalesce(market.procedure_values, []) AS procedures",
        "coalesce(market.nature_values, []) AS natures",
        "coalesce(market.montant_values, []) AS amounts",
        "coalesce(market.dureeMois_values, []) AS durations",
        BUYER_NAMES if query.grouping == "acheteur" else "[] AS buyer_names",
        HOLDERS if query.grouping == "titulaire" else "[] AS holders",
        MODIFICATIONS if query.measure == "nombre_modifications"
        else "0 AS modification_count",
    ]
    where = " AND ".join(conditions) if conditions else "true"
    cypher = (
        "MATCH (market:Marche {source_id: $source_id})\n"
        f"WHERE {where}\n"
        f"RETURN {', '.join(returned)}"
    )
    return cypher, parameters


@dataclass
class _Group:
    labels: set[str] = field(default_factory=set)
    market_count: int = 0
    measured_market_count: int = 0
    total: Decimal = Decimal("0")
    evidence: list[EvidenceReference] = field(default_factory=list)


@dataclass
class _Counters:
    unclassified: int = 0
    multi_group: int = 0
    measure_missing: int = 0
    measure_multivalued: int = 0
    amount_filtered_out: int = 0


GROUP_PREDICATES = {
    "aucun": "uid",
    "acheteur": "A_ACHETEUR",
    "titulaire": "A_TITULAIRE",
    "famille_cpv": "codeCPV_values",
    "region": "acheteur_region_code_values",
    "procedure": "procedure_values",
    "nature": "nature_values",
    "annee": "annee",
}


def _groups(query: CatalogueQuery, record: Mapping) -> list[tuple[str, tuple[str, ...]]]:
    grouping = query.grouping
    if grouping == "aucun":
        return [("ensemble", ())]
    if grouping == "acheteur":
        return [(str(record["buyer_id"]), tuple(record["buyer_names"] or ()))]
    if grouping == "titulaire":
        return [
            (f"{holder['type']}:{holder['value']}", tuple(holder["names"] or ()))
            for holder in record["holders"] or ()
        ]
    if grouping == "famille_cpv":
        families = {
            family
            for family in map(reference_queries._cpv_family, record["cpv_values"] or ())
            if family is not None
        }
        return [(family, ()) for family in sorted(families)]
    if grouping == "region":
        regions = tuple(record["regions"] or ())
        return [(regions[0], ())] if len(regions) == 1 else []
    if grouping == "procedure":
        return [(value, ()) for value in sorted(set(record["procedures"] or ()))]
    if grouping == "nature":
        return [(value, ()) for value in sorted(set(record["natures"] or ()))]
    return [(str(record["annee"]), ())]


def _single_decimal(values, uid: str, field_name: str) -> tuple[Decimal | None, str]:
    values = tuple(values or ())
    if not values:
        return None, "missing"
    if len(set(map(str, values))) > 1:
        return None, "multi"
    return reference_queries._decimal_value(values[0], uid=uid, field_name=field_name), "ok"


def aggregate(
    query: CatalogueQuery, records: Iterable[Mapping]
) -> QueryResponse[CatalogueRow]:
    """Agrège les marchés renvoyés par `build_cypher` (testable sans Neo4j)."""
    validate(query)
    groups: dict[str, _Group] = {}
    counters = _Counters()
    has_amount_range = query.amount_min is not None or query.amount_max is not None

    for record in records:
        uid = str(record["uid"])
        if query.cpv_family is not None:
            families = {reference_queries._cpv_family(v) for v in record["cpv_values"] or ()}
            if query.cpv_family not in families:
                continue
        amount, amount_state = _single_decimal(record["amounts"], uid, "montant")
        if has_amount_range:
            if amount is None or (
                query.amount_min is not None and amount < query.amount_min
            ) or (query.amount_max is not None and amount > query.amount_max):
                counters.amount_filtered_out += 1
                continue

        if query.measure == "nombre_marches":
            measured, state = Decimal(1), "ok"
        elif query.measure in ("montant_total", "montant_moyen"):
            measured, state = amount, amount_state
        elif query.measure == "duree_moyenne":
            measured, state = _single_decimal(record["durations"], uid, "dureeMois")
        else:
            measured, state = Decimal(record["modification_count"] or 0), "ok"
        if state == "missing":
            counters.measure_missing += 1
        elif state == "multi":
            counters.measure_multivalued += 1

        market_groups = _groups(query, record)
        if not market_groups:
            counters.unclassified += 1
            continue
        if len(market_groups) > 1:
            counters.multi_group += 1
        for key, labels in market_groups:
            group = groups.setdefault(key, _Group())
            group.labels.update(labels)
            group.market_count += 1
            if measured is None:
                continue
            group.measured_market_count += 1
            group.total += measured
            if len(group.evidence) < 2 * MAX_EVIDENCE_MARKETS:
                group.evidence.append(EvidenceReference(
                    "Marche", uid, GROUP_PREDICATES[query.grouping],
                    uid if query.grouping == "aucun" else key))
                if query.measure in ("montant_total", "montant_moyen"):
                    group.evidence.append(EvidenceReference(
                        "Marche", uid, "montant_values", str(measured)))
                elif query.measure == "duree_moyenne":
                    group.evidence.append(EvidenceReference(
                        "Marche", uid, "dureeMois_values", str(measured)))

    def value_of(group: _Group) -> Decimal | None:
        if query.measure == "nombre_marches":
            return Decimal(group.market_count)
        if query.measure in ("montant_moyen", "duree_moyenne"):
            if not group.measured_market_count:
                return None
            return group.total / group.measured_market_count
        return group.total

    ranked = sorted(
        groups.items(),
        key=lambda item: (value_of(item[1]) is None, -(value_of(item[1]) or 0), item[0]),
    )
    rows = tuple(
        QueryRow(
            result=CatalogueRow(
                group=key,
                labels=tuple(sorted(group.labels)),
                value=value_of(group),
                market_count=group.market_count,
                measured_market_count=group.measured_market_count,
            ),
            evidence=tuple(group.evidence),
            evidence_complete=group.measured_market_count <= MAX_EVIDENCE_MARKETS,
        )
        for key, group in ranked[: query.limit]
    )
    return QueryResponse(
        question_id=CATALOGUE_QUESTION_ID,
        rows=rows,
        limitations=_limitations(query, counters, len(groups), rows),
        metadata=(
            ("groupes", len(groups)),
            ("marches_non_rattaches", counters.unclassified),
            ("marches_valeur_absente", counters.measure_missing),
            ("marches_valeurs_multiples", counters.measure_multivalued),
        ),
    )


def _limitations(query, counters: _Counters, group_count: int, rows) -> tuple[str, ...]:
    notes = ["Comptes en marchés distincts (uid), attributions initiales seulement."]
    if query.measure in ("montant_total", "montant_moyen"):
        notes.append(
            "Les montants sont des montants déclarés, pas des paiements ; un "
            "accord-cadre peut afficher un plafond."
        )
    if query.measure in ("montant_total", "montant_moyen", "duree_moyenne"):
        notes.append(
            f"{counters.measure_multivalued} marché(s) à valeurs multiples et "
            f"{counters.measure_missing} sans valeur sont exclus de la mesure."
        )
    if query.measure == "nombre_modifications":
        notes.append(
            "Seules les versions reliées à un marché initial sont comptées ; les "
            "versions sans marché initial ne sont pas rattachables."
        )
    if counters.unclassified:
        notes.append(
            f"{counters.unclassified} marché(s) ne peuvent être rattachés à un "
            "groupe (valeur absente, ou plusieurs régions)."
        )
    if counters.multi_group:
        notes.append(
            f"{counters.multi_group} marché(s) appartiennent à plusieurs groupes et "
            "sont comptés dans chacun : les totaux ne sont pas additifs."
        )
    if query.region_code is not None or query.grouping == "region":
        notes.append(
            "Un marché n'est rattaché à une région que si son acheteur a une seule "
            "région renseignée."
        )
    if query.theme is not None:
        notes.append(
            "Le thème est recherché comme sous-chaîne insensible à la casse dans "
            "l'objet du marché."
        )
    if counters.amount_filtered_out:
        notes.append(
            f"{counters.amount_filtered_out} marché(s) hors tranche de montant ou "
            "sans montant unique sont écartés."
        )
    if group_count > len(rows):
        notes.append(f"Seuls les {len(rows)} premiers groupes sur {group_count} "
                     "sont affichés.")
    if any(not row.evidence_complete for row in rows):
        notes.append(
            f"Les preuves sont limitées aux {MAX_EVIDENCE_MARKETS} premiers marchés "
            "par groupe ; les mesures utilisent tous les marchés."
        )
    return tuple(notes)


def run_catalogue(session: Session, query: CatalogueQuery) -> QueryResponse[CatalogueRow]:
    cypher, parameters = build_cypher(query, reference_queries.DATASET_ID)
    return aggregate(query, session.run(cypher, **parameters))
