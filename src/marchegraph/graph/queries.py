from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar

from neo4j import Session

from marchegraph.graph.load_initial_awards import DATASET_ID

T = TypeVar("T")


@dataclass(frozen=True)
class EvidenceReference:
    node_type: str
    node_id: str
    predicate: str
    object_id: str


@dataclass(frozen=True)
class QueryRow(Generic[T]):
    result: T
    evidence: tuple[EvidenceReference, ...]
    evidence_complete: bool = True


@dataclass(frozen=True)
class QueryResponse(Generic[T]):
    question_id: int | tuple[int, ...]
    rows: tuple[QueryRow[T], ...]
    limitations: tuple[str, ...] = ()
    metadata: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class BuyerRanking:
    buyer_id: str
    names: tuple[str, ...]
    market_count: int


@dataclass(frozen=True)
class HolderRanking:
    identifier_type: str
    identifier_value: str
    names: tuple[str, ...]
    market_count: int


@dataclass(frozen=True)
class CategoryMarketCount:
    field: str
    value: str
    market_count: int


@dataclass(frozen=True)
class MultiBuyerHolder:
    identifier_type: str
    identifier_value: str
    names: tuple[str, ...]
    buyer_ids: tuple[str, ...]
    market_count: int


@dataclass(frozen=True)
class CpvFamilyAggregate:
    family_code: str
    market_count: int
    amount_total: Decimal
    amount_market_count: int
    amount_missing_value_market_count: int
    amount_missing_source_market_count: int
    amount_multivalued_market_count: int
    mean_duration_months: Decimal | None
    duration_market_count: int
    duration_missing_value_market_count: int
    duration_missing_source_market_count: int
    duration_multivalued_market_count: int
    multiple_cpv_market_count: int


@dataclass(frozen=True)
class ModifiedMarketCount:
    uid: str
    modification_ids: tuple[int, ...]


@dataclass(frozen=True)
class UnlinkedModification:
    uid: str
    modification_id: int


@dataclass(frozen=True)
class ModificationHistorySummary:
    year: int
    modified_market_count: int
    total_version_count: int
    linked_version_count: int
    unlinked_version_count: int
    modified_markets: tuple[ModifiedMarketCount, ...]
    unlinked_samples: tuple[UnlinkedModification, ...]


@dataclass(frozen=True)
class ThemedMarket:
    uid: str
    region_code: str
    matching_objects: tuple[str, ...]


@dataclass(frozen=True)
class HolderNameVariants:
    identifier_type: str
    identifier_value: str
    names: tuple[str, ...]
    market_count: int


@dataclass(frozen=True)
class DataQualityIssue:
    node_type: str
    issue_code: str
    affected_record_count: int


class GraphQueryDataError(ValueError):
    pass


MAX_AGGREGATE_EVIDENCE_MARKETS = 25

AMOUNTS_AND_DURATIONS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
RETURN market.uid AS uid,
       coalesce(market.codeCPV_values, []) AS cpv_values,
       coalesce(market.montant_values, []) AS amount_values,
       coalesce(market.dureeMois_values, []) AS duration_values,
       coalesce(market.montant_missing_in_source, false) AS amount_missing,
       coalesce(market.dureeMois_missing_in_source, false) AS duration_missing
ORDER BY market.uid
"""

MODIFICATION_HISTORY_SUMMARY_QUERY = """
OPTIONAL MATCH (version:Modification {source_id: $source_id})
WHERE version.annee = $year
OPTIONAL MATCH (version)-[:MODIFICATION_DE]->
               (market:Marche {source_id: $source_id})
RETURN count(DISTINCT version) AS total_version_count,
       count(DISTINCT CASE WHEN market IS NOT NULL THEN version END)
         AS linked_version_count,
       count(DISTINCT CASE WHEN version IS NOT NULL AND market IS NULL
                           THEN version END) AS unlinked_version_count,
       count(DISTINCT market.uid) AS modified_market_count
"""

MODIFIED_MARKETS_QUERY = """
MATCH (version:Modification {source_id: $source_id})-[:MODIFICATION_DE]->
      (market:Marche {source_id: $source_id})
WHERE version.annee = $year
WITH market, collect(DISTINCT version.modification_id) AS modification_ids
RETURN market.uid AS uid, modification_ids
ORDER BY size(modification_ids) DESC, market.uid ASC
LIMIT $limit
"""

UNLINKED_MODIFICATIONS_QUERY = """
MATCH (version:Modification {source_id: $source_id})
WHERE version.annee = $year
OPTIONAL MATCH (version)-[:MODIFICATION_DE]->
               (market:Marche {source_id: $source_id})
