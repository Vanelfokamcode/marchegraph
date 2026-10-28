from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from rdflib import Graph

from marchegraph.graph.demo_data import DEMO_ID
from marchegraph.graph.neo4j_store import (
    assert_connection,
    load_demo_data,
    read_demo_data,
    top_buyer_with_evidence,
)
from marchegraph.graph.neo4j_config import (
    LocalNeo4jURLError,
    validate_local_neo4j_uri,
)
from marchegraph.graph.rdf_export import graph_from_data
from marchegraph.graph.validation import validate_graph

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = PROJECT_ROOT / "data/prepared/graph-demo"
ONTOLOGY_PATH = PROJECT_ROOT / "docs/exemple/ontologie.ttl"
SHAPES_PATH = PROJECT_ROOT / "docs/exemple/formes.ttl"


class DemoError(Exception):
    pass


def run_demo(output_dir: Path) -> None:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise DemoError("NEO4J_PASSWORD doit être défini dans l'environnement.")

    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    try:
        validate_local_neo4j_uri(uri)
    except LocalNeo4jURLError as error:
        raise DemoError(str(error)) from error
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            assert_connection(driver)
            with driver.session(database=database) as session:
                load_demo_data(session)
                answer = top_buyer_with_evidence(session)
                demo_data = read_demo_data(session)
    except (DriverError, Neo4jError) as error:
        raise DemoError(
            f"Connexion ou requête Neo4j impossible ({uri}) : {error}"
        ) from error

    if answer is None:
        raise DemoError("La question de référence 1 n'a retourné aucun résultat.")

    ontology = Graph()
    ontology.parse(ONTOLOGY_PATH, format="turtle")
    shapes = Graph()
    shapes.parse(SHAPES_PATH, format="turtle")
    data_graph = graph_from_data(demo_data)
    validation = validate_graph(data_graph, shapes, ontology)
    if not validation.conforms:
        detail = "; ".join(validation.violations) or validation.summary
        raise DemoError(f"Le graphe synthétique ne respecte pas SHACL : {detail}")

    output_path = output_dir / "graph-demo.ttl"
    data_graph.serialize(destination=output_path, format="turtle")
    print(f"Démonstration locale prête (jeu synthétique : {DEMO_ID}).")
    print(
        "Question 1 — Acheteur avec le plus de marchés initiaux distincts : "
        f"{answer.buyer_name} ({answer.market_count})."
    )
    for uid in sorted(answer.market_uids):
        print(
            f"Preuve : marche:{uid} "
            f"--A_ACHETEUR--> acheteur:{answer.buyer_id}"
        )
    print(
        "Modèle visible : "
        f"{len(demo_data.markets)} marché, "
        f"{sum(len(market.holder_ids) for market in demo_data.markets)} liens "
        f"vers {len(demo_data.holders)} titulaires, "
        f"{len(demo_data.modifications)} modification."
    )
    print("Validation SHACL : conforme.")
    print(f"Export RDF local : {output_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Charge et vérifie un cas synthétique Neo4j/RDF/SHACL."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Dossier local de l'export RDF (défaut : data/prepared/graph-demo).",
    )
    args = parser.parse_args(argv)
    try:
        run_demo(args.output_dir)
    except DemoError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
