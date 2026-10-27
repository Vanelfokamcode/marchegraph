from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import duckdb

EXPECTED_SNAPSHOT_SHA256 = (
    "b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0"
)
EXPECTED_COUNTS = {
    2024: {
        "initial_award_rows": 325_470,
        "initial_award_distinct_uids": 288_057,
        "modification_rows": 220_519,
        "modification_distinct_uids": 89_737,
    },
    2025: {
        "initial_award_rows": 315_998,
        "initial_award_distinct_uids": 273_425,
        "modification_rows": 271_210,
        "modification_distinct_uids": 104_722,
    },
}
QUALITY_FIELDS = (
    "acheteur_id",
    "titulaire_id",
    "montant",
    "codeCPV",
    "objet",
    "lieuExecution_code",
    "acheteur_region_code",
    "offresRecues",
)
EXPECTED_QUALITY = {
    2024: {
        "total_rows": 325_470,
        "missing_values": {
            "acheteur_id": 0,
            "titulaire_id": 38_442,
            "montant": 1_864,
            "codeCPV": 2,
            "objet": 116,
            "lieuExecution_code": 245,
            "acheteur_region_code": 1_687,
            "offresRecues": 48_159,
        },
        "amount_anomalies": {None: 317_390, "aberrant": 1_184, "suspect": 6_896},
        "publication_delay": {
            "missing_publication_dates": 30,
            "delay_count": 325_440,
            "negative_count": 12_244,
            "negative_rate_percent": 3.76,
            "quantiles_days": {"p10": 0.0, "p50": 25.0, "p90": 266.0, "p99": 751.61},
        },
    },
    2025: {
        "total_rows": 315_998,
        "missing_values": {
            "acheteur_id": 0,
            "titulaire_id": 4_930,
            "montant": 557,
            "codeCPV": 6,
            "objet": 0,
            "lieuExecution_code": 5,
            "acheteur_region_code": 2_177,
            "offresRecues": 43_116,
        },
        "amount_anomalies": {None: 308_003, "aberrant": 1_184, "suspect": 6_811},
        "publication_delay": {
            "missing_publication_dates": 33,
            "delay_count": 315_965,
            "negative_count": 13_395,
            "negative_rate_percent": 4.24,
            "quantiles_days": {"p10": 0.0, "p50": 20.0, "p90": 194.0, "p99": 458.0},
        },
    },
}
OUTPUT_FILENAMES = ("decp.parquet", "manifest.json", "quality-report.md")
REQUIRED_COLUMNS = {
    "dateNotification",
    "modification_id",
    "uid",
    *QUALITY_FIELDS,
    "montant_anomalie",
    "datePublicationDonnees",
}


class PipelineError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _annual_counts(
    connection: duckdb.DuckDBPyConnection, view_name: str = "source_decp"
) -> dict[int, dict[str, int]]:
    rows = connection.execute(
        f"""
        SELECT
            year(dateNotification) AS year,
            count(*) FILTER (WHERE modification_id = 0) AS initial_award_rows,
            count(DISTINCT uid) FILTER (WHERE modification_id = 0)
                AS initial_award_distinct_uids,
            count(*) FILTER (WHERE modification_id > 0) AS modification_rows,
            count(DISTINCT uid) FILTER (WHERE modification_id > 0)
                AS modification_distinct_uids
        FROM {view_name}
        WHERE dateNotification >= DATE '2024-01-01'
          AND dateNotification < DATE '2026-01-01'
        GROUP BY year(dateNotification)
        ORDER BY year(dateNotification)
        """
    ).fetchall()
    return {
        int(year): {
            "initial_award_rows": int(initial_rows),
            "initial_award_distinct_uids": int(initial_uids),
            "modification_rows": int(modification_rows),
            "modification_distinct_uids": int(modification_uids),
        }
        for year, initial_rows, initial_uids, modification_rows, modification_uids in rows
    }


