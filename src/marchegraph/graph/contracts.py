from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Generic, TypeVar

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
class DemoBuyerRanking:
    buyer_id: str
    buyer_name: str
    market_count: int
    market_uids: tuple[str, ...]


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
