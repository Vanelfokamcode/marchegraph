from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/marchegraph/data"))
import prepare


class PrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source.parquet"
        self.output = self.root / "prepared"
        connection = duckdb.connect()
        connection.execute(
            """
            COPY (
                SELECT * FROM (
                    VALUES
                        (DATE '2024-02-01', 0, 'a', 'buyer-a', NULL, 10.0, 'cpv-a', 'objet-a', 'loc-a', 'reg-a', 3, 'suspect', DATE '2024-02-02', 'initial'),
                        (DATE '2024-02-02', 0, 'b', NULL, 'holder-b', NULL, NULL, NULL, 'loc-b', 'reg-b', NULL, 'aberrant', DATE '2024-02-01', 'initial'),
                        (DATE '2024-02-03', 0, 'c', 'buyer-c', 'holder-c', 30.0, 'cpv-c', 'objet-c', 'loc-c', 'reg-c', 2, NULL, NULL, 'initial'),
                        (DATE '2024-02-04', 2, 'a', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'modification'),
                        (DATE '2025-03-01', 0, 'd', 'buyer-d', 'holder-d', 40.0, 'cpv-d', 'objet-d', 'loc-d', 'reg-d', 1, NULL, DATE '2025-03-01', 'initial'),
                        (DATE '2025-03-02', 1, 'd', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'modification'),
                        (DATE '2023-12-31', 0, 'old', 'buyer-old', 'holder-old', 50.0, 'cpv-old', 'objet-old', 'loc-old', 'reg-old', 1, NULL, DATE '2023-12-31', 'outside')
                ) AS records(dateNotification, modification_id, uid, acheteur_id, titulaire_id, montant, codeCPV, objet, lieuExecution_code, acheteur_region_code, offresRecues, montant_anomalie, datePublicationDonnees, payload)
            )
            TO ? (FORMAT PARQUET)
            """,
            [str(self.source)],
        )
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_prepare_preserves_2024_2025_rows_and_separate_categories(self) -> None:
        counts = prepare.prepare(self.source, self.output, verify_baseline=False)

        self.assertEqual(
            counts,
            {
                2024: {
                    "initial_award_rows": 3,
                    "initial_award_distinct_uids": 3,
                    "modification_rows": 1,
                    "modification_distinct_uids": 1,
                },
                2025: {
                    "initial_award_rows": 1,
                    "initial_award_distinct_uids": 1,
                    "modification_rows": 1,
                    "modification_distinct_uids": 1,
                },
            },
        )
        connection = duckdb.connect()
        rows = connection.execute(
            "SELECT dateNotification, modification_id, uid, payload "
            "FROM read_parquet(?) ORDER BY dateNotification",
            [str(self.output / "decp.parquet")],
        ).fetchall()
        columns = [
            row[0]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)",
                [str(self.output / "decp.parquet")],
            ).fetchall()
        ]
        connection.close()
        self.assertEqual(
            columns,
            [
                "dateNotification",
                "modification_id",
                "uid",
                "acheteur_id",
                "titulaire_id",
                "montant",
                "codeCPV",
                "objet",
                "lieuExecution_code",
                "acheteur_region_code",
                "offresRecues",
                "montant_anomalie",
                "datePublicationDonnees",
                "payload",
            ],
        )
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(row[1] > 0 for row in rows), 2)

    def test_manifest_records_source_identity_and_extraction_unknown(self) -> None:
        self.output.mkdir()
        sentinel = self.output / "unrelated.txt"
        sentinel.write_text("keep")

        prepare.prepare(self.source, self.output, verify_baseline=False)

        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["source"]["sha256"], prepare.sha256_file(self.source))
        self.assertEqual(manifest["source"]["size_bytes"], self.source.stat().st_size)
        self.assertIsNone(manifest["source"]["extraction_date"])
        self.assertEqual(
            set(path.name for path in self.output.iterdir()),
            set(prepare.OUTPUT_FILENAMES) | {"unrelated.txt"},
        )
        self.assertEqual(sentinel.read_text(), "keep")
        report = (self.output / "quality-report.md").read_text()
        self.assertIn("| 2024 | Attribution initiale | 3 | 3 |", report)
        self.assertIn("| 2025 | Modification | 1 | 1 |", report)
        missing_section = report.split("## Valeurs manquantes\n", 1)[1].split(
            "## Anomalies de montant\n", 1
        )[0]
        missing_2024 = {
            "acheteur_id": 1,
            "titulaire_id": 1,
            "montant": 1,
            "codeCPV": 1,
            "objet": 1,
            "lieuExecution_code": 0,
            "acheteur_region_code": 0,
            "offresRecues": 1,
        }
        for field, missing in missing_2024.items():
            rate = "0,00 %" if missing == 0 else "33,33 %"
            self.assertIn(
                f"| 2024 | `{field}` | {missing} | 3 | {rate} |",
                missing_section,
            )
            self.assertIn(f"| 2025 | `{field}` | 0 | 1 | 0,00 % |", missing_section)
        self.assertIn("| 2024 | aberrant | 1 | 3 | 33,33 % |", report)
        self.assertIn("| 2024 | suspect | 1 | 3 | 33,33 % |", report)
        amount_section = report.split("## Anomalies de montant\n", 1)[1].split(
            "## Délais de publication\n", 1
        )[0]
        self.assertIn("| 2024 | NULL | 1 | 3 | 33,33 % |", amount_section)
        delay_section = report.split("## Délais de publication\n", 1)[1]
        self.assertIn(
            "| 2024 | 1 | 2 | 1 | 50,00 % | -0,8 | 0 | 0,8 | 0,98 |",
            delay_section,
        )
        self.assertIn("| 2025 | 0 | 1 | 0 | 0,00 % |", report)

    def test_missing_source_fails_without_success_outputs(self) -> None:
        with self.assertRaisesRegex(prepare.PipelineError, "absent ou illisible"):
            prepare.prepare(self.root / "missing.parquet", self.output)

        self.assertFalse(self.output.exists())

    def test_unknown_snapshot_fails_baseline_validation_without_replacing_outputs(self) -> None:
        self.output.mkdir()
        sentinel = self.output / "existing.txt"
        sentinel.write_text("unchanged")

        with self.assertRaisesRegex(prepare.PipelineError, "SHA-256"):
            prepare.prepare(self.source, self.output)

        self.assertEqual(sentinel.read_text(), "unchanged")
        self.assertEqual(list(self.output.iterdir()), [sentinel])

    def test_unusable_output_path_fails_explicitly(self) -> None:
        output_file = self.root / "not-a-directory"
        output_file.write_text("keep")

        with self.assertRaisesRegex(prepare.PipelineError, "Écriture des sorties"):
            prepare.prepare(self.source, output_file, verify_baseline=False)

        self.assertEqual(output_file.read_text(), "keep")

    def test_small_positive_percentage_is_not_rounded_to_zero(self) -> None:
        self.assertEqual(prepare._format_percent(1, 100_000), "<0,01 %")
        self.assertEqual(prepare._format_percent(1, 10_000), "0,01 %")


if __name__ == "__main__":
    unittest.main()