def _quality_metrics(
    connection: duckdb.DuckDBPyConnection, view_name: str
) -> dict[int, dict[str, Any]]:
    missing_sql = ", ".join(
        f"count(*) FILTER (WHERE {field} IS NULL) AS {field}"
        for field in QUALITY_FIELDS
    )
    missing_rows = connection.execute(
        f"""
        SELECT year(dateNotification) AS year, count(*) AS total_rows, {missing_sql}
        FROM {view_name}
        WHERE modification_id = 0
          AND dateNotification >= DATE '2024-01-01'
          AND dateNotification < DATE '2026-01-01'
        GROUP BY year(dateNotification)
        ORDER BY year(dateNotification)
        """
    ).fetchall()
    metrics: dict[int, dict[str, Any]] = {
        int(row[0]): {
            "total_rows": int(row[1]),
            "missing_values": {
                field: int(value) for field, value in zip(QUALITY_FIELDS, row[2:])
            },
            "amount_anomalies": {},
            "publication_delay": {},
        }
        for row in missing_rows
    }

    for year, category, count in connection.execute(
        f"""
        SELECT year(dateNotification), montant_anomalie, count(*)
        FROM {view_name}
        WHERE modification_id = 0
          AND dateNotification >= DATE '2024-01-01'
          AND dateNotification < DATE '2026-01-01'
        GROUP BY year(dateNotification), montant_anomalie
        """
    ).fetchall():
        metrics[int(year)]["amount_anomalies"][category] = int(count)

    delay_rows = connection.execute(
        f"""
        WITH delays AS (
            SELECT
                year(dateNotification) AS year,
                datePublicationDonnees IS NULL AS publication_date_missing,
                date_diff('day', dateNotification, datePublicationDonnees) AS delay_days
            FROM {view_name}
            WHERE modification_id = 0
              AND dateNotification >= DATE '2024-01-01'
              AND dateNotification < DATE '2026-01-01'
        )
        SELECT
            year,
            count(*) FILTER (WHERE publication_date_missing) AS missing_publication_dates,
            count(delay_days) AS delay_count,
            count(*) FILTER (WHERE delay_days < 0) AS negative_count,
            quantile_cont(delay_days, 0.10) AS p10,
            quantile_cont(delay_days, 0.50) AS p50,
            quantile_cont(delay_days, 0.90) AS p90,
            quantile_cont(delay_days, 0.99) AS p99
        FROM delays
        GROUP BY year
        ORDER BY year
        """
    ).fetchall()
    for year, missing_dates, delay_count, negative_count, p10, p50, p90, p99 in delay_rows:
        year_metrics = metrics[int(year)]
        delay_count = int(delay_count)
        negative_count = int(negative_count)
        year_metrics["publication_delay"] = {
            "missing_publication_dates": int(missing_dates),
            "delay_count": delay_count,
            "negative_count": negative_count,
            "negative_rate_percent": round(
                100.0 * negative_count / delay_count, 2
            )
            if delay_count
            else 0.0,
            "quantiles_days": {
                key: round(float(value), 2) if value is not None else None
                for key, value in zip(("p10", "p50", "p90", "p99"), (p10, p50, p90, p99))
            },
        }
    return metrics


def _check_snapshot_baseline(
    source_sha256: str,
    counts: dict[int, dict[str, int]],
    quality_metrics: dict[int, dict[str, Any]],
) -> None:
    if source_sha256 != EXPECTED_SNAPSHOT_SHA256:
        raise PipelineError(
            "Le SHA-256 du snapshot ne correspond pas au snapshot profilé ; "
            "les baselines intégrées ne peuvent pas être vérifiées."
        )
    if counts != EXPECTED_COUNTS:
        raise PipelineError(
            "Les comptes calculés diffèrent des baselines vérifiées : "
            f"attendu={EXPECTED_COUNTS}, observé={counts}"
        )
    if quality_metrics != EXPECTED_QUALITY:
        raise PipelineError(
            "Les indicateurs qualité calculés diffèrent des baselines vérifiées : "
            f"attendu={EXPECTED_QUALITY}, observé={quality_metrics}"
        )


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    percentage = 100.0 * numerator / denominator
    if 0 < percentage < 0.01:
        return "<0,01 %"
    return f"{percentage:.2f}".replace(".", ",") + " %"


def _format_days(value: float | None) -> str:
    if value is None:
        return "n/a"
    rounded = round(value, 2)
    if rounded == 0:
        return "0"
    formatted = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return formatted.replace(".", ",")


