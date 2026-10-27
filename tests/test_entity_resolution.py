from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "src/marchegraph/entity_resolution"),
)
import identity
prepare_spec = importlib.util.spec_from_file_location(
    "holder_identity_prepare",
    Path(__file__).resolve().parents[1]
    / "src/marchegraph/entity_resolution/prepare.py",
)
assert prepare_spec is not None and prepare_spec.loader is not None
prepare = importlib.util.module_from_spec(prepare_spec)
sys.modules[prepare_spec.name] = prepare
prepare_spec.loader.exec_module(prepare)


class IdentityTests(unittest.TestCase):
    def test_normalizes_type_and_outer_value_whitespace_only(self) -> None:
        self.assertEqual(
            identity.canonical_identity(" siret ", " 00123 "),
            ("SIRET", "00123"),
        )
        self.assertEqual(
            identity.canonical_identity(" tva ", " Ab- 01 "),
            ("TVA", "Ab- 01"),
        )

    def test_missing_values_are_unresolved_and_types_are_part_of_identity(self) -> None:
        self.assertIsNone(identity.canonical_identity(None, "00123"))
        self.assertIsNone(identity.canonical_identity("SIRET", "  "))
        self.assertIsNone(identity.canonical_identity(None, None))
        self.assertNotEqual(
            identity.canonical_identity("SIRET", "00123"),
            identity.canonical_identity("TVA", "00123"),
        )


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
                        (DATE '2024-02-01', 0, 'u1', 'siret', '00123'),
                        (DATE '2024-02-02', 0, 'u2', ' SIRET ', '00123 '),
                        (DATE '2024-02-03', 0, 'u3', 'TVA', '00123'),
                        (DATE '2024-02-04', 0, 'u4', NULL, 'abc'),
                        (DATE '2024-02-05', 0, 'u5', 'SIRET', NULL),
                        (DATE '2024-02-06', 0, 'u6', NULL, NULL),
                        (DATE '2025-03-01', 0, 'u7', 'siret', '0007'),
                        (DATE '2025-03-02', 0, 'u8', 'SIRET', '7'),
                        (DATE '2025-03-03', 1, 'u9', 'SIRET', '999'),
                        (DATE '2023-12-31', 0, 'old', 'SIRET', '888')
                ) AS records(dateNotification, modification_id, uid, titulaire_typeIdentifiant, titulaire_id)
            )
            TO ? (FORMAT PARQUET)
            """,
            [str(self.source)],
        )
        connection.close()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_prepare_groups_normalized_typed_identifiers_without_changing_source(self) -> None:
        source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()

        totals = prepare.prepare(self.source, self.output)

        self.assertEqual(totals, {2024: 6, 2025: 2})
        self.assertEqual(
            hashlib.sha256(self.source.read_bytes()).hexdigest(), source_hash
        )
        connection = duckdb.connect()
        rows = connection.execute(
            "SELECT year, status, normalized_type, normalized_value, source_line_count "
            "FROM read_parquet(?) ORDER BY year, status, normalized_type, normalized_value",
            [str(self.output / "holder-identities.parquet")],
        ).fetchall()
        connection.close()
        self.assertIn((2024, "resolved", "SIRET", "00123", 2), rows)
        self.assertIn((2024, "resolved", "TVA", "00123", 1), rows)
        self.assertIn((2025, "resolved", "SIRET", "0007", 1), rows)
        self.assertIn((2025, "resolved", "SIRET", "7", 1), rows)
        self.assertIn((2024, "missing_type", None, "abc", 1), rows)
        self.assertIn((2024, "missing_identifier", "SIRET", None, 1), rows)
        self.assertIn((2024, "missing_both", None, None, 1), rows)

        report = (self.output / "holder-resolution-report.md").read_text()
        self.assertIn("| 2024 | SIRET | Identité identifiée | 2 | 6 | 1 |", report)
        self.assertIn("| 2024 | NULL | Type manquant | 1 | 6 | n/a |", report)
        self.assertIn("| 2025 | SIRET | Identité identifiée | 2 | 2 | 2 |", report)

    def test_missing_source_fails_without_outputs(self) -> None:
        with self.assertRaisesRegex(prepare.ResolutionError, "absent ou illisible"):
            prepare.prepare(self.root / "missing.parquet", self.output)
        self.assertFalse(self.output.exists())

    def test_missing_required_column_fails_without_outputs(self) -> None:
        connection = duckdb.connect()
        connection.execute(
            "COPY (SELECT DATE '2024-01-01' AS dateNotification) TO ? (FORMAT PARQUET)",
            [str(self.source)],
        )
        connection.close()

        with self.assertRaisesRegex(prepare.ResolutionError, "colonnes requises"):
            prepare.prepare(self.source, self.output)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
