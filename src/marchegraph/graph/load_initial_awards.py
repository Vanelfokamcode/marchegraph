from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import duckdb
from neo4j import GraphDatabase, ManagedTransaction, Session
from neo4j.exceptions import DriverError, Neo4jError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "data/prepared/decp.parquet"
DEFAULT_IDENTITIES = PROJECT_ROOT / "data/prepared/holder-identities.parquet"
INITIAL_YEARS = (2024, 2025)
DATASET_ID = "decp-initial-2024-2025"
DEFAULT_BATCH_SIZE = 2_000
SOURCE_FILTER = (
    "modification_id = 0 "
    "AND dateNotification >= DATE '2024-01-01' "
    "AND dateNotification < DATE '2026-01-01'"
)
SOURCE_FILTER_QUALIFIED = (
    "source.modification_id = 0 "
    "AND source.dateNotification >= DATE '2024-01-01' "
    "AND source.dateNotification < DATE '2026-01-01'"
)
IDENTITY_FILTER = "year IN (2024, 2025) AND status = 'resolved'"

SOURCE_COLUMNS = {
    "uid",
    "nature",
    "acheteur_id",
    "acheteur_nom",
    "acheteur_region_code",
    "titulaire_id",
    "titulaire_typeIdentifiant",
    "titulaire_nom",
    "objet",
    "montant",
    "type",
    "codeCPV",
    "procedure",
    "dureeMois",
    "dateNotification",
    "modification_id",
}
IDENTITY_COLUMNS = {
    "year",
    "status",
    "normalized_type",
    "normalized_value",
}
MARKET_VALUE_FIELDS = (
    "type_values",
    "codeCPV_values",
    "nature_values",
    "montant_values",
    "procedure_values",
    "dureeMois_values",
    "objet_values",
    "acheteur_region_code_values",
)
MARKET_MISSING_FIELDS = tuple(
    f"{field.removesuffix('_values')}_missing_in_source"
    for field in MARKET_VALUE_FIELDS
)


class InitialAwardLoadError(Exception):
    pass


@dataclass(frozen=True)
class AnnualImportCounts:
    year: int
    market_count: int
    holder_count: int
    holder_link_count: int


@dataclass(frozen=True)
class InitialAwardImportReport:
    annual_counts: tuple[AnnualImportCounts, ...]


CREATE_CONSTRAINTS = (
    """
    CREATE CONSTRAINT marchegraph_initial_uid IF NOT EXISTS
    FOR (market:Marche) REQUIRE market.uid IS UNIQUE
    """,
    """
    CREATE CONSTRAINT marchegraph_initial_buyer_key IF NOT EXISTS
    FOR (buyer:Acheteur)
    REQUIRE (buyer.source_id, buyer.id) IS UNIQUE
    """,
    """
    CREATE CONSTRAINT marchegraph_initial_holder_key IF NOT EXISTS
    FOR (holder:Titulaire)
    REQUIRE (
        holder.source_id,
        holder.identifier_type,
        holder.identifier_value
    ) IS UNIQUE
    """,
)

UPSERT_BUYERS = """
UNWIND $rows AS row
MERGE (buyer:Acheteur {source_id: $source_id, id: row.id})
SET buyer.nom_values = row.nom_values,
    buyer.nom_missing_in_source = row.nom_missing_in_source
"""

UPSERT_HOLDERS = """
UNWIND $rows AS row
MERGE (holder:Titulaire {
    source_id: $source_id,
    identifier_type: row.identifier_type,
    identifier_value: row.identifier_value
})
SET holder.nom_values = row.nom_values,
    holder.nom_missing_in_source = row.nom_missing_in_source
"""

