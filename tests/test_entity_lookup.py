from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_formulation import BUYERS, FakeModel

from marchegraph.queries import assistant
from marchegraph.queries.entity_lookup import (
    Candidate,
    Resolution,
    decide,
    lucene_query,
    tokens,
)
from marchegraph.queries.interpretation import interpret


def candidate(identifier, name, score, markets=3):
    return Candidate("acheteur", identifier, (name,), score, markets)


class LookupTests(unittest.TestCase):
    def test_tokens_drop_accents_case_and_stopwords(self) -> None:
        self.assertEqual(tokens("Ville de Rennes"), ["ville", "rennes"])
        self.assertEqual(tokens("CENTRE HOSPITALIER D'ÉPINAL"),
                         ["centre", "hospitalier", "epinal"])

    def test_lucene_query_is_escaped_and_fuzzy_on_long_words(self) -> None:
        self.assertEqual(lucene_query("Ville de Rennes"), "ville~1 AND rennes~1")
        hostile = 'x") OR *:* //'
        query = lucene_query(hostile)
        self.assertNotIn("*", query)
        self.assertNotIn('"', query)
        self.assertNotIn("OR", query)
        self.assertIsNone(lucene_query("de la"))

    def test_decisions(self) -> None:
        self.assertEqual(decide("Rennes", []).status, "not_found")
        exact = decide("Ville de Rennes", [
            candidate("1", "RENNES METROPOLE", 3.0),
            candidate("2", "VILLE DE RENNES", 2.9),
        ])
        self.assertEqual((exact.status, exact.chosen.identifier), ("resolved", "2"))
        dominant = decide("hopital brest", [
            candidate("1", "CHU DE BREST HOPITAL", 6.0),
            candidate("2", "BREST METROPOLE", 2.0),
        ])
        self.assertEqual((dominant.status, dominant.chosen.identifier), ("resolved", "1"))
        ambiguous = decide("Rennes", [candidate(str(i), f"RENNES {i}", 2.0)
                                       for i in range(8)])
        self.assertEqual(ambiguous.status, "choose")
        self.assertEqual(len(ambiguous.options), 5)


class BuyerNameRecognitionTests(unittest.TestCase):
    def test_buyer_name_after_chez(self) -> None:
        result = interpret("Quels titulaires reviennent le plus chez la Ville de Rennes "
                           "en 2024 ?")
        self.assertEqual(result.question_id, 2)
        self.assertEqual(dict(result.params), {"buyer_name": "Ville de Rennes",
                                               "year": 2024})
        region_in_name = interpret("Quels titulaires reviennent chez la Région Bretagne ?")
        self.assertEqual(region_in_name.params["buyer_name"], "Région Bretagne")

    def test_generic_or_ambiguous_mentions_abstain(self) -> None:
        for question in (
            "Quels titulaires reviennent le plus chez un acheteur donné ?",
            "Quels titulaires en Bretagne reviennent chez la Ville de Rennes ?",
            "Quels titulaires reviennent chez ?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(interpret(question))

    def test_siret_still_wins(self) -> None:
        result = interpret("Quels titulaires reviennent le plus chez l'acheteur "
                           "12345678901234 ?")
        self.assertEqual(dict(result.params), {"buyer_id": "12345678901234",
                                               "year": 2025})


class AssistantResolutionTests(unittest.TestCase):
    question = "Quels titulaires reviennent le plus chez la Ville de Rennes ?"

    def test_resolved_name_runs_the_query_with_the_exact_identifier(self) -> None:
        chosen = candidate("21350238800019", "VILLE DE RENNES", 5.0)
        with mock.patch.object(assistant, "_resolve",
                               return_value=Resolution("resolved", chosen=chosen)), \
                mock.patch.object(assistant.dispatch, "run", return_value=BUYERS) as run:
            result = assistant.answer(self.question, object(), None)
        params = dict(run.call_args.args[1].params)
        self.assertEqual(params, {"buyer_id": "21350238800019", "year": 2025})
        self.assertIsInstance(result, assistant.AssistantAnswer)

    def test_ambiguous_or_missing_name_asks_or_abstains_without_querying(self) -> None:
        options = (candidate("1", "RENNES METROPOLE", 2.0),
                   candidate("2", "VILLE DE RENNES", 2.0))
        for resolution, expected in ((Resolution("choose", options=options), 2),
                                     (Resolution("not_found"), 0)):
            with self.subTest(status=resolution.status), \
                    mock.patch.object(assistant, "_resolve", return_value=resolution), \
                    mock.patch.object(assistant.dispatch, "run") as run:
                result = assistant.answer(self.question, object(), FakeModel("x"))
                self.assertIsInstance(result, assistant.EntityChoice)
                self.assertEqual(len(result.options), expected)
                run.assert_not_called()

    def test_user_choice_skips_the_search(self) -> None:
        with mock.patch.object(assistant, "_resolve") as resolve, \
                mock.patch.object(assistant.dispatch, "run", return_value=BUYERS) as run:
            assistant.answer(self.question, object(), None, buyer_id="2")
        resolve.assert_not_called()
        self.assertEqual(run.call_args.args[1].params["buyer_id"], "2")


@unittest.skipUnless(os.environ.get("NEO4J_PASSWORD"),
                     "Set NEO4J_PASSWORD to run the full-text search on local Neo4j.")
class FullTextFixtureTests(unittest.TestCase):
    def test_search_on_fixture_graph(self) -> None:
        from neo4j import GraphDatabase

        from marchegraph.evaluation import dataset
        from marchegraph.evaluation.run import scoped_fixture_graph
        from marchegraph.graph.entity_search import (
            create_search_indexes,
            resolve,
            search,
            search_indexes_online,
        )
        from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        validate_local_neo4j_uri(uri)
        auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
            database=os.environ.get("NEO4J_DATABASE", "neo4j")
        ) as session, scoped_fixture_graph(session):
            create_search_indexes(session)
            self.assertTrue(search_indexes_online(session))
            exact = resolve(session, "acheteur", "Acheteur 2024")
            self.assertEqual((exact.status, exact.chosen.identifier),
                             ("resolved", dataset.BUYER_2024))
            self.assertGreaterEqual(len(search(session, "acheteur", "acheteur")), 3)
            exact_name = resolve(session, "acheteur", "Acheteur A")
            self.assertEqual((exact_name.status, exact_name.chosen.identifier),
                             ("resolved", dataset.BUYER_A))
            accent = resolve(session, "titulaire", "alpha sas")
            self.assertEqual((accent.status, accent.chosen.identifier),
                             ("resolved", f"SIRET:{dataset.HOLDER}"))
            self.assertEqual(resolve(session, "acheteur", "Zorglub").status, "not_found")


if __name__ == "__main__":
    unittest.main()
