"""Exécute une question reconnue avec la requête préparée correspondante."""
from __future__ import annotations

from typing import Callable

from neo4j import Session

from marchegraph.graph import queries as q
from marchegraph.graph.contracts import QueryResponse
from marchegraph.queries.interpretation import Interpretation

QUERY_FUNCTIONS: dict[int | tuple[int, ...], Callable[..., QueryResponse]] = {
    1: q.rank_buyers,
    2: q.rank_holders_for_buyer,
    3: q.aggregate_amounts_and_durations_by_cpv,
    4: q.summarize_modification_history,
    5: q.summarize_nature_and_procedures,
    6: q.find_holders_with_multiple_buyers,
    7: q.find_theme_in_buyer_region,
    8: q.aggregate_amounts_and_durations_by_cpv,
    9: q.find_holder_name_variants,
    10: q.summarize_graph_data_issues,
    (3, 8): q.aggregate_amounts_and_durations_by_cpv,
}


def run(session: Session, interpretation: Interpretation) -> QueryResponse:
    function = QUERY_FUNCTIONS[interpretation.question_id]
    return function(session, **interpretation.params)
