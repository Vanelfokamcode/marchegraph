from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import duckdb
from neo4j import GraphDatabase, Session
from neo4j.exceptions import DriverError, Neo4jError

from marchegraph.graph.load_initial_awards import (
    DATASET_ID,
    DEFAULT_BATCH_SIZE,
    DEFAULT_INPUT,
    iter_batches,
    write_batches,
)
from marchegraph.graph.neo4j_config import (
    LocalNeo4jURLError,
    validate_local_neo4j_uri,
)

MODIFICATION_FILTER = (
    "source.modification_id > 0 "
    "AND source.dateNotification >= DATE '2024-01-01' "
    "AND source.dateNotification < DATE '2026-01-01'"
)
INITIAL_FILTER = (
    "modification_id = 0 "
    "AND dateNotification >= DATE '2024-01-01' "
    "AND dateNotification < DATE '2026-01-01'"
)
REQUIRED_COLUMNS = {
    "uid",
    "id",
    "modification_id",
    "dateNotification",
    "nature",
    "acheteur_id",
    "acheteur_nom",
    "titulaire_id",
    "titulaire_typeIdentifiant",
    "titulaire_nom",
    "objet",
    "montant",
    "type",
    "codeCPV",
    "procedure",
    "dureeMois",
}
VALUE_FIELDS = (
    "nature_values",
    "montant_values",
    "procedure_values",
    "dureeMois_values",
    "objet_values",
    "type_values",
    "codeCPV_values",
    "acheteur_id_values",
    "acheteur_nom_values",
    "titulaire_nom_values",
    "titulaire_identity_values",
)
MISSING_FIELDS = tuple(
    f"{field.removesuffix('_values')}_missing_in_source"
    for field in VALUE_FIELDS
)


class ModificationLoadError(Exception):
    pass


@dataclass(frozen=True)
class AnnualModificationCounts:
    year: int
    version_count: int
    source_line_count: int
    linked_version_count: int
    unlinked_version_count: int


@dataclass(frozen=True)
class ModificationImportReport:
    annual_counts: tuple[AnnualModificationCounts, ...]


CREATE_CONSTRAINT = """
CREATE CONSTRAINT marchegraph_modification_version_key IF NOT EXISTS
FOR (version:Modification)
REQUIRE (version.source_id, version.uid, version.modification_id) IS UNIQUE
"""

UPSERT_MODIFICATIONS = """
UNWIND $rows AS row
MERGE (version:Modification {
    source_id: $source_id,
    uid: row.uid,
    modification_id: row.modification_id
})
SET version.source_record_id = row.source_record_id,
    version.annee = row.annee,
    version.dateNotification = row.dateNotification,
    version.source_line_count = row.source_line_count,
    version.nature_values = row.nature_values,
    version.nature_missing_in_source = row.nature_missing_in_source,
    version.montant_values = row.montant_values,
    version.montant_missing_in_source = row.montant_missing_in_source,
    version.procedure_values = row.procedure_values,
    version.procedure_missing_in_source = row.procedure_missing_in_source,
    version.dureeMois_values = row.dureeMois_values,
    version.dureeMois_missing_in_source = row.dureeMois_missing_in_source,
    version.objet_values = row.objet_values,
    version.objet_missing_in_source = row.objet_missing_in_source,
    version.type_values = row.type_values,
    version.type_missing_in_source = row.type_missing_in_source,
    version.codeCPV_values = row.codeCPV_values,
    version.codeCPV_missing_in_source = row.codeCPV_missing_in_source,
    version.acheteur_id_values = row.acheteur_id_values,
    version.acheteur_id_missing_in_source =
        row.acheteur_id_missing_in_source,
    version.acheteur_nom_values = row.acheteur_nom_values,
    version.acheteur_nom_missing_in_source =
        row.acheteur_nom_missing_in_source,
    version.titulaire_nom_values = row.titulaire_nom_values,
    version.titulaire_nom_missing_in_source =
        row.titulaire_nom_missing_in_source,
    version.titulaire_identity_values = row.titulaire_identity_values,
    version.titulaire_identity_missing_in_source =
        row.titulaire_identity_missing_in_source
WITH version, row
OPTIONAL MATCH (market:Marche {source_id: $source_id, uid: row.uid})
SET version.initial_market_status =
    CASE
        WHEN market IS NULL THEN 'missing_from_snapshot'
        ELSE 'linked'
    END
FOREACH (
    _ IN CASE WHEN market IS NULL THEN [] ELSE [1] END |
    MERGE (version)-[:MODIFICATION_DE]->(market)
)
"""