WITH version, market
WHERE market IS NULL
RETURN version.uid AS uid, version.modification_id AS modification_id
ORDER BY uid ASC, modification_id ASC
LIMIT $limit
"""

THEME_REGION_SUMMARY_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
  AND any(text_value IN coalesce(market.objet_values, [])
          WHERE toLower(text_value) CONTAINS toLower($theme))
WITH market, coalesce(market.acheteur_region_code_values, []) AS regions
RETURN count(*) AS theme_market_count,
       coalesce(sum(CASE WHEN size(regions) = 0 THEN 1 ELSE 0 END), 0)
         AS missing_region_count,
       coalesce(sum(CASE WHEN size(regions) > 1 THEN 1 ELSE 0 END), 0)
         AS multivalued_region_count,
       coalesce(
           sum(CASE WHEN size(regions) = 1 AND regions[0] = $region
                    THEN 1 ELSE 0 END),
           0
       ) AS matching_region_market_count
"""

THEME_REGION_MARKETS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
  AND any(text_value IN coalesce(market.objet_values, [])
          WHERE toLower(text_value) CONTAINS toLower($theme))
WITH market,
     [text_value IN coalesce(market.objet_values, [])
      WHERE toLower(text_value) CONTAINS toLower($theme)] AS matching_objects,
     coalesce(market.acheteur_region_code_values, []) AS regions
WHERE size(regions) = 1 AND regions[0] = $region
RETURN market.uid AS uid, regions[0] AS region_code, matching_objects
ORDER BY market.uid ASC
LIMIT $limit
"""

HOLDER_NAME_VARIANTS_COUNT_QUERY = """
MATCH (holder:Titulaire {source_id: $source_id})
WITH coalesce(holder.nom_values, []) AS names
WHERE size(names) > 1
RETURN count(*) AS holder_count
"""

HOLDER_NAME_VARIANTS_QUERY = """
MATCH (holder:Titulaire {source_id: $source_id})
WITH holder, coalesce(holder.nom_values, []) AS names
WHERE size(names) > 1
OPTIONAL MATCH (market:Marche {source_id: $source_id})
               -[:A_TITULAIRE]->(holder)
RETURN holder.identifier_type AS identifier_type,
       holder.identifier_value AS identifier_value,
       names, collect(DISTINCT market.uid) AS market_uids
ORDER BY size(names) DESC, identifier_type ASC, identifier_value ASC
LIMIT $limit
"""

DATA_QUALITY_ISSUES_QUERY = """
CALL () {
    MATCH (market:Marche {source_id: $source_id})
    WITH market, [
        CASE WHEN coalesce(market.type_missing_in_source, false)
             THEN 'type:missing' END,
        CASE WHEN size(coalesce(market.type_values, [])) > 1
             THEN 'type:multiple' END,
        CASE WHEN coalesce(market.codeCPV_missing_in_source, false)
             THEN 'codeCPV:missing' END,
        CASE WHEN size(coalesce(market.codeCPV_values, [])) > 1
             THEN 'codeCPV:multiple' END,
        CASE WHEN coalesce(market.nature_missing_in_source, false)
             THEN 'nature:missing' END,
        CASE WHEN size(coalesce(market.nature_values, [])) > 1
             THEN 'nature:multiple' END,
        CASE WHEN coalesce(market.montant_missing_in_source, false)
             THEN 'montant:missing' END,
        CASE WHEN size(coalesce(market.montant_values, [])) > 1
             THEN 'montant:multiple' END,
        CASE WHEN coalesce(market.procedure_missing_in_source, false)
             THEN 'procedure:missing' END,
        CASE WHEN size(coalesce(market.procedure_values, [])) > 1
             THEN 'procedure:multiple' END,
        CASE WHEN coalesce(market.dureeMois_missing_in_source, false)
             THEN 'dureeMois:missing' END,
        CASE WHEN size(coalesce(market.dureeMois_values, [])) > 1
             THEN 'dureeMois:multiple' END,
        CASE WHEN coalesce(market.objet_missing_in_source, false)
             THEN 'objet:missing' END,
        CASE WHEN size(coalesce(market.objet_values, [])) > 1
             THEN 'objet:multiple' END,
        CASE WHEN coalesce(
                  market.acheteur_region_code_missing_in_source, false
             ) THEN 'acheteur_region_code:missing' END,
        CASE WHEN size(coalesce(market.acheteur_region_code_values, [])) > 1
             THEN 'acheteur_region_code:multiple' END
    ] AS issues
    UNWIND issues AS issue
    WITH market, issue
    WHERE issue IS NOT NULL
    RETURN 'Marche' AS node_type, market.uid AS node_id, issue
    UNION ALL
    MATCH (version:Modification {source_id: $source_id})
    WITH version, [
        CASE WHEN coalesce(version.nature_missing_in_source, false)
             THEN 'nature:missing' END,
        CASE WHEN size(coalesce(version.nature_values, [])) > 1
             THEN 'nature:multiple' END,
        CASE WHEN coalesce(version.montant_missing_in_source, false)
             THEN 'montant:missing' END,
        CASE WHEN size(coalesce(version.montant_values, [])) > 1
             THEN 'montant:multiple' END,
        CASE WHEN coalesce(version.procedure_missing_in_source, false)
             THEN 'procedure:missing' END,
        CASE WHEN size(coalesce(version.procedure_values, [])) > 1
             THEN 'procedure:multiple' END,
        CASE WHEN coalesce(version.dureeMois_missing_in_source, false)
             THEN 'dureeMois:missing' END,
        CASE WHEN size(coalesce(version.dureeMois_values, [])) > 1
             THEN 'dureeMois:multiple' END,
        CASE WHEN coalesce(version.objet_missing_in_source, false)
             THEN 'objet:missing' END,
        CASE WHEN size(coalesce(version.objet_values, [])) > 1
             THEN 'objet:multiple' END,
        CASE WHEN coalesce(version.codeCPV_missing_in_source, false)
             THEN 'codeCPV:missing' END,
        CASE WHEN size(coalesce(version.codeCPV_values, [])) > 1
             THEN 'codeCPV:multiple' END,
        CASE WHEN coalesce(version.acheteur_id_missing_in_source, false)
             THEN 'acheteur_id:missing' END,
        CASE WHEN size(coalesce(version.acheteur_id_values, [])) > 1
             THEN 'acheteur_id:multiple' END,
        CASE WHEN coalesce(version.acheteur_nom_missing_in_source, false)
             THEN 'acheteur_nom:missing' END,
        CASE WHEN size(coalesce(version.acheteur_nom_values, [])) > 1
             THEN 'acheteur_nom:multiple' END,
        CASE WHEN coalesce(version.titulaire_nom_missing_in_source, false)
             THEN 'titulaire_nom:missing' END,
        CASE WHEN size(coalesce(version.titulaire_nom_values, [])) > 1
             THEN 'titulaire_nom:multiple' END,
        CASE WHEN coalesce(version.titulaire_identity_missing_in_source, false)
             THEN 'titulaire_identity:missing' END,
        CASE WHEN size(coalesce(version.titulaire_identity_values, [])) > 1
             THEN 'titulaire_identity:multiple' END,
        CASE WHEN version.initial_market_status = 'missing_from_snapshot'
             THEN 'initial_market:missing' END
    ] AS issues
    UNWIND issues AS issue
    WITH version, issue
    WHERE issue IS NOT NULL
    RETURN 'Modification' AS node_type,
           version.uid + ':' + toString(version.modification_id) AS node_id,
           issue
}
WITH node_type, issue, collect(DISTINCT node_id) AS node_ids
RETURN node_type, issue, size(node_ids) AS affected_record_count,
       node_ids[0..25] AS sample_node_ids
