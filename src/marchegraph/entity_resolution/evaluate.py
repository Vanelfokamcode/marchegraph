from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from evaluation import EvaluationError, render_report, select_groups, validate_sample
from identity import normalize_identifier_type, normalize_identifier_value

SAMPLE_FILENAME = "holder-review-sample.csv"
VARIANTS_FILENAME = "holder-review-name-variants.csv"
REPORT_FILENAME = "holder-evaluation-report.md"
SAMPLE_FIELDS = (
    "sample_id",
    "year",
    "identifier_type",
    "identifier_value",
    "source_line_count",
    "distinct_name_count",
    "manual_review_label",
    "reviewer_notes",
)
VARIANT_FIELDS = ("sample_id", "holder_name", "source_line_count")
SAMPLE_PER_YEAR = 50
SAMPLE_SEED = 42
SOURCE_FILTER = (
    "modification_id = 0 "
    "AND dateNotification >= DATE '2024-01-01' "
    "AND dateNotification < DATE '2026-01-01'"
)
REQUIRED_SOURCE_COLUMNS = {
    "dateNotification",
    "modification_id",
    "titulaire_typeIdentifiant",
    "titulaire_id",
    "titulaire_nom",
}


class ReviewError(Exception):
    pass


def _sql_path(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _load_sample(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if tuple(reader.fieldnames or ()) != SAMPLE_FIELDS:
                raise ReviewError(
                    f"Colonnes invalides dans {path}; attendues : "
                    + ", ".join(SAMPLE_FIELDS)
                )
            rows = list(reader)
    except OSError as error:
        raise ReviewError(f"Lecture de l'échantillon impossible : {error}") from error
    try:
        for row in rows:
            row["year"] = int(row["year"])
            row["source_line_count"] = int(row["source_line_count"])
            row["distinct_name_count"] = int(row["distinct_name_count"])
    except (TypeError, ValueError) as error:
        raise ReviewError(f"Valeur numérique invalide dans {path}.") from error
    try:
        validate_sample(rows, per_year=SAMPLE_PER_YEAR)
    except EvaluationError as error:
        raise ReviewError(str(error)) from error
    return rows


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_candidates(
    connection: duckdb.DuckDBPyConnection, identity_path: Path
) -> dict[int, list[tuple[str, str, int]]]:
    try:
        result = connection.execute(
            "SELECT year, normalized_type, normalized_value, source_line_count "
            "FROM read_parquet(?) WHERE status = 'resolved' AND year IN (2024, 2025)",
            [str(identity_path)],
        )
        candidates: dict[int, list[tuple[str, str, int]]] = {2024: [], 2025: []}
        while rows := result.fetchmany(10_000):
            for year, identifier_type, identifier_value, line_count in rows:
                candidates[int(year)].append(
                    (identifier_type, identifier_value, int(line_count))
                )
    except duckdb.Error as error:
        raise ReviewError(f"Lecture des identités résolues impossible : {error}") from error
    return candidates


def _unresolved_summary(
    connection: duckdb.DuckDBPyConnection, identity_path: Path
) -> list[tuple[int, str, str | None, int]]:
    try:
        rows = connection.execute(
            """
            SELECT year, status, normalized_type, sum(source_line_count)
            FROM read_parquet(?)
            WHERE status != 'resolved' AND year IN (2024, 2025)
            GROUP BY year, status, normalized_type
            ORDER BY year, normalized_type NULLS LAST, status
            """,
            [str(identity_path)],
        ).fetchall()
    except duckdb.Error as error:
        raise ReviewError(f"Lecture des lignes non résolues impossible : {error}") from error
    return [
        (int(year), status, identifier_type, int(line_count))
        for year, status, identifier_type, line_count in rows
    ]


def _add_name_variants(
    connection: duckdb.DuckDBPyConnection,
    sample_rows: list[dict[str, Any]],
    source_path: Path,
) -> list[dict[str, Any]]:
    group_to_sample = {
        (
            int(row["year"]),
            row["identifier_type"],
            row["identifier_value"],
        ): row
        for row in sample_rows
    }
    variants: dict[str, dict[str | None, int]] = {
        row["sample_id"]: {} for row in sample_rows
    }
    grouped_source = connection.execute(
        "SELECT year(dateNotification), titulaire_typeIdentifiant, titulaire_id, "
        "titulaire_nom, count(*) "
        f"FROM prepared_decp WHERE {SOURCE_FILTER} "
        "GROUP BY year(dateNotification), titulaire_typeIdentifiant, "
        "titulaire_id, titulaire_nom"
    )
    while rows := grouped_source.fetchmany(10_000):
        for year, raw_type, raw_value, holder_name, source_line_count in rows:
            identifier_type = normalize_identifier_type(raw_type)
            identifier_value = normalize_identifier_value(raw_value)
            if identifier_type is None or identifier_value is None:
                continue
            sample_row = group_to_sample.get(
                (int(year), identifier_type, identifier_value)
            )
            if sample_row is None:
                continue
            sample_id = sample_row["sample_id"]
            variants[sample_id][holder_name] = (
                variants[sample_id].get(holder_name, 0) + int(source_line_count)
            )

    variant_rows: list[dict[str, Any]] = []
    for sample_row in sample_rows:
        name_counts = variants[sample_row["sample_id"]]
        total_lines = sum(name_counts.values())
        expected_lines = int(sample_row["source_line_count"])
        if total_lines != expected_lines:
            raise ReviewError(
                f"Les lignes d'identité pour {sample_row['sample_id']} ne "
                f"correspondent pas au Parquet : attendu={expected_lines}, "
                f"observé={total_lines}."
            )
        sample_row["distinct_name_count"] = sum(
            1 for holder_name in name_counts if holder_name is not None
        )
        for holder_name, line_count in sorted(
            name_counts.items(), key=lambda item: (item[0] is None, item[0] or "")
        ):
            variant_rows.append(
                {
                    "sample_id": sample_row["sample_id"],
                    "holder_name": "" if holder_name is None else holder_name,
                    "source_line_count": line_count,
                }
            )
    return variant_rows


def prepare_review(
    source_path: Path,
    identity_path: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path, int]:
    source_path = source_path.expanduser().resolve()
    identity_path = identity_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source_path.is_file():
        raise ReviewError(f"Le Parquet préparé est absent ou illisible : {source_path}")
    if not identity_path.is_file():
        raise ReviewError(f"Le Parquet des identités est absent ou illisible : {identity_path}")
    if source_path == identity_path:
        raise ReviewError("Les chemins source et identités doivent être distincts.")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    spill_dir = Path(
        tempfile.mkdtemp(prefix=".holder-review-duckdb-", dir=output_dir.parent)
    )
    stage_dir = Path(
        tempfile.mkdtemp(prefix=".holder-review-stage-", dir=output_dir.parent)
    )
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(
            config={
                "memory_limit": "768MB",
                "threads": "1",
                "temp_directory": str(spill_dir),
            }
        )
        try:
            connection.read_parquet(str(source_path)).create_view("prepared_decp")
            source_columns = {
                row[0]
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM prepared_decp"
                ).fetchall()
            }
            identity_columns = {
                row[0]
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM read_parquet(?)",
                    [str(identity_path)],
                ).fetchall()
            }
        except duckdb.Error as error:
            raise ReviewError(f"Lecture des fichiers Parquet impossible : {error}") from error
        missing_source = REQUIRED_SOURCE_COLUMNS - source_columns
        required_identity = {
            "year",
            "status",
            "normalized_type",
            "normalized_value",
            "source_line_count",
        }
        missing_identity = required_identity - identity_columns
        if missing_source or missing_identity:
            missing = sorted(missing_source | missing_identity)
            raise ReviewError(
                "Colonnes requises absentes : " + ", ".join(missing)
            )

        candidates = _read_candidates(connection, identity_path)
        sample_path = output_dir / SAMPLE_FILENAME
        variants_path = output_dir / VARIANTS_FILENAME
        report_path = output_dir / REPORT_FILENAME
        if sample_path.exists():
            sample_rows = _load_sample(sample_path)
        else:
            try:
                sample_rows = select_groups(
                    candidates,
                    per_year=SAMPLE_PER_YEAR,
                    seed=SAMPLE_SEED,
                )
            except EvaluationError as error:
                raise ReviewError(str(error)) from error

        candidate_maps = {
            year: {
                (identifier_type, identifier_value): line_count
                for identifier_type, identifier_value, line_count in groups
            }
            for year, groups in candidates.items()
        }
        for row in sample_rows:
            candidate_count = candidate_maps.get(int(row["year"]), {}).get(
                (row["identifier_type"], row["identifier_value"])
            )
            if candidate_count is None or candidate_count != int(row["source_line_count"]):
                raise ReviewError(
                    f"Le groupe {row['sample_id']} ne correspond pas au Parquet "
                    "de résolution courant."
                )

        variant_rows = _add_name_variants(connection, sample_rows, source_path)
        unresolved = _unresolved_summary(connection, identity_path)
        report = render_report(
            sample_rows,
            unresolved,
            seed=SAMPLE_SEED,
            per_year=SAMPLE_PER_YEAR,
        )
        sample_created = not sample_path.exists()
        if sample_created:
            _write_csv(stage_dir / SAMPLE_FILENAME, SAMPLE_FIELDS, sample_rows)
        _write_csv(stage_dir / VARIANTS_FILENAME, VARIANT_FIELDS, variant_rows)
        (stage_dir / REPORT_FILENAME).write_text(report, encoding="utf-8")

        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in (VARIANTS_FILENAME, REPORT_FILENAME):
            os.replace(stage_dir / filename, output_dir / filename)
        if sample_created:
            os.replace(stage_dir / SAMPLE_FILENAME, sample_path)

        pending = sum(
            not row["manual_review_label"] for row in sample_rows
        )
        return sample_path, variants_path, report_path, pending
    except duckdb.Error as error:
        raise ReviewError(f"Évaluation impossible : {error}") from error
    except OSError as error:
        raise ReviewError(f"Écriture des sorties impossible : {error}") from error
    finally:
        if connection is not None:
            connection.close()
        shutil.rmtree(spill_dir)
        shutil.rmtree(stage_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prépare et rapporte la revue locale de précision des titulaires."
    )
    parser.add_argument(
        "--input", type=Path, default=Path("data/prepared/decp.parquet")
    )
    parser.add_argument(
        "--identities",
        type=Path,
        default=Path("data/prepared/holder-identities.parquet"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/prepared/holder-review")
    )
    args = parser.parse_args(argv)
    try:
        sample_path, variants_path, report_path, pending = prepare_review(
            args.input, args.identities, args.output_dir
        )
    except (ReviewError, EvaluationError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    print(f"Échantillon à renseigner : {sample_path}")
    print(f"Variantes de noms à consulter : {variants_path}")
    print(f"Rapport : {report_path}")
    if pending:
        print(
            f"{pending} groupes restent à examiner ; renseignez manual_review_label "
            "avec correct, incorrect ou indeterminate, puis relancez cette commande."
        )
    else:
        print("Tous les groupes de l'échantillon ont reçu un label.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