SOURCE_COUNTS_QUERY = f"""
WITH initial_markets AS (
    SELECT DISTINCT uid
    FROM prepared_decp
    WHERE {INITIAL_FILTER}
), versions AS (
    SELECT
        source.uid,
        source.modification_id,
        year(min(source.dateNotification)) AS year,
        count(*) AS source_line_count,
        initial.uid IS NOT NULL AS linked
    FROM prepared_decp AS source
    LEFT JOIN initial_markets AS initial USING (uid)
    WHERE {MODIFICATION_FILTER}
    GROUP BY source.uid, source.modification_id, initial.uid
)
SELECT
    year,
    count(*) AS version_count,
    sum(source_line_count) AS source_line_count,
    count(*) FILTER (WHERE linked) AS linked_version_count,
    count(*) FILTER (WHERE NOT linked) AS unlinked_version_count
FROM versions
GROUP BY year
ORDER BY year
"""

MODIFICATION_QUERY = f"""
WITH initial_markets AS (
    SELECT DISTINCT uid
    FROM prepared_decp
    WHERE {INITIAL_FILTER}
)
SELECT
    source.uid,
    source.modification_id,
    min(source.id) AS source_record_id,
    year(min(source.dateNotification)) AS annee,
    min(source.dateNotification) AS dateNotification,
    count(*) AS source_line_count,
    CASE
        WHEN initial.uid IS NULL THEN 'missing_from_snapshot'
        ELSE 'linked'
    END AS initial_market_status,
    list(DISTINCT source.nature ORDER BY source.nature)
        FILTER (WHERE source.nature IS NOT NULL) AS nature_values,
    bool_or(source.nature IS NULL) AS nature_missing_in_source,
    list(
        DISTINCT CAST(source.montant AS VARCHAR)
        ORDER BY CAST(source.montant AS VARCHAR)
    ) FILTER (WHERE source.montant IS NOT NULL) AS montant_values,
    bool_or(source.montant IS NULL) AS montant_missing_in_source,
    list(DISTINCT source.procedure ORDER BY source.procedure)
        FILTER (WHERE source.procedure IS NOT NULL) AS procedure_values,
    bool_or(source.procedure IS NULL) AS procedure_missing_in_source,
    list(DISTINCT source.dureeMois ORDER BY source.dureeMois)
        FILTER (WHERE source.dureeMois IS NOT NULL) AS dureeMois_values,
    bool_or(source.dureeMois IS NULL) AS dureeMois_missing_in_source,
    list(DISTINCT source.objet ORDER BY source.objet)
        FILTER (WHERE source.objet IS NOT NULL) AS objet_values,
    bool_or(source.objet IS NULL) AS objet_missing_in_source,
    list(DISTINCT source.type ORDER BY source.type)
        FILTER (WHERE source.type IS NOT NULL) AS type_values,
    bool_or(source.type IS NULL) AS type_missing_in_source,
    list(DISTINCT source.codeCPV ORDER BY source.codeCPV)
        FILTER (WHERE source.codeCPV IS NOT NULL) AS codeCPV_values,
    bool_or(source.codeCPV IS NULL) AS codeCPV_missing_in_source,
    list(DISTINCT source.acheteur_id ORDER BY source.acheteur_id)
        FILTER (WHERE source.acheteur_id IS NOT NULL) AS acheteur_id_values,
    bool_or(source.acheteur_id IS NULL) AS acheteur_id_missing_in_source,
    list(DISTINCT source.acheteur_nom ORDER BY source.acheteur_nom)
        FILTER (WHERE source.acheteur_nom IS NOT NULL) AS acheteur_nom_values,
    bool_or(source.acheteur_nom IS NULL) AS acheteur_nom_missing_in_source,
    list(DISTINCT source.titulaire_nom ORDER BY source.titulaire_nom)
        FILTER (WHERE source.titulaire_nom IS NOT NULL) AS titulaire_nom_values,
    bool_or(source.titulaire_nom IS NULL) AS titulaire_nom_missing_in_source,
    list(
        DISTINCT to_json(
            struct_pack(
                identifier_type := nullif(
                    upper(trim(source.titulaire_typeIdentifiant)),
                    ''
                ),
                identifier_value := nullif(trim(source.titulaire_id), '')
            )
        )
        ORDER BY to_json(
            struct_pack(
                identifier_type := nullif(
                    upper(trim(source.titulaire_typeIdentifiant)),
                    ''
                ),
                identifier_value := nullif(trim(source.titulaire_id), '')
            )
        )
    ) FILTER (
        WHERE source.titulaire_typeIdentifiant IS NOT NULL
           OR source.titulaire_id IS NOT NULL
    ) AS titulaire_identity_values,
    bool_or(
        source.titulaire_typeIdentifiant IS NULL
        OR trim(source.titulaire_typeIdentifiant) = ''
        OR source.titulaire_id IS NULL
        OR trim(source.titulaire_id) = ''
    ) AS titulaire_identity_missing_in_source
FROM prepared_decp AS source
LEFT JOIN initial_markets AS initial USING (uid)
WHERE {MODIFICATION_FILTER}
GROUP BY source.uid, source.modification_id, initial.uid
ORDER BY source.uid, source.modification_id
"""

