from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlparse

import duckdb
from neo4j import GraphDatabase
from rdflib import Graph, Namespace, RDF, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph import load_initial_awards, load_modifications, queries
from marchegraph.graph.demo_data import DEMO_DATA
from marchegraph.graph.rdf_export import graph_from_data
from marchegraph.graph.validation import validate_graph, write_rejections


ROOT = Path(__file__).resolve().parents[1]
MG = Namespace("https://example.org/marchegraph/")
SOURCE_ID = "story-3-9-local-integration-fixture"
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")


def _write_source_fixtures(directory: Path) -> tuple[Path, Path]:
    source_path = directory / "prepared-decp.parquet"
    identities_path = directory / "holder-identities.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(
            """
            CREATE TABLE decp (
                uid VARCHAR,
                id VARCHAR,
                modification_id SMALLINT,
                dateNotification DATE,
                nature VARCHAR,
                acheteur_id VARCHAR,
                acheteur_nom VARCHAR,
                acheteur_region_code VARCHAR,
                titulaire_id VARCHAR,
                titulaire_typeIdentifiant VARCHAR,
                titulaire_nom VARCHAR,
                objet VARCHAR,
                montant DOUBLE,
                type VARCHAR,
                codeCPV VARCHAR,
                procedure VARCHAR,
                dureeMois SMALLINT
            )
            """
        )
        connection.executemany(
            "INSERT INTO decp VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "story-3-9-market-2024",
                    "initial-2024",
                    0,
                    "2024-02-01",
                    "Travaux",
                    "buyer-2024",
                    "Acheteur 2024",
                    "11",
                    "00000000000001",
                    "SIRET",
                    "Titulaire Alpha",
                    "Travaux 2024",
                    50.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    12,
                ),
                (
                    "story-3-9-market-a",
                    "initial-a-1",
                    0,
                    "2025-02-01",
                    "Travaux",
                    "buyer-a",
                    "Acheteur A",
                    "11",
                    "00000000000001",
                    "SIRET",
                    "Titulaire Alpha",
                    "Travaux de voirie",
                    100.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    12,
                ),
                (
                    "story-3-9-market-a",
                    "initial-a-2",
                    0,
                    "2025-02-01",
                    "Services",
                    "buyer-a",
                    "Acheteur A",
                    None,
                    "00000000000001",
                    "siret",
                    "Alpha SAS",
                    None,
                    None,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    None,
                ),
                (
                    "story-3-9-market-b",
                    "initial-b",
                    0,
                    "2025-03-01",
                    "Fournitures",
                    "buyer-b",
                    "Acheteur B",
                    "84",
                    "00000000000001",
                    "SIRET",
                    "Titulaire Alpha",
                    "Fournitures",
                    200.0,
                    "Marché",
                    "30000000",
                    "Procédure adaptée",
                    6,
                ),
                (
                    "story-3-9-market-2024",
                    "modification-2024",
                    1,
                    "2024-06-01",
                    "Travaux",
                    "buyer-2024",
                    "Acheteur 2024",
                    "11",
                    "00000000000001",
                    "SIRET",
                    "Titulaire Alpha",
                    "Avenant 2024",
                    55.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    13,
                ),
                (
                    "story-3-9-market-a",
                    "modification-a",
                    1,
                    "2025-04-01",
                    "Travaux",
                    "buyer-a",
                    "Acheteur A",
                    "11",
                    "00000000000001",
                    "SIRET",
                    "Titulaire Alpha",
                    "Avenant voirie",
                    110.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    14,
                ),
                (
                    "story-3-9-orphan",
                    "modification-orphan",
                    1,
                    "2025-05-01",
                    None,
                    "buyer-missing-market",
                    "Acheteur sans marché initial",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            ],
        )
        connection.execute(
            "COPY decp TO ? (FORMAT PARQUET)",
            [str(source_path)],
        )
        connection.execute(
            """
            CREATE TABLE identities (
                year INTEGER,
                status VARCHAR,
                normalized_type VARCHAR,
                normalized_value VARCHAR,
                source_line_count BIGINT
            )
            """
        )
        connection.executemany(
            "INSERT INTO identities VALUES (?, ?, ?, ?, ?)",
            [
                (2024, "resolved", "SIRET", "00000000000001", 1),
                (2025, "resolved", "SIRET", "00000000000001", 3),
            ],
        )
        connection.execute(
            "COPY identities TO ? (FORMAT PARQUET)",
            [str(identities_path)],
        )
    finally:
        connection.close()
    return source_path, identities_path