UPSERT_MARKETS = """
UNWIND $rows AS row
MATCH (buyer:Acheteur {source_id: $source_id, id: row.acheteur_id})
MERGE (market:Marche {uid: row.uid})
SET market.source_id = $source_id,
    market.annee = row.annee,
    market.acheteur_id = row.acheteur_id,
    market.acheteur_region_code_values = row.acheteur_region_code_values,
    market.acheteur_region_code_missing_in_source =
        row.acheteur_region_code_missing_in_source,
    market.type_values = row.type_values,
    market.type_missing_in_source = row.type_missing_in_source,
    market.codeCPV_values = row.codeCPV_values,
    market.codeCPV_missing_in_source = row.codeCPV_missing_in_source,
    market.nature_values = row.nature_values,
    market.nature_missing_in_source = row.nature_missing_in_source,
    market.montant_values = row.montant_values,
    market.montant_missing_in_source = row.montant_missing_in_source,
    market.procedure_values = row.procedure_values,
    market.procedure_missing_in_source = row.procedure_missing_in_source,
    market.dureeMois_values = row.dureeMois_values,
    market.dureeMois_missing_in_source = row.dureeMois_missing_in_source,
    market.objet_values = row.objet_values,
    market.objet_missing_in_source = row.objet_missing_in_source
MERGE (market)-[:A_ACHETEUR]->(buyer)
"""

UPSERT_HOLDER_LINKS = """
UNWIND $rows AS row
MATCH (market:Marche {source_id: $source_id, uid: row.uid})
MATCH (holder:Titulaire {
    source_id: $source_id,
    identifier_type: row.identifier_type,
    identifier_value: row.identifier_value
})
MERGE (market)-[:A_TITULAIRE]->(holder)
"""

GRAPH_COUNTS = """
MATCH (market:Marche {source_id: $source_id})
OPTIONAL MATCH (market)-[:A_TITULAIRE]->(holder:Titulaire {
    source_id: $source_id
})
WITH market.annee AS year,
     count(DISTINCT market.uid) AS market_count,
     count(DISTINCT holder) AS holder_count,
     count(holder) AS holder_link_count
RETURN year, market_count, holder_count, holder_link_count
ORDER BY year
"""


def _existing_columns(
    connection: duckdb.DuckDBPyConnection, view_name: str
) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            f"DESCRIBE SELECT * FROM {view_name}"
        ).fetchall()
    }


def _validate_views(connection: duckdb.DuckDBPyConnection) -> None:
    missing_source = SOURCE_COLUMNS - _existing_columns(connection, "prepared_decp")
    if missing_source:
        raise InitialAwardLoadError(
            "Le Parquet préparé ne contient pas les colonnes requises : "
            + ", ".join(sorted(missing_source))
        )

    missing_identity = IDENTITY_COLUMNS - _existing_columns(
        connection, "holder_identities"
    )
    if missing_identity:
        raise InitialAwardLoadError(
            "Le Parquet des identités ne contient pas les colonnes requises : "
            + ", ".join(sorted(missing_identity))
        )

    invalid_counts = connection.execute(
        f"""
        SELECT
            count(*) FILTER (
                WHERE uid IS NULL OR trim(uid) = ''
            ) AS invalid_uid_count,
            count(*) FILTER (
                WHERE acheteur_id IS NULL OR trim(acheteur_id) = ''
            ) AS invalid_buyer_count
        FROM prepared_decp
        WHERE {SOURCE_FILTER}
        """
    ).fetchone()
    if invalid_counts is None:
        raise InitialAwardLoadError("Le contrôle des identifiants source a échoué.")
    if invalid_counts[0] or invalid_counts[1]:
        raise InitialAwardLoadError(
            "Le périmètre contient des marchés sans uid ou identifiant acheteur."
        )

    years = {
        int(row[0])
        for row in connection.execute(
            f"""
            SELECT DISTINCT year(dateNotification)
            FROM prepared_decp
            WHERE {SOURCE_FILTER}
            """
        ).fetchall()
    }
    if years != set(INITIAL_YEARS):
        raise InitialAwardLoadError(
            "Le périmètre doit contenir des attributions initiales en 2024 et 2025."
        )

    inconsistent_markets = connection.execute(
        f"""
        SELECT count(*)
        FROM (
            SELECT uid
            FROM prepared_decp
            WHERE {SOURCE_FILTER}
            GROUP BY uid
            HAVING count(DISTINCT year(dateNotification)) != 1
                OR count(DISTINCT acheteur_id) != 1
        )
        """
    ).fetchone()[0]
    if inconsistent_markets:
        raise InitialAwardLoadError(
            "Un uid correspond à plusieurs années ou acheteurs dans le périmètre."
        )

    unresolved_identity_keys = connection.execute(
        f"""
        SELECT count(*)
        FROM holder_identities
        WHERE {IDENTITY_FILTER}
          AND (
              normalized_type IS NULL OR trim(normalized_type) = ''
              OR normalized_value IS NULL OR trim(normalized_value) = ''
          )
        """
    ).fetchone()[0]
    if unresolved_identity_keys:
        raise InitialAwardLoadError(
            "Le Parquet des identités marque comme résolues des clés incomplètes."
        )

    duplicate_identity_keys = connection.execute(
        f"""
        SELECT count(*)
        FROM (
            SELECT year, normalized_type, normalized_value
            FROM holder_identities
            WHERE {IDENTITY_FILTER}
            GROUP BY year, normalized_type, normalized_value
            HAVING count(*) > 1
        )
        """
    ).fetchone()[0]
    if duplicate_identity_keys:
        raise InitialAwardLoadError(
            "Le Parquet des identités contient des clés résolues dupliquées."
        )


