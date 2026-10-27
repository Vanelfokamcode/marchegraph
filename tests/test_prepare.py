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
                        (DATE '2024-02-01', 0, 'a', 'initial'),
                        (DATE '2024-02-02', 2, 'a', 'modification'),
                        (DATE '2025-03-01', 0, 'b', 'initial'),
                        (DATE '2025-03-02', 1, 'b', 'modification'),
                        (DATE '2023-12-31', 0, 'old', 'outside')
                ) AS records(dateNotification, modification_id, uid, payload)
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
                    "initial_award_rows": 1,
                    "initial_award_distinct_uids": 1,
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
            columns, ["dateNotification", "modification_id", "uid", "payload"]
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[1][3], "modification")

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
        self.assertIn("| 2024 | Attribution initiale | 1 | 1 |", report)
        self.assertIn("| 2025 | Modification | 1 | 1 |", report)

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


if __name__ == "__main__":
    unittest.main()
