from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class QueryResponse(Generic[T]):
    question_id: int
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