def _annual_source_counts(
    connection: duckdb.DuckDBPyConnection,
) -> dict[int, AnnualImportCounts]:
    markets = {
        int(year): int(count)
        for year, count in connection.execute(
            f"""
            SELECT year(dateNotification), count(DISTINCT uid)
            FROM prepared_decp
            WHERE {SOURCE_FILTER}
            GROUP BY year(dateNotification)
            """
        ).fetchall()
    }

    holders = {
        int(year): int(count)
        for year, count in connection.execute(
            f"""
            SELECT year, count(*)
            FROM holder_identities
            WHERE {IDENTITY_FILTER}
            GROUP BY year
            """
        ).fetchall()
    }

    links = {
        int(year): int(count)
        for year, count in connection.execute(
            f"""
            SELECT year, count(*)
            FROM (
                SELECT DISTINCT
                    year(source.dateNotification) AS year,
                    source.uid,
                    identity.normalized_type,
                    identity.normalized_value
                FROM prepared_decp AS source
                JOIN holder_identities AS identity
                  ON identity.year = year(source.dateNotification)
                 AND identity.status = 'resolved'
                 AND identity.normalized_type =
                     upper(trim(source.titulaire_typeIdentifiant))
                 AND identity.normalized_value = trim(source.titulaire_id)
                WHERE {SOURCE_FILTER_QUALIFIED}
            )
            GROUP BY year
            """
        ).fetchall()
    }

    linked_holders = {
        int(year): int(count)
        for year, count in connection.execute(
            f"""
            SELECT year, count(*)
            FROM (
                SELECT DISTINCT
                    year(source.dateNotification) AS year,
                    identity.normalized_type,
                    identity.normalized_value
                FROM prepared_decp AS source
                JOIN holder_identities AS identity
                  ON identity.year = year(source.dateNotification)
                 AND identity.status = 'resolved'
                 AND identity.normalized_type =
                     upper(trim(source.titulaire_typeIdentifiant))
                 AND identity.normalized_value = trim(source.titulaire_id)
                WHERE {SOURCE_FILTER_QUALIFIED}
            )
            GROUP BY year
            """
        ).fetchall()
    }

    if linked_holders != holders:
        raise InitialAwardLoadError(
            "Les identités résolues ne correspondent pas aux clés présentes "
            "dans les attributions initiales."
        )

    return {
        year: AnnualImportCounts(
            year=year,
            market_count=markets.get(year, 0),
            holder_count=holders.get(year, 0),
            holder_link_count=links.get(year, 0),
        )
        for year in INITIAL_YEARS
    }


def iter_batches(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    batch_size: int,
) -> Iterator[list[dict[str, object]]]:
    cursor = connection.execute(query)
    columns = [str(column[0]) for column in cursor.description]
    while rows := cursor.fetchmany(batch_size):
        yield [
            dict(zip(columns, row, strict=True))
            for row in rows
        ]


BUYER_QUERY = f"""
SELECT
    acheteur_id AS id,
    list(DISTINCT acheteur_nom ORDER BY acheteur_nom)
        FILTER (WHERE acheteur_nom IS NOT NULL) AS nom_values,
    bool_or(acheteur_nom IS NULL) AS nom_missing_in_source
FROM prepared_decp
WHERE {SOURCE_FILTER}
GROUP BY acheteur_id
ORDER BY acheteur_id
"""

