from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph import contracts, demo, load_initial_awards, load_modifications
from marchegraph.graph.neo4j_config import (
    LocalNeo4jURLError,
    validate_local_neo4j_uri,
)
from marchegraph.graph.queries import QueryResponse


class GraphContractTests(unittest.TestCase):
    def test_domain_contracts_live_in_the_framework_independent_module(self):
        self.assertIs(QueryResponse, contracts.QueryResponse)
        self.assertEqual(QueryResponse.__module__, contracts.__name__)
        self.assertEqual(
            contracts.DemoBuyerRanking.__module__,
            contracts.__name__,
        )

    def test_contract_module_imports_only_standard_library_dependencies(self):
        module_path = (
            Path(__file__).resolve().parents[1]
            / "src/marchegraph/graph/contracts.py"
        )
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported_modules = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        self.assertTrue(imported_modules <= sys.stdlib_module_names)

    def test_graph_entrypoints_accept_only_loopback_neo4j_uris(self):
        for uri in (
            "bolt://localhost:7687",
            "bolt://127.0.0.1:7687",
            "bolt://[::1]:7687",
        ):
            with self.subTest(uri=uri):
                validate_local_neo4j_uri(uri)

        with self.assertRaises(LocalNeo4jURLError):
            validate_local_neo4j_uri("bolt://neo4j.example:7687")

    def test_graph_entrypoints_reject_remote_uris_before_connecting(self):
        environment = {
            "NEO4J_PASSWORD": "fixture-password",
            "NEO4J_URI": "bolt://neo4j.example:7687",
        }
        with patch.dict(os.environ, environment):
            with patch.object(load_initial_awards.GraphDatabase, "driver") as driver:
                with self.assertRaises(load_initial_awards.InitialAwardLoadError):
                    load_initial_awards.run_import(
                        Path("unused.parquet"),
                        Path("unused-identities.parquet"),
                        1,
                    )
                driver.assert_not_called()

            with patch.object(load_modifications.GraphDatabase, "driver") as driver:
                with self.assertRaises(load_modifications.ModificationLoadError):
                    load_modifications.run_import(Path("unused.parquet"), 1)
                driver.assert_not_called()

            with tempfile.TemporaryDirectory() as directory:
                with patch.object(demo.GraphDatabase, "driver") as driver:
                    with self.assertRaises(demo.DemoError):
                        demo.run_demo(Path(directory) / "output")
                    driver.assert_not_called()


if __name__ == "__main__":
    unittest.main()