GRAPH_COUNTS_QUERY = """
MATCH (version:Modification {source_id: $source_id})
OPTIONAL MATCH (version)-[link:MODIFICATION_DE]->(
    market:Marche {source_id: $source_id}
)
WITH version, collect(DISTINCT market) AS markets, count(link) AS link_count
RETURN version.annee AS year,
       count(version) AS version_count,
       sum(version.source_line_count) AS source_line_count,
       sum(CASE WHEN size(markets) > 0 THEN 1 ELSE 0 END)
           AS linked_version_count,
       sum(CASE WHEN size(markets) = 0 THEN 1 ELSE 0 END)
           AS unlinked_version_count,
       sum(
           CASE
               WHEN size(markets) = 0
                    AND (
                        version.initial_market_status <> 'missing_from_snapshot'
                        OR link_count <> 0
                    )
                   THEN 1
               WHEN size(markets) > 0
                    AND (
                        version.initial_market_status <> 'linked'
                        OR size(markets) > 1
                        OR link_count <> 1
                    )
                   THEN 1
               ELSE 0
           END
       ) AS inconsistent_versions
ORDER BY year
"""


def _validate_source(connection: duckdb.DuckDBPyConnection) -> None:
    columns = {
        str(row[0])
        for row in connection.execute(
            "DESCRIBE SELECT * FROM prepared_decp"
        ).fetchall()
    }
    missing_columns = REQUIRED_COLUMNS - columns
    if missing_columns:
        raise ModificationLoadError(
            "Le Parquet préparé ne contient pas les colonnes requises : "
            + ", ".join(sorted(missing_columns))
        )

    invalid_keys = connection.execute(
        f"""
        SELECT count(*)
        FROM prepared_decp AS source
        WHERE {MODIFICATION_FILTER}
          AND (
              source.uid IS NULL OR trim(source.uid) = ''
              OR source.id IS NULL OR trim(source.id) = ''
              OR source.modification_id IS NULL
          )
        """
    ).fetchone()[0]
    if invalid_keys:
        raise ModificationLoadError(
            "Le périmètre contient des versions sans clé source complète."
        )

    years = {
        int(row[0])
        for row in connection.execute(
            f"""
            SELECT DISTINCT year(dateNotification)
            FROM prepared_decp AS source
            WHERE {MODIFICATION_FILTER}
            """
        ).fetchall()
    }
    if years != {2024, 2025}:
        raise ModificationLoadError(
            "Le périmètre doit contenir des modifications notifiées en 2024 et 2025."
        )

    inconsistent_versions = connection.execute(
        f"""
        SELECT count(*)
        FROM (
            SELECT source.uid, source.modification_id
            FROM prepared_decp AS source
            WHERE {MODIFICATION_FILTER}
            GROUP BY source.uid, source.modification_id
            HAVING count(DISTINCT source.id) != 1
                OR count(DISTINCT source.dateNotification) != 1
        )
        """
    ).fetchone()[0]
    if inconsistent_versions:
        raise ModificationLoadError(
            "Une version ne possède pas un identifiant source et une date uniques."
        )