@unittest.skipUnless(
    NEO4J_PASSWORD,
    "Set NEO4J_PASSWORD to run the local Neo4j end-to-end fixture.",
)
class GraphEndToEndTests(unittest.TestCase):
    def test_local_fixture_covers_load_queries_validation_and_rdf_export(self):
        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        if urlparse(uri).hostname not in {"127.0.0.1", "localhost", "::1"}:
            self.fail("The end-to-end fixture must connect only to local Neo4j.")

        with TemporaryDirectory() as temporary_directory:
            source_path, identities_path = _write_source_fixtures(
                Path(temporary_directory)
            )
            rdf_path = Path(temporary_directory) / "fixture.ttl"
            rejection_path = Path(temporary_directory) / "rejections.jsonl"

            with GraphDatabase.driver(
                uri,
                auth=(
                    os.environ.get("NEO4J_USERNAME", "neo4j"),
                    NEO4J_PASSWORD,
                ),
            ) as driver:
                driver.verify_connectivity()
                with driver.session(
                    database=os.environ.get("NEO4J_DATABASE", "neo4j")
                ) as session:
                    session.run(
                        "MATCH (node {source_id: $source_id}) DETACH DELETE node",
                        source_id=SOURCE_ID,
                    ).consume()
                    try:
                        with (
                            patch.object(
                                load_initial_awards, "DATASET_ID", SOURCE_ID
                            ),
                            patch.object(
                                load_modifications, "DATASET_ID", SOURCE_ID
                            ),
                            patch.object(queries, "DATASET_ID", SOURCE_ID),
                        ):
                            load_initial_awards.load_initial_awards(
                                session, source_path, identities_path
                            )
                            load_modifications.load_modification_versions(
                                session, source_path
                            )
                            responses = (
                                queries.rank_buyers(session, year=2025),
                                queries.rank_holders_for_buyer(
                                    session, "buyer-a", year=2025
                                ),
                                queries.aggregate_amounts_and_durations_by_cpv(
                                    session, year=2025
                                ),
                                queries.summarize_nature_and_procedures(
                                    session, year=2025
                                ),
                                queries.find_holders_with_multiple_buyers(
                                    session, year=2025
                                ),
                                queries.summarize_modification_history(
                                    session, year=2025
                                ),
                                queries.find_theme_in_buyer_region(
                                    session, "voirie", "11", year=2025
                                ),
                                queries.find_holder_name_variants(session),
                                queries.summarize_graph_data_issues(session),
                            )

                        question_ids = {
                            question_id
                            for response in responses
                            for question_id in (
                                response.question_id
                                if isinstance(response.question_id, tuple)
                                else (response.question_id,)
                            )
                        }
                        self.assertEqual(question_ids, set(range(1, 11)))
                        self.assertTrue(all(response.rows for response in responses))
                        self.assertTrue(
                            all(
                                any(row.evidence for row in response.rows)
                                for response in responses
                            )
                        )
                        self.assertEqual(
                            responses[5].rows[0].result.unlinked_version_count,
                            1,
                        )
                        self.assertEqual(
                            responses[6].rows[0].result.region_code,
                            "11",
                        )
                        self.assertGreaterEqual(
                            len(responses[7].rows[0].result.names),
                            2,
                        )

                        ontology = Graph()
                        ontology.parse(
                            ROOT / "docs/exemple/ontologie.ttl",
                            format="turtle",
                        )
                        shapes = Graph()
                        shapes.parse(
                            ROOT / "docs/exemple/formes.ttl",
                            format="turtle",
                        )
                        exported_graph = graph_from_data(DEMO_DATA)
                        validation = validate_graph(
                            exported_graph, shapes, ontology
                        )
                        self.assertTrue(validation.conforms, validation.summary)
                        exported_graph.serialize(
                            destination=rdf_path,
                            format="turtle",
                        )
                        reloaded_graph = Graph()
                        reloaded_graph.parse(rdf_path, format="turtle")
                        self.assertIn(
                            (None, RDF.type, MG.Modification),
                            reloaded_graph,
                        )

                        market = URIRef(
                            "https://marchegraph.local/resource/marche/"
                            "demo-marche-2025-001"
                        )
                        rejected_graph = graph_from_data(DEMO_DATA)
                        rejected_graph.remove((market, MG.acheteur, None))
                        rejection_report = validate_graph(
                            rejected_graph, shapes, ontology
                        )
                        self.assertFalse(rejection_report.conforms)
                        self.assertIn(
                            "MG-VAL-MARCHE-ACHETEUR-001",
                            {
                                reason.rule_id
                                for record in rejection_report.rejected_records
                                for reason in record.reasons
                            },
                        )
                        write_rejections(
                            rejection_report, rejection_path
                        )
                        saved_rejections = [
                            json.loads(line)
                            for line in rejection_path.read_text(
                                encoding="utf-8"
                            ).splitlines()
                        ]
                        self.assertTrue(saved_rejections)
                    finally:
                        session.run(
                            "MATCH (node {source_id: $source_id}) "
                            "DETACH DELETE node",
                            source_id=SOURCE_ID,
                        ).consume()


if __name__ == "__main__":
    unittest.main()
