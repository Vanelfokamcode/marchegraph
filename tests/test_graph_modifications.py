from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph.load_modifications import (
    MODIFICATION_QUERY,
    SOURCE_COUNTS_QUERY,
    _modification_batches,
    _validate_source,
)


class ModificationImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.source = Path(self.temporary_directory.name) / "decp.parquet"
        self.connection = duckdb.connect()
        self.addCleanup(self.connection.close)
        self._write_fixture()
        self.connection.read_parquet(str(self.source)).create_view("prepared_decp")

    def _write_fixture(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE decp (
                uid VARCHAR,
                id VARCHAR,
                modification_id SMALLINT,
                dateNotification DATE,
                nature VARCHAR,
                acheteur_id VARCHAR,
                acheteur_nom VARCHAR,
                titulaire_id VARCHAR,
                titulaire_typeIdentifiant VARCHAR,
                titulaire_nom VARCHAR,
                objet VARCHAR,
                montant DOUBLE,
                type VARCHAR,
                codeCPV VARCHAR,
                procedure VARCHAR,
                dureeMois SMALLINT
            )
            """
        )
        self.connection.executemany(
            "INSERT INTO decp VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "contract-001",
                    "initial-001",
                    0,
                    "2024-01-01",
                    "Travaux",
                    "buyer-001",
                    "Acheteur A",
                    "00000000000001",
                    "SIRET",
                    "Titulaire A",
                    "Objet initial",
                    10.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    12,
                ),
                (
                    "contract-001",
                    "source-mod-001",
                    1,
                    "2024-05-01",
                    "Travaux",
                    "buyer-001",
                    "Acheteur A",
                    "00000000000001",
                    "siret",
                    "Titulaire A",
                    "Objet modifié A",
                    20.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    18,
                ),
                (
                    "contract-001",
                    "source-mod-001",
                    1,
                    "2024-05-01",
                    "Travaux",
                    "buyer-001",
                    "Acheteur A",
                    "00000000000002",
                    "SIRET",
                    "Titulaire B",
                    "Objet modifié B",
                    25.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    18,
                ),
                (
                    "contract-orphan-2024",
                    "source-orphan-2024",
                    1,
                    "2024-06-01",
                    "Services",
                    "buyer-002",
                    "Acheteur B",
                    None,
                    None,
                    None,
                    "Objet sans marché initial",
                    None,
                    "Marché",
                    "72000000",
                    "Procédure adaptée",
                    None,
                ),
                (
                    "contract-001",
                    "source-mod-002",
                    2,
                    "2025-02-01",
                    "Travaux",
                    "buyer-001",
                    "Acheteur A",
                    "00000000000002",
                    "SIRET",
                    "Titulaire B",
                    "Objet modifié 2025",
                    30.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    24,
                ),
                (
                    "contract-orphan-2025",
                    "source-orphan-2025",
                    1,
                    "2025-03-01",
                    "Fournitures",
                    "buyer-003",
                    "Acheteur C",
                    "00000000000003",
                    "SIRET",
                    "Titulaire C",
                    "Objet sans marché initial",
                    40.0,
                    "Marché",
                    "30000000",
                    "Appel d'offres",
                    6,
                ),
            ],
        )
        self.connection.execute(
            """
            COPY decp TO ?
            (FORMAT PARQUET)
            """,
            [str(self.source)],
        )

    def test_versions_preserve_distinct_values_and_explicit_missing_links(
        self,
    ) -> None:
        _validate_source(self.connection)
        batches = _modification_batches(self.connection, batch_size=1)
        first_version = next(batches)[0]

        self.assertEqual(first_version["uid"], "contract-001")
        self.assertEqual(first_version["modification_id"], 1)
        self.assertEqual(first_version["source_record_id"], "source-mod-001")
        self.assertEqual(first_version["annee"], 2024)
        self.assertEqual(
            first_version["objet_values"],
            ["Objet modifié A", "Objet modifié B"],
        )
        self.assertEqual(first_version["montant_values"], ["20.0", "25.0"])
        self.assertEqual(
            first_version["titulaire_identity_values"],
            [
                '{"identifier_type":"SIRET","identifier_value":"00000000000001"}',
                '{"identifier_type":"SIRET","identifier_value":"00000000000002"}',
            ],
        )
        self.assertEqual(first_version["initial_market_status"], "linked")
        self.assertEqual(first_version["source_line_count"], 2)

        counts = {
            int(row[0]): tuple(int(value) for value in row[1:])
            for row in self.connection.execute(SOURCE_COUNTS_QUERY).fetchall()
        }
        self.assertEqual(counts[2024], (2, 3, 1, 1))
        self.assertEqual(counts[2025], (2, 2, 1, 1))

        orphan = next(
            row
            for batch in _modification_batches(self.connection, batch_size=10)
            for row in batch
            if row["uid"] == "contract-orphan-2024"
        )
        self.assertEqual(orphan["initial_market_status"], "missing_from_snapshot")
        self.assertTrue(orphan["titulaire_identity_missing_in_source"])


if __name__ == "__main__":
    unittest.main()