ORDER BY node_type ASC, issue ASC
"""


BUYER_RANKING_QUERY = """
MATCH (market:Marche {source_id: $source_id})-[:A_ACHETEUR]->
      (buyer:Acheteur {source_id: $source_id})
WHERE market.annee = $year
WITH buyer, count(DISTINCT market.uid) AS market_count,
     collect(DISTINCT market.uid) AS market_uids
RETURN buyer.id AS buyer_id,
       coalesce(buyer.nom_values, []) AS names,
       market_count, market_uids
ORDER BY market_count DESC, buyer.id ASC
LIMIT $limit
"""

HOLDER_RANKING_QUERY = """
MATCH (market:Marche {source_id: $source_id})-[:A_ACHETEUR]->
      (buyer:Acheteur {source_id: $source_id, id: $buyer_id})
MATCH (market)-[:A_TITULAIRE]->(holder:Titulaire {source_id: $source_id})
WHERE market.annee = $year
WITH holder, count(DISTINCT market.uid) AS market_count,
     collect(DISTINCT market.uid) AS market_uids
RETURN holder.identifier_type AS identifier_type,
       holder.identifier_value AS identifier_value,
       coalesce(holder.nom_values, []) AS names,
       market_count, market_uids
ORDER BY market_count DESC, identifier_type ASC, identifier_value ASC
LIMIT $limit
"""

NATURE_COUNTS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
UNWIND coalesce(market.nature_values, []) AS value
WITH value, collect(DISTINCT market.uid) AS market_uids
RETURN value, size(market_uids) AS market_count, market_uids
ORDER BY market_count DESC, value ASC
"""

PROCEDURE_COUNTS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
UNWIND coalesce(market.procedure_values, []) AS value
WITH value, collect(DISTINCT market.uid) AS market_uids
RETURN value, size(market_uids) AS market_count, market_uids
ORDER BY market_count DESC, value ASC
"""

NATURE_COVERAGE_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
WITH coalesce(market.nature_values, []) AS values
RETURN count(*) AS market_count,
       sum(CASE WHEN size(values) = 0 THEN 1 ELSE 0 END) AS missing_count,
       sum(CASE WHEN size(values) > 1 THEN 1 ELSE 0 END) AS multivalued_count
"""

