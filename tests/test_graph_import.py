from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph.load_initial_awards import (
    HOLDER_LINK_QUERY,
    _annual_source_counts,
    iter_batches,
    _market_batches,
    _validate_views,
)


class InitialAwardImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "decp.parquet"
        self.identities = self.root / "holder-identities.parquet"
        self._write_fixtures()
        self.connection = duckdb.connect()
        self.addCleanup(self.connection.close)
        self.connection.read_parquet(str(self.source)).create_view("prepared_decp")
        self.connection.read_parquet(str(self.identities)).create_view(
            "holder_identities"
        )

    def _write_fixtures(self) -> None:
        connection = duckdb.connect()
        self.addCleanup(connection.close)
        connection.execute(
            """
            CREATE TABLE decp (
                uid VARCHAR,
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
                dureeMois SMALLINT,
                dateNotification DATE,
                modification_id SMALLINT
            )
            """
        )
        connection.executemany(
            "INSERT INTO decp VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "000-market-2024",
                    "Travaux",
                    "000-buyer",
                    "Acheteur de test",
                    "00000000000001",
                    "siret",
                    "Titulaire A",
                    "Objet A",
                    100.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    12,
                    "2024-03-01",
                    0,
                ),
                (
                    "000-market-2024",
                    "Services",
                    "000-buyer",
                    "Acheteur de test",
                    "00000000000001",
                    "SIRET",
                    "Titulaire A",
                    "Objet B",
                    250.0,
                    "Marché",
                    "45000000",
                    "Procédure adaptée",
                    24,
                    "2024-03-01",
                    0,
                ),
                (
                    "000-market-2024",
                    None,
                    "000-buyer",
                    "Acheteur de test",
                    "00000000000001",
                    "SIRET",
                    "Titulaire A",
                    None,
                    None,
                    "Marché",
                    "45000000",
                    None,
                    None,
                    "2024-03-01",
                    0,
                ),
                (
                    "market-no-holder",
                    "Travaux",
                    "000-buyer",
                    "Acheteur de test",
                    None,
                    None,
                    None,
                    "Objet sans identité résolue",
                    50.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    6,
                    "2024-04-01",
                    0,
                ),
                (
                    "market-2025",
                    "Fournitures",
                    "buyer-2025",
                    "Acheteur 2025",
                    "00000000000002",
                    "SIRET",
                    "Titulaire B",
                    "Objet 2025",
                    75.0,
                    "Marché",
                    "30000000",
                    "Appel d'offres",
                    3,
                    "2025-02-01",
                    0,
                ),
                (
                    "market-modification",
                    "Travaux",
                    "buyer-2025",
                    "Acheteur 2025",
                    "00000000000003",
                    "SIRET",
                    "Titulaire C",
                    "Modification hors périmètre",
                    999.0,
                    "Marché",
                    "45000000",
                    "Appel d'offres",
                    12,
                    "2025-05-01",
                    1,
                ),
            ],
        )
        connection.execute(
            """
            COPY decp TO ?
            (FORMAT PARQUET)
            """,
            [str(self.source)],
        )
        connection.execute(
            """
            CREATE TABLE identities (
                year INTEGER,
                status VARCHAR,
                normalized_type VARCHAR,
                normalized_value VARCHAR,
                source_line_count BIGINT
            )
            """
        )
        connection.executemany(
            "INSERT INTO identities VALUES (?, ?, ?, ?, ?)",
            [
                (2024, "resolved", "SIRET", "00000000000001", 3),
                (2024, "missing_both", None, None, 1),
                (2025, "resolved", "SIRET", "00000000000002", 1),
            ],
        )
        connection.execute(
            """
            COPY identities TO ?
            (FORMAT PARQUET)
            """,
            [str(self.identities)],
        )

    def test_market_import_keeps_distinct_values_and_missingness(self) -> None:
        batches = _market_batches(self.connection, batch_size=1)
        first_market = next(batches)[0]

        self.assertEqual(first_market["uid"], "000-market-2024")
        self.assertEqual(first_market["acheteur_id"], "000-buyer")
        self.assertEqual(first_market["nature_values"], ["Services", "Travaux"])
        self.assertEqual(first_market["montant_values"], ["100.0", "250.0"])
        self.assertEqual(
            first_market["procedure_values"],
            ["Appel d'offres", "Procédure adaptée"],
        )
        self.assertEqual(first_market["dureeMois_values"], [12, 24])
        self.assertEqual(first_market["objet_values"], ["Objet A", "Objet B"])
        self.assertTrue(first_market["nature_missing_in_source"])
        self.assertTrue(first_market["montant_missing_in_source"])
        self.assertTrue(first_market["procedure_missing_in_source"])
        self.assertTrue(first_market["dureeMois_missing_in_source"])
        self.assertTrue(first_market["objet_missing_in_source"])

    def test_annual_source_counts_exclude_modifications_and_unresolved_holders(
        self,
    ) -> None:
        _validate_views(self.connection)

        counts = _annual_source_counts(self.connection)

        self.assertEqual(counts[2024].market_count, 2)
        self.assertEqual(counts[2024].holder_count, 1)
        self.assertEqual(counts[2024].holder_link_count, 1)
        self.assertEqual(counts[2025].market_count, 1)
        self.assertEqual(counts[2025].holder_count, 1)
        self.assertEqual(counts[2025].holder_link_count, 1)

    def test_only_resolved_typed_identifiers_create_holder_links(self) -> None:
        links = [
            row
            for batch in iter_batches(self.connection, HOLDER_LINK_QUERY, 2)
            for row in batch
        ]

        self.assertEqual(
            links,
            [
                {
                    "uid": "000-market-2024",
                    "identifier_type": "SIRET",
                    "identifier_value": "00000000000001",
                },
                {
                    "uid": "market-2025",
                    "identifier_type": "SIRET",
                    "identifier_value": "00000000000002",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
