from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb

ENTITY_RESOLUTION_DIR = (
    Path(__file__).resolve().parents[1] / "src/marchegraph/entity_resolution"
)
sys.path.insert(0, str(ENTITY_RESOLUTION_DIR))
import evaluation

prepare_spec = importlib.util.spec_from_file_location(
    "holder_identity_prepare_for_review", ENTITY_RESOLUTION_DIR / "prepare.py"
)
assert prepare_spec is not None and prepare_spec.loader is not None
identity_prepare = importlib.util.module_from_spec(prepare_spec)
sys.modules[prepare_spec.name] = identity_prepare
prepare_spec.loader.exec_module(identity_prepare)

evaluate_spec = importlib.util.spec_from_file_location(
    "holder_identity_evaluate", ENTITY_RESOLUTION_DIR / "evaluate.py"
)
assert evaluate_spec is not None and evaluate_spec.loader is not None
evaluate = importlib.util.module_from_spec(evaluate_spec)
sys.modules[evaluate_spec.name] = evaluate
evaluate_spec.loader.exec_module(evaluate)


class SamplingTests(unittest.TestCase):
    def test_selects_reproducible_equal_year_samples(self) -> None:
        candidates = {
            year: [(f"SIRET-{index % 2}", f"{year}-{index:03}", index + 1) for index in range(60)]
            for year in (2024, 2025)
        }

        first = evaluation.select_groups(candidates)
        second = evaluation.select_groups(candidates)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 100)
        self.assertEqual(
            {year: sum(row["year"] == year for row in first) for year in (2024, 2025)},
            {2024: 50, 2025: 50},
        )

    def test_insufficient_groups_fails_instead_of_sampling_smaller(self) -> None:
        with self.assertRaisesRegex(evaluation.EvaluationError, "50 requis"):
            evaluation.select_groups({2024: [], 2025: []})


class ReviewPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "decp.parquet"
        self.identities_dir = self.root / "identities"
        self.review_dir = self.root / "review"
        connection = duckdb.connect()
        connection.execute(
            """
            CREATE TABLE source_data (
                dateNotification DATE,
                modification_id INTEGER,
                titulaire_typeIdentifiant VARCHAR,
                titulaire_id VARCHAR,
                titulaire_nom VARCHAR
            )
            """
        )
        rows = []
        for year in (2024, 2025):
            for index in range(55):
                identifier = f"{year}-{index:03}"
                rows.extend(
                    [
                        (
                            date(year, 1, 1),
                            0,
                            "siret",
                            identifier,
                            f"Supplier {index:03}",
                        ),
                        (
                            date(year, 1, 2),
                            0,
                            " SIRET ",
                            f" {identifier} ",
                            f"supplier {index:03}",
                        ),
                    ]
                )
            rows.extend(
                [
                    (date(year, 2, 1), 0, None, f"missing-type-{year}", "Unknown"),
                    (date(year, 2, 2), 0, "SIRET", None, "Unknown"),
                ]
            )
        connection.executemany("INSERT INTO source_data VALUES (?, ?, ?, ?, ?)", rows)
        connection.execute(
            "COPY source_data TO ? (FORMAT PARQUET)", [str(self.source)]
        )
        connection.close()
        identity_prepare.prepare(self.source, self.identities_dir)
        self.identity_path = self.identities_dir / "holder-identities.parquet"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_creates_review_files_and_reports_labels_without_overwriting_them(self) -> None:
        sample_path, variants_path, report_path, pending = evaluate.prepare_review(
            self.source, self.identity_path, self.review_dir
        )

        self.assertEqual(pending, 100)
        with sample_path.open(newline="", encoding="utf-8") as sample_file:
            sample_rows = list(csv.DictReader(sample_file))
        self.assertEqual(len(sample_rows), 100)
        self.assertEqual(
            {year: sum(int(row["year"]) == year for row in sample_rows) for year in (2024, 2025)},
            {2024: 50, 2025: 50},
        )
        self.assertTrue(all(int(row["distinct_name_count"]) == 2 for row in sample_rows))
        with variants_path.open(newline="", encoding="utf-8") as variant_file:
            self.assertEqual(sum(1 for _ in csv.DictReader(variant_file)), 200)
        self.assertIn("| **Total** | 100 | 0 | 0 | 0 | 0 | 100 | 0 | n/a |", report_path.read_text())
        self.assertIn("provisoires", report_path.read_text())

        with sample_path.open(newline="", encoding="utf-8") as sample_file:
            sample_rows = list(csv.DictReader(sample_file))
        for year in (2024, 2025):
            year_rows = [row for row in sample_rows if int(row["year"]) == year]
            year_rows[0]["manual_review_label"] = "correct"
            year_rows[1]["manual_review_label"] = "incorrect"
            year_rows[2]["manual_review_label"] = "indeterminate"
        with sample_path.open("w", newline="", encoding="utf-8") as sample_file:
            writer = csv.DictWriter(sample_file, fieldnames=evaluate.SAMPLE_FIELDS)
            writer.writeheader()
            writer.writerows(sample_rows)

        _, _, report_path, pending = evaluate.prepare_review(
            self.source, self.identity_path, self.review_dir
        )

        self.assertEqual(pending, 94)
        report = report_path.read_text()
        self.assertIn("| 2024 | 50 | 3 | 1 | 1 | 1 | 47 | 2 | 50,00 % |", report)
        self.assertIn("| 2025 | 50 | 3 | 1 | 1 | 1 | 47 | 2 | 50,00 % |", report)

    def test_rejects_an_invalid_manual_label(self) -> None:
        sample_path, _, _, _ = evaluate.prepare_review(
            self.source, self.identity_path, self.review_dir
        )
        with sample_path.open(newline="", encoding="utf-8") as sample_file:
            sample_rows = list(csv.DictReader(sample_file))
        sample_rows[0]["manual_review_label"] = "maybe"
        with sample_path.open("w", newline="", encoding="utf-8") as sample_file:
            writer = csv.DictWriter(sample_file, fieldnames=evaluate.SAMPLE_FIELDS)
            writer.writeheader()
            writer.writerows(sample_rows)

        with self.assertRaisesRegex(evaluate.ReviewError, "Label invalide"):
            evaluate.prepare_review(self.source, self.identity_path, self.review_dir)

    def test_new_output_directory_uses_same_deterministic_sample(self) -> None:
        sample_a, _, _, _ = evaluate.prepare_review(
            self.source, self.identity_path, self.root / "review-a"
        )
        sample_b, _, _, _ = evaluate.prepare_review(
            self.source, self.identity_path, self.root / "review-b"
        )
        self.assertEqual(sample_a.read_bytes(), sample_b.read_bytes())


if __name__ == "__main__":
    unittest.main()