PROCEDURE_COVERAGE_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE market.annee = $year
WITH coalesce(market.procedure_values, []) AS values
RETURN count(*) AS market_count,
       sum(CASE WHEN size(values) = 0 THEN 1 ELSE 0 END) AS missing_count,
       sum(CASE WHEN size(values) > 1 THEN 1 ELSE 0 END) AS multivalued_count
"""

MULTI_BUYER_HOLDERS_QUERY = """
MATCH (market:Marche {source_id: $source_id})-[:A_TITULAIRE]->
      (holder:Titulaire {source_id: $source_id})
MATCH (market)-[:A_ACHETEUR]->(buyer:Acheteur {source_id: $source_id})
WHERE market.annee = $year
WITH holder, collect(DISTINCT buyer.id) AS buyer_ids,
     collect(DISTINCT market.uid) AS market_uids,
     collect(DISTINCT {market_uid: market.uid, buyer_id: buyer.id})
       AS market_buyers
WHERE size(buyer_ids) > 1
RETURN holder.identifier_type AS identifier_type,
       holder.identifier_value AS identifier_value,
       coalesce(holder.nom_values, []) AS names,
       buyer_ids, size(market_uids) AS market_count, market_buyers
ORDER BY size(buyer_ids) DESC, market_count DESC,
         identifier_type ASC, identifier_value ASC
