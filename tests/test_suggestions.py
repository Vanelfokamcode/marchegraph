from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph import dimension_values as dv
from marchegraph.queries.catalogue import CatalogueRefusal
from marchegraph.queries.interpretation import interpret
from marchegraph.queries.suggestions import (
    Suggestions,
    Value,
    describe,
    examples,
    guided_query,
)


class FakeSession:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.calls = []

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return self.results_by_query[query]


def suggestions(year=2025, region=("53", "Bretagne"), buyer="21350238800019"):
    return Suggestions(
        year,
        years=(Value(str(year), str(year), 10),),
        regions=(Value(region[0], region[1], 7),),
        cpv_families=(Value("452", "CPV 452", 5),),
        procedures=(Value("Appel d'offres ouvert", "Appel d'offres ouvert", 4),),
        natures=(Value("Marché", "Marché", 9),),
        buyers=(Value(buyer, f"VILLE ({buyer})", 3),),
    )


class ExampleTests(unittest.TestCase):
    def test_every_example_is_recognized(self) -> None:
        for s in (suggestions(), suggestions(2024, ("11", "Île-de-France")),
                  suggestions(region=("04", "La Réunion")),
                  suggestions(region=("93", "Provence-Alpes-Côte d'Azur"))):
            for question in examples(s):
                with self.subTest(question=question):
                    self.assertIsNotNone(interpret(question))

    def test_examples_follow_the_graph_content(self) -> None:
        first = examples(suggestions())
        other = examples(suggestions(2024, ("11", "Île-de-France"), "21750001600019"))
        self.assertNotEqual(first, other)
        q2 = interpret(next(q for q in other if "chez" in q))
        self.assertEqual(dict(q2.params), {"buyer_id": "21750001600019", "year": 2024})
        q7 = interpret(next(q for q in other if "concernent" in q))
        self.assertEqual(dict(q7.params),
                         {"theme": "travaux", "region_code": "11", "year": 2024})

    def test_buyers_without_siret_are_not_used_as_examples(self) -> None:
        self.assertFalse(any("chez" in q for q in examples(suggestions(buyer="buyer-x"))))


class GuidedQueryTests(unittest.TestCase):
    def test_offered_values_build_a_valid_catalogue_query(self) -> None:
        s = suggestions()
        query = guided_query(s, measure="montant_total", grouping="famille_cpv",
                             year=2025, region_code="53", procedure="Appel d'offres ouvert")
        self.assertEqual((query.region_code, query.year_given), ("53", True))
        self.assertEqual(describe(query, s),
                         "Montant total déclaré par famille cpv "
                         "(2025, Bretagne, Appel d'offres ouvert)")

    def test_values_outside_the_lists_are_refused(self) -> None:
        s = suggestions()
        for filters in ({"year": 2019}, {"year": 2025, "region_code": "11"},
                        {"year": 2025, "buyer_id": "x' OR 1=1"},
                        {"year": 2025, "nature": "Inventée"}):
            with self.subTest(filters=filters), self.assertRaises(CatalogueRefusal):
                guided_query(s, measure="nombre_marches", grouping="aucun", **filters)

    def test_catalogue_rules_still_apply(self) -> None:
        with self.assertRaises(CatalogueRefusal):
            guided_query(suggestions(), measure="nombre_modifications",
                         grouping="titulaire", year=2025)


class LoadSuggestionsTests(unittest.TestCase):
    def test_values_are_read_ranked_and_filtered(self) -> None:
        session = FakeSession({
            dv.YEARS_QUERY: [{"value": "2025", "market_count": 3},
                             {"value": "2024", "market_count": 2},
                             {"value": "2019", "market_count": 1}],
            dv.REGIONS_QUERY: [{"value": "53", "market_count": 2},
                               {"value": "99", "market_count": 1}],
            dv.CPV_FAMILIES_QUERY: [{"value": "452", "market_count": 2},
                                    {"value": "4x", "market_count": 1}],
            dv.PROCEDURES_QUERY: [{"value": "Ouvert", "market_count": 2},
                                  {"value": " ", "market_count": 1}],
            dv.NATURES_QUERY: [{"value": "Marché", "market_count": 3}],
            dv.BUYERS_QUERY: [{"value": "21350238800019", "name": "VILLE",
                               "market_count": 2}],
        })
        s = dv.load_suggestions(session)
        self.assertEqual(s.year, 2025)
        self.assertEqual([v.value for v in s.years], ["2025", "2024"])
        self.assertEqual([(v.value, v.label) for v in s.regions], [("53", "Bretagne")])
        self.assertEqual([v.value for v in s.cpv_families], ["452"])
        self.assertEqual([v.value for v in s.procedures], ["Ouvert"])
        self.assertEqual(s.buyers[0].label, "VILLE (21350238800019)")
        buyer_call = next(p for q, p in session.calls if q == dv.BUYERS_QUERY)
        self.assertEqual(buyer_call["year"], 2025)


@unittest.skipUnless(os.environ.get("NEO4J_PASSWORD"),
                     "Set NEO4J_PASSWORD to read suggestions from local Neo4j.")
class SuggestionsFixtureTests(unittest.TestCase):
    def test_examples_and_guided_queries_on_fixture_graph(self) -> None:
        from neo4j import GraphDatabase

        from marchegraph.evaluation import dataset
        from marchegraph.evaluation.run import scoped_fixture_graph
        from marchegraph.graph.neo4j_config import validate_local_neo4j_uri
        from marchegraph.queries import assistant

        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        validate_local_neo4j_uri(uri)
        auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
            database=os.environ.get("NEO4J_DATABASE", "neo4j")
        ) as session, scoped_fixture_graph(session):
            s = dv.load_suggestions(session)
            self.assertEqual(s.year, 2025)
            self.assertEqual(s.regions[0].value, "11")
            self.assertEqual(s.buyers[0].value, dataset.BUYER_A)
            for question in examples(s)[:4]:
                with self.subTest(question=question):
                    result = assistant.answer(question, session, None)
                    self.assertIsInstance(result, assistant.AssistantAnswer)
                    self.assertTrue(result.response.rows)
                    self.assertTrue(result.response.rows[0].evidence)
            query = guided_query(s, measure="nombre_marches", grouping="acheteur",
                                 year=2025, region_code=s.regions[0].value)
            guided = assistant.answer_guided(query, describe(query, s), session, None)
            self.assertTrue(guided.response.rows)
            self.assertTrue(guided.response.rows[0].evidence)


if __name__ == "__main__":
    unittest.main()
