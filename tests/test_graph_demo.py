from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import Graph, Namespace, RDF, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph.demo_data import DEMO_DATA
from marchegraph.graph.rdf_export import graph_from_data
from marchegraph.graph.validation import validate_graph, write_rejections


ROOT = Path(__file__).resolve().parents[1]
MG = Namespace("https://example.org/marchegraph/")


def load_shapes() -> Graph:
    shapes = Graph()
    shapes.parse(ROOT / "docs/exemple/formes.ttl", format="turtle")
    return shapes


class GraphDemoTests(unittest.TestCase):
    def test_synthetic_graph_preserves_multi_holder_and_modification(self) -> None:
        graph = graph_from_data(DEMO_DATA)
        market = URIRef(
            "https://marchegraph.local/resource/marche/demo-marche-2025-001"
        )
        self.assertEqual(len(list(graph.objects(market, MG.titulaire))), 2)
        self.assertEqual(
            len(list(graph.subjects(RDF.type, MG.Modification))),
            1,
        )
        ontology = Graph()
        ontology.parse(ROOT / "docs/exemple/ontologie.ttl", format="turtle")
        self.assertTrue(validate_graph(graph, load_shapes(), ontology).conforms)

    def test_shacl_reports_invalid_siret(self) -> None:
        invalid_holder = replace(DEMO_DATA.holders[0], identifier_value="123")
        data = replace(
            DEMO_DATA,
            holders=(invalid_holder, *DEMO_DATA.holders[1:]),
        )
        graph = graph_from_data(data)
        ontology = Graph()
        ontology.parse(ROOT / "docs/exemple/ontologie.ttl", format="turtle")

        report = validate_graph(graph, load_shapes(), ontology)

        self.assertFalse(report.conforms)
        self.assertIn(
            "Un SIRET contient exactement 14 chiffres.",
            report.violations,
        )
        rejection = next(
            item
            for item in report.rejected_records
            if str(item.focus_node).endswith("/titulaire/holder-demo-1")
        )
        self.assertIn(
            "MG-VAL-TITULAIRE-SIRET-006",
            {reason.rule_id for reason in rejection.reasons},
        )
        self.assertTrue(
            any(str(predicate) == str(MG.siret) for _, predicate, _ in rejection.triples)
        )

        with TemporaryDirectory() as directory:
            output_path = Path(directory) / "reports" / "rejections.jsonl"
            write_rejections(report, output_path)
            saved = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(
            saved["focus_node"],
            rejection.focus_node.n3(),
        )
        self.assertIn(
            "MG-VAL-TITULAIRE-SIRET-006",
            {reason["rule_id"] for reason in saved["reasons"]},
        )
        self.assertTrue(saved["triples"])

    def test_shacl_reports_market_without_buyer(self) -> None:
        graph = graph_from_data(DEMO_DATA)
        market = URIRef(
            "https://marchegraph.local/resource/marche/demo-marche-2025-001"
        )
        graph.remove((market, MG.acheteur, None))

        ontology = Graph()
        ontology.parse(ROOT / "docs/exemple/ontologie.ttl", format="turtle")
        report = validate_graph(graph, load_shapes(), ontology)

        self.assertFalse(report.conforms)
        self.assertTrue(report.violations)
        market_rejection = next(
            item
            for item in report.rejected_records
            if str(item.focus_node).endswith("/marche/demo-marche-2025-001")
        )
        self.assertIn(
            "MG-VAL-MARCHE-ACHETEUR-001",
            {reason.rule_id for reason in market_rejection.reasons},
        )
        self.assertTrue(market_rejection.triples)
        self.assertTrue(
            all(reason.message for reason in market_rejection.reasons)
        )


if __name__ == "__main__":
    unittest.main()
