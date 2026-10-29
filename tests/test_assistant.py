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
from marchegraph.queries.interpretation import interpret
from marchegraph.queries.local_model import LocalModelURLError


class AssistantTests(unittest.TestCase):
    def test_examples_cover_the_ten_questions(self) -> None:
        ids = set()
        for example in assistant.EXAMPLES:
            result = interpret(example)
            self.assertIsNotNone(result, example)
            ids.add(result.question_id)
        self.assertEqual(ids, set(range(1, 11)))

    def test_off_topic_question_abstains_without_querying(self) -> None:
        with mock.patch.object(assistant.dispatch, "run") as run:
            self.assertIsNone(assistant.answer("Quelle est la météo à Paris ?",
                                               object(), FakeModel("x")))
        run.assert_not_called()

    def test_answer_keeps_query_evidence_and_controls_wording(self) -> None:
        session = object()
        question = "Quels acheteurs ont attribué le plus de marchés en 2025 ?"
        with mock.patch.object(assistant.dispatch, "run", return_value=BUYERS) as run:
            faithful = assistant.answer(
                question, session, FakeModel("Acheteur Alpha a attribué 1234 marchés.")
            )
            invented = assistant.answer(
                question, session, FakeModel("Acheteur Alpha a attribué 4000 marchés.")
            )
        run.assert_called_with(session, interpret(question))
        self.assertIs(faithful.response, BUYERS)
        self.assertEqual(faithful.formulation.source, "modele")
        self.assertIs(invented.response, BUYERS)
        self.assertEqual(invented.formulation.source, "abstention")

    def test_model_configuration_is_optional_and_loopback_only(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(assistant.MODEL_ENV, None)
            self.assertIsNone(assistant.model_from_env())
        with mock.patch.dict(os.environ, {assistant.MODEL_ENV: "phi4-mini:3.8b"}):
            os.environ.pop(assistant.MODEL_URL_ENV, None)
            self.assertEqual(assistant.model_from_env().model, "phi4-mini:3.8b")
        with mock.patch.dict(os.environ, {assistant.MODEL_ENV: "phi4-mini:3.8b",
                                          assistant.MODEL_URL_ENV: "http://10.1.2.3:11434"}):
            with self.assertRaises(LocalModelURLError):
                assistant.model_from_env()


if __name__ == "__main__":
    unittest.main()
