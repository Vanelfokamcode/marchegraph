from __future__ import annotations

import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.evaluation import dataset
from marchegraph.evaluation.coverage import summarize, to_markdown
from marchegraph.evaluation.coverage_cases import CATALOGUE_ROUTE, Route, build_cases
from marchegraph.queries.catalogue import validate
from marchegraph.queries.suggestions import Suggestions, Value

FIXTURE_VALUES = Suggestions(
    2025,
    years=(Value("2025", "2025", 2), Value("2024", "2024", 1)),
    regions=(Value("11", "Île-de-France", 2),),
    cpv_families=(Value("450", "CPV 450", 2),),
    procedures=(Value("Appel d'offres", "Appel d'offres", 2),),
    natures=(Value("Marché", "Marché", 3),),
    buyers=(Value(dataset.BUYER_A, f"Acheteur A ({dataset.BUYER_A})", 1),),
)


class CaseGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = build_cases(FIXTURE_VALUES)

    def test_categories_and_sizes(self) -> None:
        counts = Counter(case.category for case in self.cases)
        self.assertEqual(counts["référence"], 10)
        self.assertEqual(counts["hors périmètre"], 10)
        self.assertGreaterEqual(counts["paraphrase"], 20)
        self.assertGreaterEqual(counts["catalogue"], 50)
        self.assertGreaterEqual(counts["combinaison invalide"], 5)
        self.assertEqual(counts["entité citée"], 4)
        self.assertEqual(len({case.question for case in self.cases}), len(self.cases))

    def test_catalogue_routes_are_valid_and_invalid_ones_expect_abstention(self) -> None:
        for case in self.cases:
            catalogue = [r for r in case.routes if r.question_id == CATALOGUE_ROUTE]
            for route in catalogue:
                validate(dict(route.params)["query"])
            if case.category == "combinaison invalide":
                self.assertEqual(case.routes, ())

    def test_equivalent_reference_questions_are_accepted(self) -> None:
        case = next(c for c in self.cases
                    if c.question == "Quel est le nombre de marchés par acheteur en 2025 ?")
        self.assertIn(Route.of(1, {"year": 2025}), case.routes)

    def test_generation_is_deterministic(self) -> None:
        self.assertEqual(self.cases, build_cases(FIXTURE_VALUES))


class SummaryTests(unittest.TestCase):
    def test_rates_per_category_and_total(self) -> None:
        records = [
            {"catégorie": "catalogue", "attendu": "réponse",
             "assistant": {"label": "correct", "secondes": 1.0}},
            {"catégorie": "catalogue", "attendu": "réponse",
             "assistant": {"label": "mauvaise question", "secondes": 3.0,
                           "texte_halluciné": True}},
            {"catégorie": "catalogue", "attendu": "réponse",
             "assistant": {"label": "abstention à tort", "secondes": 2.0}},
            {"catégorie": "hors périmètre", "attendu": "abstention",
             "assistant": {"label": "abstention correcte", "secondes": 0.0}},
        ]
        summary = summarize(records)["assistant"]
        self.assertEqual(summary["catalogue"]["couverture"], 0.333)
        self.assertEqual(summary["catalogue"]["precision"], 0.5)
        self.assertEqual(summary["catalogue"]["hallucinations_affichees"], 1)
        self.assertEqual(summary["catalogue"]["latence_moyenne_s"], 2.0)
        self.assertEqual(summary["total"]["abstentions_correctes"], 1.0)
        self.assertIn("| catalogue | 3 | 0.333 | 0.5 |", to_markdown({"assistant": summary}))


@unittest.skipUnless(os.environ.get("NEO4J_PASSWORD"),
                     "Set NEO4J_PASSWORD to run the coverage evaluation on local Neo4j.")
class CoverageFixtureTests(unittest.TestCase):
    def test_reference_and_out_of_scope_cases_on_fixture_graph(self) -> None:
        from neo4j import GraphDatabase

        from marchegraph.evaluation.coverage import evaluate
        from marchegraph.evaluation.run import scoped_fixture_graph
        from marchegraph.graph.dimension_values import load_suggestions
        from marchegraph.graph.entity_search import create_search_indexes
        from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        validate_local_neo4j_uri(uri)
        auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
            database=os.environ.get("NEO4J_DATABASE", "neo4j")
        ) as session, scoped_fixture_graph(session) as source_path:
            create_search_indexes(session)
            cases = build_cases(load_suggestions(session))
            records = evaluate(session, source_path, cases, None, False)
        labels = {(r["catégorie"], r["assistant"]["label"]) for r in records}
        self.assertNotIn(("référence", "différent"), labels)
        self.assertNotIn(("référence", "abstention à tort"), labels)
        self.assertNotIn(("hors périmètre", "réponse au lieu d'abstention"), labels)
        entity = {r["question"]: r["assistant"]["label"] for r in records
                  if r["catégorie"] == "entité citée"}
        self.assertEqual(sorted(entity.values()),
                         ["abstention correcte", "abstention correcte", "correct", "correct"])


if __name__ == "__main__":
    unittest.main()
