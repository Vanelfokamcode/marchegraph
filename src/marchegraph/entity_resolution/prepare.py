from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from itertools import islice
from pathlib import Path

import duckdb

from identity import (
    canonical_identity,
    normalize_identifier_type,
    normalize_identifier_value,
    resolution_status,
)

OUTPUT_FILENAMES = ("holder-identities.parquet", "holder-resolution-report.md")
REQUIRED_COLUMNS = {
    "dateNotification",
    "modification_id",
    "titulaire_typeIdentifiant",
    "titulaire_id",
}
STATUS_LABELS = {
    "resolved": "Identité identifiée",
    "missing_type": "Type manquant",
    "missing_identifier": "Identifiant manquant",
    "missing_both": "Type et identifiant manquants",
}


class ResolutionError(Exception):
    pass


class _PublicationRollbackError(OSError):
    pass


def _sql_path(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _render_report(
    source: Path,
    annual_totals: dict[int, int],
    summary: list[tuple[int, str, str | None, int, int]],
) -> str:
    lines = [
        "# Résolution des identités titulaires",
        "",
        f"Source préparée : `{source.as_posix()}`.",
        "Périmètre : attributions initiales (`modification_id = 0`), notifiées",
        "en 2024 et 2025.",
        "",
        "Une identité est définie par le type d'identifiant en majuscules et sa",
        "valeur sans espaces externes. La valeur conserve sa casse, sa",
        "ponctuation, ses espaces internes et ses zéros initiaux. Aucun",
        "rapprochement par nom n'est effectué. Les identifiants manquants restent",
        "non résolus.",
        "",
        "| Année | Type normalisé | Statut | Lignes | Total annuel | Identités canoniques |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for year, status, identifier_type, line_count, identity_count in summary:
        type_label = "NULL" if identifier_type is None else identifier_type
        identities = str(identity_count) if status == "resolved" else "n/a"
        lines.append(
            f"| {year} | {type_label} | {STATUS_LABELS[status]} | "
            f"{line_count} | {annual_totals[year]} | {identities} |"
        )
    lines.extend(
        [
            "",
            "Les lignes identifiées et les identités canoniques sont comptées",
            "séparément ; les lignes sans type ou valeur sont conservées dans",
            "des catégories non résolues. Le Parquet source n'est pas modifié.",
            "",
        ]
    )
    return "\n".join(lines)


def _publish_outputs(stage_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = stage_dir / "backup"
    backup_dir.mkdir()
    backed_up: list[str] = []
    installed: list[str] = []
    for filename in OUTPUT_FILENAMES:
        existing = output_dir / filename
        if existing.is_symlink() or (existing.exists() and not existing.is_file()):
            raise OSError(f"Une sortie attendue n'est pas un fichier : {existing}")
    try:
        for filename in OUTPUT_FILENAMES:
            existing = output_dir / filename
            if existing.exists():
                os.replace(existing, backup_dir / filename)
                backed_up.append(filename)
        for filename in OUTPUT_FILENAMES:
            os.replace(stage_dir / filename, output_dir / filename)
            installed.append(filename)
    except OSError as error:
        rollback_errors: list[str] = []
        for filename in installed:
            try:
                (output_dir / filename).unlink()
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for filename in backed_up:
            try:
                os.replace(backup_dir / filename, output_dir / filename)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        if rollback_errors:
            raise _PublicationRollbackError(
                f"Publication impossible ({error}); sauvegardes conservées dans "
                f"{backup_dir}: {'; '.join(rollback_errors)}"
            ) from error
        raise


def prepare(source: Path, output_dir: Path) -> dict[int, int]:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_file():
        raise ResolutionError(f"Le Parquet préparé est absent ou illisible : {source}")
    if source in {
        output_dir / OUTPUT_FILENAMES[0],
        output_dir / OUTPUT_FILENAMES[1],
    }:
        raise ResolutionError("Le dossier de sortie ne peut pas écraser le Parquet source.")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(
        tempfile.mkdtemp(prefix=".holder-resolution-stage-", dir=output_dir.parent)
    )
    spill_dir = Path(
        tempfile.mkdtemp(prefix=".holder-resolution-duckdb-", dir=output_dir.parent)
    )
    connection: duckdb.DuckDBPyConnection | None = None
    preserve_stage = False
    try:
        connection = duckdb.connect(
            config={
                "memory_limit": "768MB",
                "threads": "1",
                "temp_directory": str(spill_dir),
            }
        )
        try:
            connection.read_parquet(str(source)).create_view("prepared_decp")
            columns = {
                row[0]
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM prepared_decp"
                ).fetchall()
            }
        except duckdb.Error as error:
            raise ResolutionError(f"Lecture du Parquet préparé impossible : {error}") from error
        missing_columns = REQUIRED_COLUMNS - columns
        if missing_columns:
            raise ResolutionError(
                "Le Parquet préparé ne contient pas les colonnes requises : "
                + ", ".join(sorted(missing_columns))
            )

        period_filter = (
            "modification_id = 0 "
            "AND dateNotification >= DATE '2024-01-01' "
            "AND dateNotification < DATE '2026-01-01'"
        )
        annual_totals = {
            int(year): int(total)
            for year, total in connection.execute(
                "SELECT year(dateNotification), count(*) "
                f"FROM prepared_decp WHERE {period_filter} "
                "GROUP BY year(dateNotification)"
            ).fetchall()
        }
        grouped_source = connection.execute(
            "SELECT year(dateNotification), titulaire_typeIdentifiant, "
            "titulaire_id, count(*) "
            f"FROM prepared_decp WHERE {period_filter} "
            "GROUP BY year(dateNotification), titulaire_typeIdentifiant, titulaire_id"
        )
        identity_counts: dict[tuple[int, str, str | None, str | None], int] = {}
        while grouped_rows := grouped_source.fetchmany(10_000):
            for year, raw_type, raw_value, source_line_count in grouped_rows:
                normalized_type = normalize_identifier_type(raw_type)
                normalized_value = normalize_identifier_value(raw_value)
                status = resolution_status(normalized_type, normalized_value)
                if status == "resolved":
                    identity = canonical_identity(raw_type, raw_value)
                    if identity is None:
                        raise ResolutionError(
                            "Un identifiant complet n'a pas produit de clé canonique."
                        )
                    normalized_type, normalized_value = identity
                key = (
                    int(year),
                    status,
                    normalized_type,
                    normalized_value,
                )
                identity_counts[key] = (
                    identity_counts.get(key, 0) + int(source_line_count)
                )

        connection.execute(
            """
            CREATE TEMP TABLE holder_identities (
                year INTEGER,
                status VARCHAR,
                normalized_type VARCHAR,
                normalized_value VARCHAR,
                source_line_count BIGINT
            )
            """
        )
        identity_iterator = iter(identity_counts.items())
        while identity_batch := list(islice(identity_iterator, 10_000)):
            connection.executemany(
                "INSERT INTO holder_identities VALUES (?, ?, ?, ?, ?)",
                [
                    (*key, source_line_count)
                    for key, source_line_count in identity_batch
                ],
            )
        result_totals = {
            int(year): int(total)
            for year, total in connection.execute(
                "SELECT year, sum(source_line_count) "
                "FROM holder_identities GROUP BY year"
            ).fetchall()
        }
        if result_totals != annual_totals:
            raise ResolutionError(
                "Les lignes regroupées ne correspondent pas aux attributions "
                f"initiales : attendu={annual_totals}, observé={result_totals}"
            )

        summary = [
            (int(year), status, identifier_type, int(line_count), int(identity_count))
            for year, status, identifier_type, line_count, identity_count in connection.execute(
                """
                SELECT
                    year,
                    status,
                    normalized_type,
                    sum(source_line_count),
                    count(*) FILTER (WHERE status = 'resolved')
                FROM holder_identities
                GROUP BY year, status, normalized_type
                ORDER BY year, normalized_type NULLS LAST, status
                """
            ).fetchall()
        ]
        parquet_path = stage_dir / OUTPUT_FILENAMES[0]
        report_path = stage_dir / OUTPUT_FILENAMES[1]
        connection.execute(
            "COPY holder_identities TO "
            f"{_sql_path(parquet_path)} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        report_path.write_text(
            _render_report(source, annual_totals, summary), encoding="utf-8"
        )
        _publish_outputs(stage_dir, output_dir)
        return annual_totals
    except _PublicationRollbackError as error:
        preserve_stage = True
        raise ResolutionError(f"Écriture des sorties impossible : {error}") from error
    except duckdb.Error as error:
        raise ResolutionError(f"Préparation des identités impossible : {error}") from error
    except OSError as error:
        raise ResolutionError(f"Écriture des sorties impossible : {error}") from error
    finally:
        if connection is not None:
            connection.close()
        shutil.rmtree(spill_dir)
        if stage_dir.exists() and not preserve_stage:
            shutil.rmtree(stage_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rapproche localement les identifiants typés des titulaires."
    )
    parser.add_argument(
        "--input", type=Path, default=Path("data/prepared/decp.parquet")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/prepared"))
    args = parser.parse_args(argv)
    try:
        annual_totals = prepare(args.input, args.output_dir)
    except ResolutionError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    for year, total in sorted(annual_totals.items()):
        print(f"{year}: {total} lignes d'attribution initiale traitées")
    print(f"Sorties générées dans {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
