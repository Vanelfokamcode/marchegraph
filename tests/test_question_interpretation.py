from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.queries.dispatch import QUERY_FUNCTIONS
from marchegraph.queries.interpretation import LABELS, interpret


RECOGNIZED = [
    ("Quels acheteurs ont attribué le plus de marchés en 2025 ?", 1, {"year": 2025}),
    ("Classement des acheteurs par nombre de marchés en 2024", 1, {"year": 2024}),
    (
        "Quels titulaires reviennent le plus chez l'acheteur 12345678901234 ?",
        2,
        {"buyer_id": "12345678901234", "year": 2025},
    ),
    (
        "Quelles entreprises reviennent chez l’acheteur 00012345678901 en 2024 ?",
        2,
        {"buyer_id": "00012345678901", "year": 2024},
    ),
    ("Quel montant total est attribué par famille de codes CPV ?", 3, {"year": 2025}),
    ("Quels marchés ont été modifiés après attribution, et combien de fois ?", 4,
     {"year": 2025}),
    ("Quels avenants en 2024 ?", 4, {"year": 2024}),
    ("Quelles procédures sont utilisées selon la nature du marché ?", 5,
     {"year": 2025}),
    ("Quels titulaires travaillent avec plusieurs acheteurs différents ?", 6,
     {"year": 2025}),
    (
        "Quels marchés concernent la voirie dans la région 84 ?",
        7,
        {"theme": "voirie", "region_code": "84", "year": 2025},
    ),
    (
        "Quels marchés sur le thème de la restauration scolaire en Île-de-France en 2024 ?",
        7,
        {"theme": "restauration scolaire", "region_code": "11", "year": 2024},
    ),
    (
        "Marchés portant sur l'éclairage public attribués en Provence-Alpes-Côte d’Azur",
        7,
        {"theme": "éclairage public", "region_code": "93", "year": 2025},
    ),
    ("Quelle est la durée moyenne des marchés par famille CPV ?", 8, {"year": 2025}),
    ("Quels fournisseurs apparaissent sous plusieurs écritures de leur nom ?", 9, {}),
    ("Quels marchés ont des données manquantes ou incohérentes ?", 10, {}),
    ("Quel montant et quelle durée par famille CPV ?", (3, 8), {"year": 2025}),
]

ABSTAIN = [
    "Quelle est la météo à Paris ?",
    "Bonjour",
    "",
    "Quels marchés ont été modifiés en 2031 ?",
    "Quels acheteurs ont attribué le plus de marchés entre 2024 et 2025 ?",
    "Quels titulaires reviennent le plus chez un acheteur donné ?",
    "Quels acheteurs ont attribué le plus de marchés en Bretagne ?",
    "Quels marchés dans la région 84 ?",
    "Quels marchés concernent la voirie dans la région 99 ?",
    "Quels marchés concernent la voirie en Bretagne et en Normandie ?",
    "Quelles données sont manquantes en 2025 ?",
    "Quels fournisseurs ont plusieurs écritures de leur nom en 2024 ?",
    "Quelles familles CPV ?",
    "Qui va gagner le prochain marché public ?",
]


class InterpretationTests(unittest.TestCase):
    def test_reference_questions_are_recognized_with_parameters(self) -> None:
        for question, question_id, params in RECOGNIZED:
            with self.subTest(question=question):
                result = interpret(question)
                self.assertIsNotNone(result)
                self.assertEqual(result.question_id, question_id)
                self.assertEqual(dict(result.params), params)
                self.assertEqual(result.label, LABELS[question_id])

    def test_out_of_scope_questions_abstain(self) -> None:
        for question in ABSTAIN:
            with self.subTest(question=question):
                self.assertIsNone(interpret(question))

    def test_all_ten_questions_are_covered(self) -> None:
        covered = {question_id for _, question_id, _ in RECOGNIZED}
        self.assertTrue(set(range(1, 11)) <= covered)

    def test_parameters_bind_to_the_prepared_query(self) -> None:
        for question, question_id, _ in RECOGNIZED:
            with self.subTest(question=question):
                function = QUERY_FUNCTIONS[question_id]
                inspect.signature(function).bind(
                    object(), **interpret(question).params
                )


if __name__ == "__main__":
    unittest.main()
