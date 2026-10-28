from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar

from neo4j import Session

from marchegraph.graph.load_initial_awards import DATASET_ID

T = TypeVar("T")


@dataclass(frozen=True)
class EvidenceReference:
    market_uid: str
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
        EvidenceReference(str(uid), predicate, object_id)
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
                                uid,
                                "codeCPV_values",
                                family_values[family_code][0],
                            ),
                            EvidenceReference(
                                uid, "montant_values", str(amount_values[0])
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
                                uid,
                                "codeCPV_values",
                                family_values[family_code][0],
                            ),
                            EvidenceReference(
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
            "national : la région de l’acheteur n’est pas présente dans le "
            "graphe chargé.",
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
                    EvidenceReference(uid, "A_ACHETEUR", buyer_id),
                    EvidenceReference(
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
                    path["market_uid"], "A_TITULAIRE", holder_id
                ),
                EvidenceReference(
                    path["market_uid"], "A_ACHETEUR", path["buyer_id"]
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
