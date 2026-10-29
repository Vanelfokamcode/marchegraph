from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.evaluation import dataset, scoring, sql_baseline
from marchegraph.queries.interpretation import interpret


class DatasetTests(unittest.TestCase):
    def test_reference_questions_are_recognized_as_expected(self) -> None:
        self.assertEqual({q.question_id for q in dataset.REFERENCE_QUESTIONS},
                         set(range(1, 11)))
        for item in dataset.REFERENCE_QUESTIONS:
            with self.subTest(question=item.question):
                result = interpret(item.question)
                self.assertEqual(result.question_id, item.question_id)
                self.assertEqual(dict(result.params), item.params)

    def test_abstention_questions_are_not_recognized(self) -> None:
        self.assertEqual(len(dataset.ABSTENTION_QUESTIONS), 10)
        for question in dataset.ABSTENTION_QUESTIONS:
            with self.subTest(question=question):
                self.assertIsNone(interpret(question))


class SqlBaselineTests(unittest.TestCase):
    def test_every_question_runs_on_the_fixture_parquet(self) -> None:
        with TemporaryDirectory() as directory:
            source, _ = dataset.write_fixtures(Path(directory))
            results = {
                item.question_id: sql_baseline.run(source, item.question_id, item.params)
                for item in dataset.REFERENCE_QUESTIONS
            }
        self.assertEqual(results[1], [(dataset.BUYER_A, 1), (dataset.BUYER_B, 1)])
        self.assertEqual(results[2], [(dataset.HOLDER, 1)])
        self.assertEqual(results[4], [(2, 2)])
        self.assertEqual(results[6], [(dataset.HOLDER, 2)])
        self.assertEqual(results[7], [("eval-market-a",)])
        self.assertEqual(results[9], [(dataset.HOLDER, 2)])
        self.assertTrue(all(results[question_id] for question_id in range(1, 11)))


class ScoringTests(unittest.TestCase):
    reference = [("21000000000011", Decimal(1)), ("21000000000022", Decimal(1))]

    def test_structured_scores(self) -> None:
        facts = scoring.normalize_facts([("21000000000022", 1), ("21000000000011", 1)])
        self.assertEqual(scoring.score_structured(facts, self.reference).label, "correct")
        other = scoring.normalize_facts([("21000000000011", 2)])
        score = scoring.score_structured(other, self.reference)
        self.assertEqual(score.label, "différent")
        self.assertTrue(score.invented and score.missing)
        self.assertEqual(scoring.score_structured(None, self.reference).label,
                         "abstention à tort")

    def test_text_scores(self) -> None:
        question = "Quels acheteurs ont attribué le plus de marchés en 2025 ?"
        self.assertEqual(
            scoring.score_text("L'acheteur A et l'acheteur B ont 1 marché chacun.",
                               question, self.reference).label,
            "correct",
        )
        self.assertEqual(
            scoring.score_text("La Ville de Paris a attribué 2485 marchés.",
                               question, self.reference).label,
            "hallucination",
        )
        self.assertEqual(
            scoring.score_text("Je ne dispose pas de ces données.", question,
                               self.reference).label,
            "abstention à tort",
        )
        self.assertEqual(
            scoring.score_text("Je ne peux pas prédire la météo.",
                               "Quelle est la météo ?", None).label,
            "abstention correcte",
        )
        self.assertEqual(
            scoring.score_text("Il fera 18 degrés.", "Quelle est la météo ?", None).label,
            "réponse au lieu d'abstention",
        )

    def test_decimal_values_are_compared_to_the_cent(self) -> None:
        self.assertEqual(
            scoring.normalize_facts([("452", 37.269565)]),
            scoring.normalize_facts([("452", Decimal("37.2695652173913"))]),
        )


if __name__ == "__main__":
    unittest.main()