HOLDER_QUERY = f"""
SELECT
    identity.normalized_type AS identifier_type,
    identity.normalized_value AS identifier_value,
    list(DISTINCT source.titulaire_nom ORDER BY source.titulaire_nom)
        FILTER (WHERE source.titulaire_nom IS NOT NULL) AS nom_values,
    bool_or(source.titulaire_nom IS NULL) AS nom_missing_in_source
FROM prepared_decp AS source
JOIN holder_identities AS identity
  ON identity.year = year(source.dateNotification)
 AND identity.status = 'resolved'
 AND identity.normalized_type = upper(trim(source.titulaire_typeIdentifiant))
 AND identity.normalized_value = trim(source.titulaire_id)
WHERE {SOURCE_FILTER_QUALIFIED}
GROUP BY identity.normalized_type, identity.normalized_value
ORDER BY identity.normalized_type, identity.normalized_value
"""

MARKET_QUERY = f"""
SELECT
    uid,
    year(dateNotification) AS annee,
    min(acheteur_id) AS acheteur_id,
    list(DISTINCT acheteur_region_code ORDER BY acheteur_region_code)
        FILTER (WHERE acheteur_region_code IS NOT NULL)
        AS acheteur_region_code_values,
    bool_or(acheteur_region_code IS NULL)
        AS acheteur_region_code_missing_in_source,
    list(DISTINCT type ORDER BY type)
        FILTER (WHERE type IS NOT NULL) AS type_values,
    bool_or(type IS NULL) AS type_missing_in_source,
    list(DISTINCT codeCPV ORDER BY codeCPV)
        FILTER (WHERE codeCPV IS NOT NULL) AS codeCPV_values,
    bool_or(codeCPV IS NULL) AS codeCPV_missing_in_source,
    list(DISTINCT nature ORDER BY nature)
        FILTER (WHERE nature IS NOT NULL) AS nature_values,
    bool_or(nature IS NULL) AS nature_missing_in_source,
    list(DISTINCT CAST(montant AS VARCHAR) ORDER BY CAST(montant AS VARCHAR))
        FILTER (WHERE montant IS NOT NULL) AS montant_values,
    bool_or(montant IS NULL) AS montant_missing_in_source,
    list(DISTINCT procedure ORDER BY procedure)
        FILTER (WHERE procedure IS NOT NULL) AS procedure_values,
    bool_or(procedure IS NULL) AS procedure_missing_in_source,
    list(DISTINCT dureeMois ORDER BY dureeMois)
        FILTER (WHERE dureeMois IS NOT NULL) AS dureeMois_values,
    bool_or(dureeMois IS NULL) AS dureeMois_missing_in_source,
    list(DISTINCT objet ORDER BY objet)
        FILTER (WHERE objet IS NOT NULL) AS objet_values,
    bool_or(objet IS NULL) AS objet_missing_in_source
FROM prepared_decp
WHERE {SOURCE_FILTER}
GROUP BY uid, year(dateNotification)
ORDER BY uid
"""

HOLDER_LINK_QUERY = f"""
SELECT DISTINCT
    source.uid,
    identity.normalized_type AS identifier_type,
    identity.normalized_value AS identifier_value
FROM prepared_decp AS source
JOIN holder_identities AS identity
  ON identity.year = year(source.dateNotification)
 AND identity.status = 'resolved'
 AND identity.normalized_type = upper(trim(source.titulaire_typeIdentifiant))
 AND identity.normalized_value = trim(source.titulaire_id)
WHERE {SOURCE_FILTER_QUALIFIED}
ORDER BY source.uid, identifier_type, identifier_value
"""


def _market_batches(
    connection: duckdb.DuckDBPyConnection,
    batch_size: int,
) -> Iterator[list[dict[str, object]]]:
    for batch in iter_batches(connection, MARKET_QUERY, batch_size):
        for row in batch:
            row["annee"] = int(row["annee"])
            row["acheteur_id"] = str(row["acheteur_id"])
            row["uid"] = str(row["uid"])
            for field in MARKET_VALUE_FIELDS:
                values = row[field]
                row[field] = list(values) if values is not None else []
            for field in MARKET_MISSING_FIELDS:
                row[field] = bool(row[field])
        yield batch


def _write_batch(
    transaction: ManagedTransaction,
    query: str,
    rows: list[dict[str, object]],
    source_id: str,
) -> None:
    transaction.run(query, rows=rows, source_id=source_id).consume()


