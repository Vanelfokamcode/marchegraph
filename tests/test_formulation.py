from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph.contracts import (
    BuyerRanking,
    EvidenceReference,
    MultiBuyerHolder,
    QueryResponse,
    QueryRow,
)
from marchegraph.queries.formulation import _plain, check, formulate, payload
from marchegraph.queries.local_model import LocalModelURLError, OllamaClient


EVIDENCE = (EvidenceReference("Marche", "uid-preuve-1", "acheteur", "00000000000011"),)

BUYERS = QueryResponse(
    question_id=1,
    rows=(
        QueryRow(BuyerRanking("00000000000011", ("Acheteur Alpha",), 1234), EVIDENCE),
        QueryRow(BuyerRanking("00000000000012", ("Acheteur Beta",), 987), EVIDENCE),
    ),
    limitations=("Le classement couvre tout le territoire national.",),
)

MULTI_BUYER = QueryResponse(
    question_id=6,
    rows=(
        QueryRow(
            MultiBuyerHolder("SIRET", "00000000000031", ("Titulaire Trois",),
                             ("00000000000011", "00000000000012"), 6),
            EVIDENCE,
        ),
    ),
)

EMPTY = QueryResponse(question_id=4, rows=())

QUESTION = "Quels acheteurs ont attribué le plus de marchés en 2025 ?"
LABEL = "Classement des acheteurs"


class FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.text


class FormulationTests(unittest.TestCase):
    def test_faithful_text_is_accepted(self) -> None:
        model = FakeModel(
            "Acheteur Alpha a attribué 1 234 marchés en 2025 et Acheteur Beta 987. "
            "Les deux acheteurs couvrent tout le territoire national."
        )
        result = formulate(QUESTION, LABEL, BUYERS, model)
        self.assertEqual(result.source, "modele")
        self.assertEqual(result.problems, ())

    def test_invented_digit_leads_to_abstention(self) -> None:
        result = formulate(QUESTION, LABEL, BUYERS,
                           FakeModel("Acheteur Alpha a attribué 1500 marchés."))
        self.assertEqual(result.source, "abstention")
        self.assertIsNone(result.text)
        self.assertIn("chiffre absent du résultat : 1500", result.problems)

    def test_wrong_number_word_leads_to_abstention(self) -> None:
        result = formulate(
            "Quels titulaires travaillent avec plusieurs acheteurs ?",
            "Titulaires multi-acheteurs",
            MULTI_BUYER,
            FakeModel("Titulaire Trois travaille avec trois acheteurs."),
        )
        self.assertEqual(result.source, "abstention")
        self.assertIn("nombre en lettres absent du résultat : trois", result.problems)

    def test_false_absence_leads_to_abstention(self) -> None:
        for text in ("Aucun résultat n'est disponible.",
                     "Aucun fournisseur n'a plusieurs écritures de son nom.",
                     "La liste des lignes est vide."):
            with self.subTest(text=text):
                result = formulate(QUESTION, LABEL, BUYERS, FakeModel(text))
                self.assertEqual(result.source, "abstention")
                self.assertIn(
                    "absence de résultat affirmée alors que des lignes existent",
                    result.problems,
                )

    def test_empty_or_failing_model_leads_to_abstention(self) -> None:
        self.assertEqual(
            formulate(QUESTION, LABEL, BUYERS, FakeModel("  ")).source, "abstention"
        )

        def failing(prompt: str) -> str:
            raise TimeoutError("délai dépassé")

        result = formulate(QUESTION, LABEL, BUYERS, failing)
        self.assertEqual(result.source, "abstention")
        self.assertTrue(result.problems[0].startswith("modèle indisponible"))

    def test_template_without_model_or_without_rows(self) -> None:
        model = FakeModel("ne doit pas être appelé")
        empty = formulate("Quels marchés ont été modifiés ?", "Historique", EMPTY, model)
        self.assertEqual(empty.source, "gabarit")
        self.assertIn("aucun résultat", empty.text)
        self.assertEqual(model.prompts, [])
        without_model = formulate(QUESTION, LABEL, BUYERS, None)
        self.assertEqual(without_model.source, "gabarit")
        self.assertIn("2 ligne(s)", without_model.text)

    def test_model_never_receives_evidence_and_evidence_is_unchanged(self) -> None:
        model = FakeModel("Acheteur Alpha a attribué 1234 marchés.")
        formulate(QUESTION, LABEL, BUYERS, model)
        self.assertNotIn("uid-preuve-1", model.prompts[0])
        self.assertNotIn("evidence", payload(BUYERS))
        self.assertEqual(BUYERS.rows[0].evidence, EVIDENCE)

    def test_check_accepts_decimal_comma_and_question_numbers(self) -> None:
        data = {"rows": [{"montant_total": str(Decimal("81234567.50"))}], "limites": []}
        self.assertEqual(
            check("En 2025, le total est de 81 234 567,50.", data, "Montant en 2025 ?"),
            (),
        )

    def test_json_or_code_output_leads_to_abstention(self) -> None:
        for text in ('```json\n{"marches": 1234}\n```', '{"marches": 1234}'):
            with self.subTest(text=text):
                result = formulate(QUESTION, LABEL, BUYERS, FakeModel(text))
                self.assertEqual(result.source, "abstention")
                self.assertEqual(result.problems,
                                 ("réponse non rédigée (JSON ou code)",))

    def test_model_receives_at_most_ten_rows_with_total(self) -> None:
        many = QueryResponse(
            question_id=1,
            rows=tuple(
                QueryRow(BuyerRanking(f"{i:014d}", (f"Acheteur {i}",), 100 + i), EVIDENCE)
                for i in range(25)
            ),
        )
        data = payload(many)
        self.assertEqual(len(data["rows"]), 10)
        self.assertEqual((data["lignes_fournies"], data["lignes_total"]), (10, 25))
        model = FakeModel("Voici les 10 premiers acheteurs sur 25.")
        self.assertEqual(formulate(QUESTION, LABEL, many, model).source, "modele")
        self.assertNotIn("Acheteur 24", model.prompts[0])

    def test_long_decimals_are_rounded_for_the_model(self) -> None:
        self.assertEqual(_plain(Decimal("37.26956521739130434782608696")), "37.27")
        self.assertEqual(_plain(Decimal("81234567.50")), "81234567.50")


class LocalModelTests(unittest.TestCase):
    def test_only_loopback_http_urls_are_accepted(self) -> None:
        for url in ("http://127.0.0.1:11434", "http://localhost:11434",
                    "http://[::1]:11434"):
            with self.subTest(url=url):
                OllamaClient("phi4-mini:3.8b", url)
        for url in ("http://10.0.0.5:11434", "https://api.example.com",
                    "http://0.0.0.0:11434", "ftp://127.0.0.1"):
            with self.subTest(url=url):
                with self.assertRaises(LocalModelURLError):
                    OllamaClient("phi4-mini:3.8b", url)


if __name__ == "__main__":
    unittest.main()