LIMIT $limit
"""


def _validate_limit(limit: int) -> None:
    if limit < 1:
        raise ValueError("La limite de résultats doit être supérieure à zéro.")


def _names(values: list[str] | None) -> tuple[str, ...]:
    return tuple(sorted(set(values or ())))


def _market_evidence(
    market_uids: list[str] | tuple[str, ...],
    predicate: str,
    object_id: str,
) -> tuple[EvidenceReference, ...]:
    return tuple(
        EvidenceReference("Marche", str(uid), predicate, object_id)
        for uid in sorted(set(market_uids))
    )


def _decimal_value(raw_value: object, *, uid: str, field_name: str) -> Decimal:
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError) as error:
        raise GraphQueryDataError(
            f"La valeur {field_name} du marché {uid} n'est pas numérique."
        ) from error
    if not value.is_finite():
        raise GraphQueryDataError(
            f"La valeur {field_name} du marché {uid} n'est pas finie."
        )
    return value


def _cpv_family(value: object) -> str | None:
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits[:3] if len(digits) >= 3 else None


@dataclass
class _CpvFamilyAccumulator:
    market_count: int = 0
    amount_total: Decimal = Decimal("0")
    amount_market_count: int = 0
    amount_missing_value_market_count: int = 0
    amount_missing_source_market_count: int = 0
    amount_multivalued_market_count: int = 0
    duration_total: Decimal = Decimal("0")
    duration_market_count: int = 0
    duration_missing_value_market_count: int = 0
    duration_missing_source_market_count: int = 0
    duration_multivalued_market_count: int = 0
    multiple_cpv_market_count: int = 0
    amount_evidence: list[EvidenceReference] = field(default_factory=list)
    duration_evidence: list[EvidenceReference] = field(default_factory=list)


def aggregate_amounts_and_durations_by_cpv(
    session: Session,
    *,
    year: int = 2025,
) -> QueryResponse[CpvFamilyAggregate]:
    records = session.run(
        AMOUNTS_AND_DURATIONS_QUERY,
        source_id=DATASET_ID,
        year=year,
    )
    families: dict[str, _CpvFamilyAccumulator] = {}
    unclassified_market_count = 0
    unmapped_cpv_value_count = 0

    for record in records:
        uid = str(record["uid"])
        cpv_values = tuple(sorted(set(record["cpv_values"] or ())))
        family_values: dict[str, list[str]] = {}
        for value in cpv_values:
            family_code = _cpv_family(value)
            if family_code is not None:
                family_values.setdefault(family_code, []).append(str(value))
        unmapped_cpv_value_count += len(cpv_values) - sum(
            1 for value in cpv_values if _cpv_family(value) is not None
        )
        if not family_values:
            unclassified_market_count += 1
            continue

        amount_values = tuple(record["amount_values"] or ())
        duration_values = tuple(record["duration_values"] or ())
        for family_code in sorted(family_values):
            aggregate = families.setdefault(
                family_code, _CpvFamilyAccumulator()
            )
            aggregate.market_count += 1
            if len(cpv_values) > 1:
                aggregate.multiple_cpv_market_count += 1
            if record["amount_missing"]:
                aggregate.amount_missing_source_market_count += 1
            if record["duration_missing"]:
                aggregate.duration_missing_source_market_count += 1

            if not amount_values:
                aggregate.amount_missing_value_market_count += 1
            elif len(amount_values) > 1:
                aggregate.amount_multivalued_market_count += 1
            else:
                amount = _decimal_value(
                    amount_values[0], uid=uid, field_name="montant"
                )
                aggregate.amount_total += amount
                aggregate.amount_market_count += 1
                if (
                    aggregate.amount_market_count
                    <= MAX_AGGREGATE_EVIDENCE_MARKETS
                ):
                    aggregate.amount_evidence.extend(
                        (
                            EvidenceReference(
                                "Marche",
                                uid,
                                "codeCPV_values",
                                family_values[family_code][0],
                            ),
                            EvidenceReference(
                                "Marche",
                                uid,
                                "montant_values",
                                str(amount_values[0]),
                            ),
                        )
                    )

            if not duration_values:
                aggregate.duration_missing_value_market_count += 1
            elif len(duration_values) > 1:
                aggregate.duration_multivalued_market_count += 1
            else:
                duration = _decimal_value(
                    duration_values[0], uid=uid, field_name="dureeMois"
                )
                aggregate.duration_total += duration
                aggregate.duration_market_count += 1
                if (
                    aggregate.duration_market_count
                    <= MAX_AGGREGATE_EVIDENCE_MARKETS
                ):
                    aggregate.duration_evidence.extend(
                        (
                            EvidenceReference(
                                "Marche",
                                uid,
                                "codeCPV_values",
                                family_values[family_code][0],
                            ),
                            EvidenceReference(
                                "Marche",
                                uid,
                                "dureeMois_values",
                                str(duration_values[0]),
                            ),
                        )
                    )

    rows: list[QueryRow[CpvFamilyAggregate]] = []
    for family_code, aggregate in sorted(families.items()):
        evidence = tuple(
            (*aggregate.amount_evidence, *aggregate.duration_evidence)
        )
        evidence_complete = (
            aggregate.amount_market_count <= MAX_AGGREGATE_EVIDENCE_MARKETS
            and aggregate.duration_market_count
            <= MAX_AGGREGATE_EVIDENCE_MARKETS
        )
        rows.append(
            QueryRow(
                result=CpvFamilyAggregate(
                    family_code=family_code,
                    market_count=aggregate.market_count,
                    amount_total=aggregate.amount_total,
                    amount_market_count=aggregate.amount_market_count,
                    amount_missing_value_market_count=(
                        aggregate.amount_missing_value_market_count
                    ),
                    amount_missing_source_market_count=(
                        aggregate.amount_missing_source_market_count
                    ),
                    amount_multivalued_market_count=(
                        aggregate.amount_multivalued_market_count
                    ),
                    mean_duration_months=(
                        aggregate.duration_total
                        / aggregate.duration_market_count
                        if aggregate.duration_market_count
                        else None
                    ),
                    duration_market_count=aggregate.duration_market_count,
                    duration_missing_value_market_count=(
                        aggregate.duration_missing_value_market_count
                    ),
                    duration_missing_source_market_count=(
                        aggregate.duration_missing_source_market_count
                    ),
                    duration_multivalued_market_count=(
                        aggregate.duration_multivalued_market_count
                    ),
                    multiple_cpv_market_count=(
                        aggregate.multiple_cpv_market_count
                    ),
                ),
                evidence=evidence,
                evidence_complete=evidence_complete,
            )
        )

    limitations = [
        "Les montants sont des montants déclarés, pas des paiements ni "
        "l'exécution financière ; un montant d'accord-cadre peut représenter "
        "un plafond.",
        "Les marchés à montant unique sont comptés une fois, même si des "
        "lignes source n'ont pas de montant ; leurs absences sont signalées. "
        "Les montants multivalués sont exclus du total.",
        "Les durées à valeur unique sont comptées une fois, même si des "
        "lignes source sont sans durée ; les durées multivaluées sont exclues "
        "de la moyenne et rapportées séparément.",
    ]
    if unclassified_market_count:
        limitations.append(
            f"{unclassified_market_count} marché(s) sans code CPV exploitable "
            "ne peuvent être rattachés à une famille."
        )
    if unmapped_cpv_value_count:
        limitations.append(
            f"{unmapped_cpv_value_count} valeur(s) CPV n'ont pas assez de "
            "chiffres pour déterminer une famille."
        )
    if any(row.result.multiple_cpv_market_count for row in rows):
        limitations.append(
            "Les marchés rattachés à plusieurs familles CPV sont comptés une "
            "fois dans chaque famille concernée ; les totaux de familles ne "
            "sont donc pas nécessairement additifs."
        )
    if any(not row.evidence_complete for row in rows):
        limitations.append(
            "Les preuves détaillées sont limitées aux 25 premiers marchés "
            "par famille et par mesure ; les agrégats utilisent tous les "
            "marchés admissibles."
        )
    return QueryResponse(
        question_id=(3, 8),
        rows=tuple(rows),
        limitations=tuple(limitations),
    )


def rank_buyers(
    session: Session,
    *,
    year: int = 2025,
    limit: int = 10,
) -> QueryResponse[BuyerRanking]:
    _validate_limit(limit)
    records = session.run(
        BUYER_RANKING_QUERY,
        source_id=DATASET_ID,
        year=year,
        limit=limit,
    )
    rows = tuple(
        QueryRow(
            result=BuyerRanking(
                buyer_id=record["buyer_id"],
                names=_names(record["names"]),
                market_count=record["market_count"],
            ),
            evidence=_market_evidence(
                record["market_uids"], "A_ACHETEUR", record["buyer_id"]
            ),
        )
        for record in records
    )
    return QueryResponse(
        question_id=1,
        rows=rows,
        limitations=(
            "Le classement est filtré par année et couvre tout le territoire "
            "national, conformément au périmètre retenu pour cette question.",
            f"Le classement est limité aux {limit} premiers acheteurs.",
        ),
    )


def rank_holders_for_buyer(
    session: Session,
    buyer_id: str,
    *,
    year: int = 2025,
    limit: int = 10,
) -> QueryResponse[HolderRanking]:
    _validate_limit(limit)
    records = session.run(
        HOLDER_RANKING_QUERY,
        source_id=DATASET_ID,
        buyer_id=buyer_id,
        year=year,
        limit=limit,
    )
    rows = tuple(
        QueryRow(
            result=HolderRanking(
                identifier_type=record["identifier_type"],
                identifier_value=record["identifier_value"],
                names=_names(record["names"]),
                market_count=record["market_count"],
            ),
            evidence=tuple(
                evidence_item
                for uid in sorted(set(record["market_uids"]))
                for evidence_item in (
                    EvidenceReference(
                        "Marche", uid, "A_ACHETEUR", buyer_id
                    ),
                    EvidenceReference(
                        "Marche",
                        uid,
                        "A_TITULAIRE",
                        f"{record['identifier_type']}:"
                        f"{record['identifier_value']}",
                    ),
                )
            ),
        )
        for record in records
    )
    return QueryResponse(
        question_id=2,
        rows=rows,
        limitations=(f"Le classement est limité aux {limit} premiers titulaires.",),
    )


def summarize_nature_and_procedures(
    session: Session,
    *,
    year: int = 2025,
) -> QueryResponse[CategoryMarketCount]:
    rows: list[QueryRow[CategoryMarketCount]] = []
    limitations: list[str] = []
    for field, counts_query, coverage_query in (
        ("nature", NATURE_COUNTS_QUERY, NATURE_COVERAGE_QUERY),
        ("procedure", PROCEDURE_COUNTS_QUERY, PROCEDURE_COVERAGE_QUERY),
    ):
        records = session.run(
            counts_query,
            source_id=DATASET_ID,
            year=year,
        )
        rows.extend(
            QueryRow(
                result=CategoryMarketCount(
                    field=field,
                    value=record["value"],
                    market_count=record["market_count"],
                ),
                evidence=_market_evidence(
                    record["market_uids"], f"{field}_values", record["value"]
                ),
            )
            for record in records
        )
        coverage = session.run(
            coverage_query,
            source_id=DATASET_ID,
            year=year,
        ).single()
        if coverage is not None:
            limitations.append(
                f"{field} : {coverage['missing_count']} marché(s) sans valeur "
                f"et {coverage['multivalued_count']} avec plusieurs valeurs "
                f"distinctes, sur {coverage['market_count']} marchés."
            )

    limitations.append(
        "Les valeurs de nature et de procédure sont résumées séparément : "
        "le Parquet agrégé ne conserve pas leur association ligne par ligne "
        "pour les marchés multivalués."
    )
    return QueryResponse(
        question_id=5,
        rows=tuple(rows),
        limitations=tuple(limitations),
    )


def find_holders_with_multiple_buyers(
    session: Session,
    *,
    year: int = 2025,
    limit: int = 10,
) -> QueryResponse[MultiBuyerHolder]:
    _validate_limit(limit)
    records = session.run(
        MULTI_BUYER_HOLDERS_QUERY,
        source_id=DATASET_ID,
        year=year,
        limit=limit,
    )
    rows: list[QueryRow[MultiBuyerHolder]] = []
    for record in records:
        holder_id = (
            f"{record['identifier_type']}:{record['identifier_value']}"
        )
        evidence = tuple(
            evidence_item
            for path in record["market_buyers"]
            for evidence_item in (
                EvidenceReference(
                    "Marche",
                    path["market_uid"],
                    "A_TITULAIRE",
                    holder_id,
                ),
                EvidenceReference(
                    "Marche",
                    path["market_uid"],
                    "A_ACHETEUR",
                    path["buyer_id"],
                ),
            )
        )
        rows.append(
            QueryRow(
                result=MultiBuyerHolder(
                    identifier_type=record["identifier_type"],
                    identifier_value=record["identifier_value"],
                    names=_names(record["names"]),
                    buyer_ids=tuple(sorted(record["buyer_ids"])),
                    market_count=record["market_count"],
                ),
                evidence=evidence,
            )
        )
    return QueryResponse(
        question_id=6,
        rows=tuple(rows),
        limitations=(
            f"Le classement est limité aux {limit} premiers titulaires.",
        ),
    )


def summarize_modification_history(
    session: Session,
    *,
    year: int = 2025,
    limit: int = 10,
) -> QueryResponse[ModificationHistorySummary]:
    _validate_limit(limit)
    summary = session.run(
        MODIFICATION_HISTORY_SUMMARY_QUERY,
        source_id=DATASET_ID,
        year=year,
    ).single()
    if summary is None:
        raise GraphQueryDataError(
            "La synthèse de l'historique des modifications est absente."
        )

    modified_markets = tuple(
        ModifiedMarketCount(
            uid=record["uid"],
            modification_ids=tuple(
                sorted(int(value) for value in record["modification_ids"])
            ),
        )
        for record in session.run(
            MODIFIED_MARKETS_QUERY,
            source_id=DATASET_ID,
            year=year,
            limit=limit,
        )
    )
    unlinked_samples = tuple(
        UnlinkedModification(
            uid=record["uid"],
            modification_id=int(record["modification_id"]),
        )
        for record in session.run(
            UNLINKED_MODIFICATIONS_QUERY,
            source_id=DATASET_ID,
            year=year,
            limit=MAX_AGGREGATE_EVIDENCE_MARKETS,
        )
    )
    evidence = tuple(
        [
            EvidenceReference(
                "Marche",
                market.uid,
                "HAS_MODIFICATION",
                str(modification_id),
            )
            for market in modified_markets
            for modification_id in market.modification_ids
        ]
        + [
            EvidenceReference(
                "Modification",
                f"{item.uid}:{item.modification_id}",
                "initial_market_status",
                "missing_from_snapshot",
            )
            for item in unlinked_samples
        ]
    )
    result = ModificationHistorySummary(
        year=year,
        modified_market_count=int(summary["modified_market_count"]),
        total_version_count=int(summary["total_version_count"]),
        linked_version_count=int(summary["linked_version_count"]),
        unlinked_version_count=int(summary["unlinked_version_count"]),
        modified_markets=modified_markets,
        unlinked_samples=unlinked_samples,
    )
    limitations = [
        "Les versions sont filtrées par année de notification ; seules les "
        "versions reliées à un marché initial sont classées par marché."
    ]
    if result.unlinked_version_count:
        limitations.append(
            f"{result.unlinked_version_count} version(s) n'ont pas de marché "
            "initial dans le snapshot ; elles restent signalées sans créer "
            "de marché fictif."
        )
    if result.modified_market_count > limit:
        limitations.append(
            f"Le détail est limité aux {limit} marchés ayant le plus de "
            "versions."
        )
    if result.unlinked_version_count > len(unlinked_samples):
        limitations.append(
            f"Les preuves des versions sans marché initial sont limitées aux "
            f"{len(unlinked_samples)} premiers exemples."
        )
    return QueryResponse(
        question_id=4,
        rows=(
            QueryRow(
                result=result,
                evidence=evidence,
                evidence_complete=(
                    result.modified_market_count <= limit
                    and result.unlinked_version_count <= len(unlinked_samples)
                ),
            ),
        ),
        limitations=tuple(limitations),
    )


def find_theme_in_buyer_region(
    session: Session,
    theme: str,
    region_code: str,
    *,
    year: int = 2025,
    limit: int = 100,
) -> QueryResponse[ThemedMarket]:
    theme = theme.strip()
    region_code = region_code.strip()
    if not theme:
        raise ValueError("Le thème doit contenir au moins un caractère.")
    if not region_code:
        raise ValueError("Le code de région doit contenir au moins un caractère.")
    _validate_limit(limit)

    parameters = {
        "source_id": DATASET_ID,
        "year": year,
        "theme": theme,
        "region": region_code,
    }
    summary = session.run(
        THEME_REGION_SUMMARY_QUERY,
        **parameters,
    ).single()
    if summary is None:
        raise GraphQueryDataError(
            "La synthèse de recherche par thème et région est absente."
        )

    records = session.run(
        THEME_REGION_MARKETS_QUERY,
        **parameters,
        limit=limit,
    )
    rows = tuple(
        QueryRow(
            result=ThemedMarket(
                uid=record["uid"],
                region_code=record["region_code"],
                matching_objects=tuple(sorted(record["matching_objects"])),
            ),
            evidence=tuple(
                EvidenceReference(
                    "Marche",
                    record["uid"],
                    "objet_values",
                    text_value,
                )
                for text_value in sorted(record["matching_objects"])
            )
            + (
                EvidenceReference(
                    "Marche",
                    record["uid"],
                    "acheteur_region_code_values",
                    record["region_code"],
                ),
            ),
            evidence_complete=(
                int(summary["matching_region_market_count"]) <= limit
            ),
        )
        for record in records
    )
    metadata = (
        ("theme_market_count", int(summary["theme_market_count"])),
        ("missing_region_count", int(summary["missing_region_count"])),
        ("multivalued_region_count", int(summary["multivalued_region_count"])),
        (
            "matching_region_market_count",
            int(summary["matching_region_market_count"]),
        ),
    )
    limitations = [
        "Le thème est recherché comme sous-chaîne insensible à la casse dans "
        "les valeurs distinctes de l'objet.",
        "Les marchés sans région ou ayant plusieurs régions sont exclus du "
        "résultat par région et comptés séparément.",
    ]
    if summary["matching_region_market_count"] > limit:
        limitations.append(
            f"Seuls les {limit} premiers marchés correspondants sont détaillés."
        )
    return QueryResponse(
        question_id=7,
        rows=rows,
        limitations=tuple(limitations),
        metadata=metadata,
    )


def find_holder_name_variants(
    session: Session,
    *,
    limit: int = 25,
) -> QueryResponse[HolderNameVariants]:
    _validate_limit(limit)
    summary = session.run(
        HOLDER_NAME_VARIANTS_COUNT_QUERY,
        source_id=DATASET_ID,
    ).single()
    if summary is None:
        raise GraphQueryDataError(
            "Le compte des variantes de noms titulaires est absent."
        )
    records = session.run(
        HOLDER_NAME_VARIANTS_QUERY,
        source_id=DATASET_ID,
        limit=limit,
    )
    rows: list[QueryRow[HolderNameVariants]] = []
    for record in records:
        identifier_type = record["identifier_type"]
        identifier_value = record["identifier_value"]
        holder_id = f"{identifier_type}:{identifier_value}"
        names = _names(record["names"])
        market_uids = tuple(sorted(set(record["market_uids"] or ())))
        evidence = tuple(
            [
                EvidenceReference(
                    "Titulaire", holder_id, "nom_values", name
                )
                for name in names
            ]
            + [
                EvidenceReference(
                    "Marche", uid, "A_TITULAIRE", holder_id
                )
                for uid in market_uids[:MAX_AGGREGATE_EVIDENCE_MARKETS]
            ]
        )
        rows.append(
            QueryRow(
                result=HolderNameVariants(
                    identifier_type=identifier_type,
                    identifier_value=identifier_value,
                    names=names,
                    market_count=len(market_uids),
                ),
                evidence=evidence,
                evidence_complete=(
                    len(market_uids) <= MAX_AGGREGATE_EVIDENCE_MARKETS
                ),
            )
        )
    limitations = [
        "Les variantes sont regroupées uniquement sous l'identité titulaire "
        "déjà résolue par identifiant typé ; les noms seuls ne fusionnent pas "
        "des titulaires.",
        "Les résultats sont limités aux titulaires ayant plusieurs noms, "
        f"avec un plafond de {limit} titulaires et {MAX_AGGREGATE_EVIDENCE_MARKETS} "
        "preuves de marchés par titulaire.",
    ]
    if summary["holder_count"] > limit:
        limitations.append(
            f"Seuls les {limit} premiers titulaires avec des variantes sont "
            "détaillés."
        )
    if summary["holder_count"] == 0:
        limitations.append(
            "Aucun titulaire avec plusieurs noms distincts n'a été trouvé "
            "dans le snapshot interrogé."
        )
    return QueryResponse(
        question_id=9,
        rows=tuple(rows),
        limitations=tuple(limitations),
        metadata=(("variant_holder_count", int(summary["holder_count"])),),
    )


def summarize_graph_data_issues(
    session: Session,
) -> QueryResponse[DataQualityIssue]:
    records = session.run(
        DATA_QUALITY_ISSUES_QUERY,
        source_id=DATASET_ID,
    )
    rows: list[QueryRow[DataQualityIssue]] = []
    for record in records:
        sample_node_ids = tuple(record["sample_node_ids"])
        affected_count = int(record["affected_record_count"])
        issue_code = record["issue"]
        node_type = record["node_type"]
        evidence = tuple(
            EvidenceReference(
                node_type,
                node_id,
                issue_code,
                "observed",
            )
            for node_id in sample_node_ids
        )
        rows.append(
            QueryRow(
                result=DataQualityIssue(
                    node_type=node_type,
                    issue_code=issue_code,
                    affected_record_count=affected_count,
                ),
                evidence=evidence,
                evidence_complete=affected_count <= len(sample_node_ids),
            )
        )
    limitations = (
        "Les valeurs manquantes reflètent les indicateurs source ; les valeurs "
        "multiples signalent une hétérogénéité conservée, pas une erreur "
        "automatiquement arbitrée.",
        "Les preuves listent jusqu'à 25 exemples par signal ; les comptes "
        "portent sur tous les nœuds du snapshot.",
    )
    return QueryResponse(
        question_id=10,
        rows=tuple(rows),
        limitations=limitations,
    )