def _annual_source_counts(
    connection: duckdb.DuckDBPyConnection,
) -> dict[int, AnnualModificationCounts]:
    result: dict[int, AnnualModificationCounts] = {}
    for row in connection.execute(SOURCE_COUNTS_QUERY).fetchall():
        counts = AnnualModificationCounts(
            year=int(row[0]),
            version_count=int(row[1]),
            source_line_count=int(row[2]),
            linked_version_count=int(row[3]),
            unlinked_version_count=int(row[4]),
        )
        result[counts.year] = counts
    if set(result) != {2024, 2025}:
        raise ModificationLoadError(
            "Le contrôle source n'a pas produit de comptes pour 2024 et 2025."
        )
    return result


def _modification_batches(
    connection: duckdb.DuckDBPyConnection,
    batch_size: int,
) -> Iterator[list[dict[str, object]]]:
    for batch in iter_batches(connection, MODIFICATION_QUERY, batch_size):
        for row in batch:
            row["uid"] = str(row["uid"])
            row["modification_id"] = int(row["modification_id"])
            row["source_record_id"] = str(row["source_record_id"])
            row["annee"] = int(row["annee"])
            row["source_line_count"] = int(row["source_line_count"])
            for field in VALUE_FIELDS:
                values = row[field]
                row[field] = list(values) if values is not None else []
            for field in MISSING_FIELDS:
                row[field] = bool(row[field])
        yield batch


def _graph_counts(
    session: Session,
) -> dict[int, AnnualModificationCounts]:
    result: dict[int, AnnualModificationCounts] = {}
    inconsistent_versions = 0
    for row in session.run(GRAPH_COUNTS_QUERY, source_id=DATASET_ID):
        counts = AnnualModificationCounts(
            year=int(row["year"]),
            version_count=int(row["version_count"]),
            source_line_count=int(row["source_line_count"]),
            linked_version_count=int(row["linked_version_count"]),
            unlinked_version_count=int(row["unlinked_version_count"]),
        )
        result[counts.year] = counts
        inconsistent_versions += int(row["inconsistent_versions"])
    if inconsistent_versions:
        raise ModificationLoadError(
            "Des versions ont un statut ou un nombre de liens incohérent."
        )
    return result


def load_modification_versions(
    session: Session,
    source_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> ModificationImportReport:
    if batch_size < 1:
        raise ModificationLoadError("La taille de lot doit être strictement positive.")
    source_path = source_path.expanduser().resolve()
    if not source_path.is_file():
        raise ModificationLoadError(
            f"Le Parquet préparé est absent ou illisible : {source_path}"
        )

    connection = duckdb.connect(config={"memory_limit": "768MB", "threads": "1"})
    try:
        connection.read_parquet(str(source_path)).create_view("prepared_decp")
        _validate_source(connection)
        expected = _annual_source_counts(connection)

        session.run(CREATE_CONSTRAINT).consume()
        write_batches(
            session,
            UPSERT_MODIFICATIONS,
            _modification_batches(connection, batch_size),
        )
        actual = _graph_counts(session)
        if actual != expected:
            raise ModificationLoadError(
                "Les comptes Neo4j diffèrent des Parquet source : "
                f"attendu={expected}, obtenu={actual}."
            )
        return ModificationImportReport(
            annual_counts=tuple(expected[year] for year in (2024, 2025))
        )
    except duckdb.Error as error:
        raise ModificationLoadError(
            f"Lecture ou agrégation du Parquet impossible : {error}"
        ) from error
    finally:
        connection.close()


def run_import(
    source_path: Path,
    batch_size: int,
) -> ModificationImportReport:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise ModificationLoadError(
            "NEO4J_PASSWORD doit être défini dans l'environnement."
        )

    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    try:
        validate_local_neo4j_uri(uri)
    except LocalNeo4jURLError as error:
        raise ModificationLoadError(str(error)) from error
    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                return load_modification_versions(
                    session,
                    source_path,
                    batch_size,
                )
    except (DriverError, Neo4jError) as error:
        raise ModificationLoadError(
            f"Connexion ou écriture Neo4j impossible ({uri}) : {error}"
        ) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Charge localement les versions de modification des marchés 2024–2025."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Parquet préparé (défaut : data/prepared/decp.parquet).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Nombre de versions écrites par transaction.",
    )
    args = parser.parse_args(argv)
    try:
        report = run_import(args.input, args.batch_size)
    except ModificationLoadError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1

    print("Chargement idempotent des versions de modification vérifié.")
    for counts in report.annual_counts:
        print(
            f"{counts.year} : {counts.version_count} versions "
            f"({counts.source_line_count} lignes), "
            f"{counts.linked_version_count} reliées, "
            f"{counts.unlinked_version_count} sans marché initial."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
