"""Valeurs les plus fréquentes de chaque dimension, lues dans le graphe (lecture seule)."""
from __future__ import annotations

import re

from neo4j import Session

from marchegraph.graph import queries as reference_queries
from marchegraph.queries.interpretation import SUPPORTED_YEARS
from marchegraph.queries.suggestions import REGION_NAMES, Suggestions, Value, example_year

TOP_VALUES = 20

YEARS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
RETURN toString(market.annee) AS value, count(*) AS market_count
ORDER BY market_count DESC, value ASC
"""

REGIONS_QUERY = """
MATCH (market:Marche {source_id: $source_id})
WHERE size(coalesce(market.acheteur_region_code_values, [])) = 1
RETURN market.acheteur_region_code_values[0] AS value, count(*) AS market_count
ORDER BY market_count DESC, value ASC
"""

CPV_FAMILIES_QUERY = """
MATCH (market:Marche {source_id: $source_id})
UNWIND coalesce(market.codeCPV_values, []) AS code
WITH DISTINCT market, left(toString(code), 3) AS value
RETURN value, count(*) AS market_count
ORDER BY market_count DESC, value ASC
LIMIT $limit
"""

PROCEDURES_QUERY = """
MATCH (market:Marche {source_id: $source_id})
UNWIND coalesce(market.procedure_values, []) AS value
WITH DISTINCT market, value
RETURN value, count(*) AS market_count
ORDER BY market_count DESC, value ASC
LIMIT $limit
"""

NATURES_QUERY = """
MATCH (market:Marche {source_id: $source_id})
UNWIND coalesce(market.nature_values, []) AS value
WITH DISTINCT market, value
RETURN value, count(*) AS market_count
ORDER BY market_count DESC, value ASC
LIMIT $limit
"""

BUYERS_QUERY = """
MATCH (market:Marche {source_id: $source_id})-[:A_ACHETEUR]->
      (buyer:Acheteur {source_id: $source_id})
WHERE market.annee = $year
WITH buyer, count(DISTINCT market.uid) AS market_count
ORDER BY market_count DESC, buyer.id ASC
LIMIT $limit
RETURN buyer.id AS value, head(coalesce(buyer.nom_values, [])) AS name, market_count
"""


def _values(session: Session, query: str, **parameters) -> list[dict]:
    return [dict(record) for record in session.run(
        query, source_id=reference_queries.DATASET_ID, **parameters)]


def load_suggestions(session: Session, *, limit: int = TOP_VALUES) -> Suggestions:
    years = tuple(
        Value(r["value"], r["value"], int(r["market_count"]))
        for r in _values(session, YEARS_QUERY)
        if r["value"] is not None and int(r["value"]) in SUPPORTED_YEARS
    )
    year = example_year(years)
    regions = tuple(
        Value(r["value"], REGION_NAMES[r["value"]], int(r["market_count"]))
        for r in _values(session, REGIONS_QUERY)
        if r["value"] in REGION_NAMES
    )
    families = tuple(
        Value(r["value"], f"CPV {r['value']}", int(r["market_count"]))
        for r in _values(session, CPV_FAMILIES_QUERY, limit=limit)
        if re.fullmatch(r"\d{3}", r["value"] or "")
    )

    def plain(query: str) -> tuple[Value, ...]:
        return tuple(
            Value(str(r["value"]), str(r["value"]), int(r["market_count"]))
            for r in _values(session, query, limit=limit)
            if r["value"] is not None and str(r["value"]).strip()
        )

    buyers = tuple(
        Value(str(r["value"]), f"{r['name'] or r['value']} ({r['value']})",
              int(r["market_count"]))
        for r in _values(session, BUYERS_QUERY, year=year, limit=limit)
    )
    return Suggestions(year, years, regions, families, plain(PROCEDURES_QUERY),
                       plain(NATURES_QUERY), buyers)
