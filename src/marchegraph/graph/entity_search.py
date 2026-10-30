"""Recherche plein texte (BM25, Lucene) des acheteurs et titulaires par leur nom.

`python -m marchegraph.graph.entity_search` crée les index : c'est une écriture
de schéma, réservée au pipeline (AD-3). La recherche, elle, est en lecture
seule et ne renvoie que des candidats avec identifiant exact et score.
"""
from __future__ import annotations

import os
from dataclasses import replace

from neo4j import Session

from marchegraph.graph import queries as reference_queries
from marchegraph.queries.entity_lookup import (
    Candidate,
    Resolution,
    by_market_count,
    decide,
    lucene_query,
    organisation,
    shared_sirens,
    siren_of,
)

INDEXES = {"acheteur": "acheteur_noms", "titulaire": "titulaire_noms"}
ANALYZER = "standard-folding"
SEARCH_LIMIT = 20

CREATE_INDEXES = (
    "CREATE FULLTEXT INDEX acheteur_noms IF NOT EXISTS "
    "FOR (n:Acheteur) ON EACH [n.nom_values] "
    f"OPTIONS {{indexConfig: {{`fulltext.analyzer`: '{ANALYZER}'}}}}",
    "CREATE FULLTEXT INDEX titulaire_noms IF NOT EXISTS "
    "FOR (n:Titulaire) ON EACH [n.nom_values] "
    f"OPTIONS {{indexConfig: {{`fulltext.analyzer`: '{ANALYZER}'}}}}",
)

SEARCH_QUERIES = {
    "acheteur": """
CALL db.index.fulltext.queryNodes($index, $search_text) YIELD node, score
WHERE node.source_id = $source_id
WITH node, score ORDER BY score DESC LIMIT $limit
RETURN node.id AS identifier, coalesce(node.nom_values, []) AS names, score,
       COUNT { (:Marche)-[:A_ACHETEUR]->(node) } AS market_count
""",
    "titulaire": """
CALL db.index.fulltext.queryNodes($index, $search_text) YIELD node, score
WHERE node.source_id = $source_id
WITH node, score ORDER BY score DESC LIMIT $limit
RETURN node.identifier_type + ':' + node.identifier_value AS identifier,
       coalesce(node.nom_values, []) AS names, score,
       COUNT { (:Marche)-[:A_TITULAIRE]->(node) } AS market_count
""",
}

ORGANISATION_QUERY = """
MATCH (buyer:Acheteur {source_id: $source_id})
WHERE buyer.id STARTS WITH $siren AND size(buyer.id) = 14
OPTIONAL MATCH (market:Marche)-[:A_ACHETEUR]->(buyer)
RETURN count(DISTINCT buyer) AS establishments,
       count(DISTINCT market) AS market_count
"""


def create_search_indexes(session: Session) -> None:
    for statement in CREATE_INDEXES:
        session.run(statement).consume()
    session.run("CALL db.awaitIndexes(600)").consume()


def search_indexes_online(session: Session) -> bool:
    states = {
        record["name"]: record["state"]
        for record in session.run("SHOW FULLTEXT INDEXES YIELD name, state")
    }
    return all(states.get(name) == "ONLINE" for name in INDEXES.values())


def search(session: Session, kind: str, mention: str) -> list[Candidate]:
    search_text = lucene_query(mention)
    if search_text is None:
        return []
    records = session.run(
        SEARCH_QUERIES[kind],
        index=INDEXES[kind],
        search_text=search_text,
        source_id=reference_queries.DATASET_ID,
        limit=SEARCH_LIMIT,
    )
    return [
        Candidate(kind, str(r["identifier"]), tuple(sorted(set(r["names"]))),
                  float(r["score"]), int(r["market_count"]))
        for r in records
    ]


def resolve(session: Session, kind: str, mention: str) -> Resolution:
    resolution = decide(mention, search(session, kind, mention))
    if resolution.status != "choose":
        return resolution
    return replace(resolution, options=with_organisations(session, resolution.options))


def with_organisations(session: Session, options) -> tuple[Candidate, ...]:
    groups = []
    for siren in shared_sirens(options):
        record = session.run(ORGANISATION_QUERY, siren=siren,
                             source_id=reference_queries.DATASET_ID).single()
        members = [o for o in options if siren_of(o.identifier) == siren]
        groups.append(organisation(siren, members, int(record["market_count"]),
                                   int(record["establishments"])))
    return by_market_count([*groups, *options])


def main() -> int:
    from neo4j import GraphDatabase

    from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("NEO4J_PASSWORD doit être défini dans l'environnement.")
        return 1
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    validate_local_neo4j_uri(uri)
    auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), password)
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
        database=os.environ.get("NEO4J_DATABASE", "neo4j")
    ) as session:
        create_search_indexes(session)
        print("Index plein texte prêts :", ", ".join(INDEXES.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