def write_batches(
    session: Session,
    query: str,
    batches: Iterator[list[dict[str, object]]],
) -> None:
    for batch in batches:
        session.execute_write(_write_batch, query, batch, DATASET_ID)


def _write_constraints(session: Session) -> None:
    for query in CREATE_CONSTRAINTS:
        session.run(query).consume()


def _graph_counts(session: Session) -> dict[int, AnnualImportCounts]:
    result: dict[int, AnnualImportCounts] = {}
    for record in session.run(GRAPH_COUNTS, source_id=DATASET_ID):
        year = int(record["year"])
        result[year] = AnnualImportCounts(
            year=year,
            market_count=int(record["market_count"]),
            holder_count=int(record["holder_count"]),
            holder_link_count=int(record["holder_link_count"]),
        )
    return result


def load_initial_awards(
    session: Session,
    source_path: Path,
    identities_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> InitialAwardImportReport:
    if batch_size < 1:
        raise InitialAwardLoadError("La taille de lot doit être strictement positive.")
    source_path = source_path.expanduser().resolve()
    identities_path = identities_path.expanduser().resolve()
    if not source_path.is_file():
        raise InitialAwardLoadError(
            f"Le Parquet préparé est absent ou illisible : {source_path}"
        )
    if not identities_path.is_file():
        raise InitialAwardLoadError(
            f"Le Parquet des identités est absent ou illisible : {identities_path}"
        )

    connection = duckdb.connect(config={"memory_limit": "768MB", "threads": "1"})
    try:
        connection.read_parquet(str(source_path)).create_view("prepared_decp")
        connection.read_parquet(str(identities_path)).create_view("holder_identities")
        _validate_views(connection)
        expected = _annual_source_counts(connection)

        _write_constraints(session)
        write_batches(
            session,
            UPSERT_BUYERS,
            iter_batches(connection, BUYER_QUERY, batch_size),
        )
        write_batches(
            session,
            UPSERT_HOLDERS,
            iter_batches(connection, HOLDER_QUERY, batch_size),
        )
        write_batches(
            session,
            UPSERT_MARKETS,
            _market_batches(connection, batch_size),
        )
        write_batches(
            session,
            UPSERT_HOLDER_LINKS,
            iter_batches(connection, HOLDER_LINK_QUERY, batch_size),
        )
        actual = _graph_counts(session)
        if actual != expected:
            raise InitialAwardLoadError(
                "Les comptes Neo4j diffèrent des Parquet source : "
                f"attendu={expected}, obtenu={actual}."
            )
        return InitialAwardImportReport(
            annual_counts=tuple(expected[year] for year in INITIAL_YEARS)
        )
    except duckdb.Error as error:
        raise InitialAwardLoadError(
            f"Lecture ou agrégation des Parquet impossible : {error}"
        ) from error
    finally:
        connection.close()


def run_import(
    source_path: Path,
    identities_path: Path,
    batch_size: int,
) -> InitialAwardImportReport:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise InitialAwardLoadError(
            "NEO4J_PASSWORD doit être défini dans l'environnement."
        )

    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    username = os.environ.get("NEO4J_USERNAME", "neo4j")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    try:
        with GraphDatabase.driver(uri, auth=(username, password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=database) as session:
                return load_initial_awards(
                    session,
                    source_path,
                    identities_path,
                    batch_size,
                )
    except (DriverError, Neo4jError) as error:
        raise InitialAwardLoadError(
            f"Connexion ou écriture Neo4j impossible ({uri}) : {error}"
        ) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Charge localement les attributions initiales 2024–2025 dans Neo4j."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Parquet préparé (défaut : data/prepared/decp.parquet).",
    )
    parser.add_argument(
        "--identities",
        type=Path,
        default=DEFAULT_IDENTITIES,
        help=(
            "Parquet des identités résolues "
            "(défaut : data/prepared/holder-identities.parquet)."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Nombre d'enregistrements écrits par transaction.",
    )
    args = parser.parse_args(argv)
    try:
        report = run_import(args.input, args.identities, args.batch_size)
    except InitialAwardLoadError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1

    print("Chargement idempotent des attributions initiales vérifié.")
    for counts in report.annual_counts:
        print(
            f"{counts.year} : {counts.market_count} marchés, "
            f"{counts.holder_count} titulaires résolus, "
            f"{counts.holder_link_count} liens marché–titulaire."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