def _render_report(
    counts: dict[int, dict[str, int]],
    quality_metrics: dict[int, dict[str, Any]],
) -> str:
    lines = [
        "# Préparation DECP — rapport de qualité",
        "",
        "Périmètre : lignes notifiées en 2024 et 2025, toutes régions.",
        "Les attributions initiales (`modification_id = 0`) et les lignes de",
        "modification (`modification_id > 0`) sont comptées séparément.",
        "Les indicateurs de qualité ci-dessous portent sur les attributions initiales.",
        "",
        "| Année | Type de ligne | Nombre de lignes | `uid` distincts |",
        "|---:|---|---:|---:|",
    ]
    for year in (2024, 2025):
        year_counts = counts.get(
            year,
            {
                "initial_award_rows": 0,
                "initial_award_distinct_uids": 0,
                "modification_rows": 0,
                "modification_distinct_uids": 0,
            },
        )
        lines.extend(
            [
                f"| {year} | Attribution initiale | "
                f"{year_counts['initial_award_rows']} | "
                f"{year_counts['initial_award_distinct_uids']} |",
                f"| {year} | Modification | "
                f"{year_counts['modification_rows']} | "
                f"{year_counts['modification_distinct_uids']} |",
            ]
        )
    lines.extend(
        [
            "",
            "Les comptes de `uid` distincts parmi les modifications ne sont pas",
            "des nombres de marchés distincts et ne sont pas ajoutés aux",
            "statistiques d'attribution initiale.",
            "",
            "## Valeurs manquantes",
            "",
            "Les taux sont calculés sur toutes les lignes d'attribution initiale",
            "de l'année ; les nombres indiquent le numérateur et le dénominateur.",
            "",
            "| Année | Champ | Valeurs manquantes | Total | Taux |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for year in (2024, 2025):
        year_metrics = quality_metrics.get(year)
        if year_metrics is None:
            continue
        total = year_metrics["total_rows"]
        for field in QUALITY_FIELDS:
            missing = year_metrics["missing_values"][field]
            lines.append(
                f"| {year} | `{field}` | {missing} | {total} | "
                f"{_format_percent(missing, total)} |"
            )

    lines.extend(
        [
            "",
            "## Anomalies de montant",
            "",
            "Les taux sont calculés sur toutes les lignes d'attribution initiale.",
            "`NULL` signifie que la source ne fournit pas de catégorie.",
            "",
            "| Année | Catégorie source | Nombre de lignes | Total | Taux |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for year in (2024, 2025):
        year_metrics = quality_metrics.get(year)
        if year_metrics is None:
            continue
        total = year_metrics["total_rows"]
        categories = year_metrics["amount_anomalies"]
        for category in sorted(categories, key=lambda value: (value is None, str(value))):
            count = categories[category]
            label = "NULL" if category is None else str(category)
            lines.append(
                f"| {year} | {label} | {count} | {total} | "
                f"{_format_percent(count, total)} |"
            )

    lines.extend(
        [
            "",
            "## Délais de publication",
            "",
            "Délai = `datePublicationDonnees` moins `dateNotification`, en jours.",
            "Les dates de publication manquantes sont comptées sur toutes les",
            "attributions initiales ; taux négatif et quantiles utilisent les",
            "seuls délais calculables. Les quantiles sont continus.",
            "",
            "| Année | Dates publication manquantes | Délais calculables | Délais négatifs | Taux négatif | p10 (j) | p50 (j) | p90 (j) | p99 (j) |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for year in (2024, 2025):
        year_metrics = quality_metrics.get(year)
        if year_metrics is None:
            continue
        delay = year_metrics["publication_delay"]
        quantiles = delay["quantiles_days"]
        quantile_values = [
            _format_days(quantiles[key]) for key in ("p10", "p50", "p90", "p99")
        ]
        lines.append(
            f"| {year} | {delay['missing_publication_dates']} | "
            f"{delay['delay_count']} | {delay['negative_count']} | "
            f"{_format_percent(delay['negative_count'], delay['delay_count'])} | "
            + " | ".join(quantile_values)
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_outputs(
    connection: duckdb.DuckDBPyConnection,
    source_path: Path,
    output_dir: Path,
    source_sha256: str,
    counts: dict[int, dict[str, int]],
    verify_baseline: bool,
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-stage-", dir=output_dir.parent)
    )
    preserve_stage = False
    try:
        parquet_path = stage_dir / "decp.parquet"
        manifest_path = stage_dir / "manifest.json"
        report_path = stage_dir / "quality-report.md"
        parquet_sql_path = parquet_path.as_posix().replace("'", "''")
        connection.execute(
            "COPY (SELECT * FROM source_decp "
            "WHERE dateNotification >= DATE '2024-01-01' "
            "AND dateNotification < DATE '2026-01-01') "
            f"TO '{parquet_sql_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        connection.read_parquet(str(parquet_path)).create_view("prepared_decp")
        prepared_counts = _annual_counts(connection, "prepared_decp")
        if prepared_counts != counts:
            raise PipelineError(
                "Les comptes du Parquet préparé diffèrent de ceux du snapshot source."
            )
        quality_metrics = _quality_metrics(connection, "prepared_decp")
        if verify_baseline:
            _check_snapshot_baseline(source_sha256, prepared_counts, quality_metrics)

        manifest: dict[str, Any] = {
            "source": {
                "path": source_path.as_posix(),
                "sha256": source_sha256,
                "size_bytes": source_path.stat().st_size,
                "extraction_date": None,
            },
            "outputs": {
                "prepared_parquet": (output_dir / "decp.parquet").as_posix(),
                "quality_report": (output_dir / "quality-report.md").as_posix(),
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            _render_report(prepared_counts, quality_metrics), encoding="utf-8"
        )

        if output_dir.exists() and not output_dir.is_dir():
            raise OSError(f"Le chemin de sortie n'est pas un dossier : {output_dir}")
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
                preserve_stage = True
                raise OSError(
                    f"Publication impossible ({error}); sauvegardes conservées "
                    f"dans {backup_dir}: {'; '.join(rollback_errors)}"
                ) from error
            raise
    finally:
        if stage_dir.exists() and not preserve_stage:
            shutil.rmtree(stage_dir)


def prepare(
    source: Path, output_dir: Path, *, verify_baseline: bool = True
) -> dict[int, dict[str, int]]:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_file():
        raise PipelineError(f"Le snapshot source est absent ou illisible : {source}")
    if source == output_dir or output_dir in source.parents:
        raise PipelineError("Le dossier de sortie ne peut pas contenir le snapshot source.")
    if source.parent == output_dir or source in output_dir.parents:
        raise PipelineError("Le chemin source et le dossier de sortie se chevauchent.")

    source_sha256 = sha256_file(source)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    spill_dir = Path(
        tempfile.mkdtemp(prefix=".decp-duckdb-", dir=output_dir.parent)
    )
    connection = duckdb.connect(
        config={
            "memory_limit": "768MB",
            "threads": "1",
            "temp_directory": str(spill_dir),
        }
    )
    try:
        try:
            connection.read_parquet(str(source)).create_view("source_decp")
            columns = {
                row[0]
                for row in connection.execute(
                    "DESCRIBE SELECT * FROM source_decp"
                ).fetchall()
            }
        except duckdb.Error as error:
            raise PipelineError(f"Lecture du snapshot impossible : {error}") from error
        missing_columns = REQUIRED_COLUMNS - columns
        if missing_columns:
            raise PipelineError(
                "Le snapshot ne contient pas les colonnes requises : "
                + ", ".join(sorted(missing_columns))
            )
        counts = _annual_counts(connection)
        if verify_baseline:
            if source_sha256 != EXPECTED_SNAPSHOT_SHA256:
                raise PipelineError(
                    "Le SHA-256 du snapshot ne correspond pas au snapshot profilé ; "
                    "les baselines intégrées ne peuvent pas être vérifiées."
                )
            if counts != EXPECTED_COUNTS:
                raise PipelineError(
                    "Les comptes calculés diffèrent des baselines vérifiées : "
                    f"attendu={EXPECTED_COUNTS}, observé={counts}"
                )
        try:
            _write_outputs(
                connection,
                source,
                output_dir,
                source_sha256,
                counts,
                verify_baseline,
            )
        except (OSError, duckdb.Error) as error:
            raise PipelineError(f"Écriture des sorties impossible : {error}") from error
        return counts
    finally:
        connection.close()
        shutil.rmtree(spill_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prépare localement le snapshot DECP 2024–2025."
    )
    parser.add_argument("--input", type=Path, default=Path("data/decp.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/prepared"))
    args = parser.parse_args(argv)
    try:
        counts = prepare(args.input, args.output_dir)
    except PipelineError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    for year, values in sorted(counts.items()):
        print(
            f"{year}: attributions initiales "
            f"{values['initial_award_rows']} lignes / "
            f"{values['initial_award_distinct_uids']} uid distincts ; "
            f"modifications {values['modification_rows']} lignes / "
            f"{values['modification_distinct_uids']} uid distincts"
        )
    print(f"Sorties générées dans {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
