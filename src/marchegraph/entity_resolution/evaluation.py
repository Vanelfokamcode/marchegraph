from __future__ import annotations

import random
from collections import Counter
from typing import Any

LABELS = {"", "correct", "incorrect", "indeterminate"}
YEARS = (2024, 2025)


class EvaluationError(Exception):
    pass


def select_groups(
    candidates: dict[int, list[tuple[str, str, int]]],
    *,
    per_year: int = 50,
    seed: int = 42,
) -> list[dict[str, Any]]:
    if per_year < 1:
        raise EvaluationError("La taille de l'échantillon doit être positive.")
    rng = random.Random(seed)
    sample: list[dict[str, Any]] = []
    for year in YEARS:
        population = sorted(candidates.get(year, []))
        if len(population) < per_year:
            raise EvaluationError(
                f"Échantillon impossible pour {year} : {len(population)} groupes "
                f"disponibles, {per_year} requis."
            )
        if len(set(population)) != len(population):
            raise EvaluationError(f"Groupes canoniques dupliqués pour {year}.")
        selected = sorted(rng.sample(population, per_year))
        for index, (identifier_type, identifier_value, line_count) in enumerate(
            selected, start=1
        ):
            sample.append(
                {
                    "sample_id": f"{year}-{index:03d}",
                    "year": year,
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "source_line_count": line_count,
                    "distinct_name_count": 0,
                    "manual_review_label": "",
                    "reviewer_notes": "",
                }
            )
    return sample


def validate_sample(
    rows: list[dict[str, Any]], *, per_year: int = 50
) -> None:
    expected_count = len(YEARS) * per_year
    if len(rows) != expected_count:
        raise EvaluationError(
            f"L'échantillon doit contenir {expected_count} groupes, "
            f"observé : {len(rows)}."
        )
    ids: set[str] = set()
    keys: set[tuple[int, str, str]] = set()
    year_counts: Counter[int] = Counter()
    for row in rows:
        sample_id = row["sample_id"]
        year = int(row["year"])
        identifier_type = row["identifier_type"]
        identifier_value = row["identifier_value"]
        label = row.get("manual_review_label", "")
        if sample_id in ids:
            raise EvaluationError(f"Identifiant d'échantillon dupliqué : {sample_id}.")
        if year not in YEARS:
            raise EvaluationError(f"Année hors périmètre dans l'échantillon : {year}.")
        if not identifier_type or not identifier_value:
            raise EvaluationError(f"Clé canonique incomplète : {sample_id}.")
        if label not in LABELS:
            raise EvaluationError(
                f"Label invalide pour {sample_id} : {label!r}. "
                "Valeurs permises : correct, incorrect, indeterminate ou vide."
            )
        key = (year, identifier_type, identifier_value)
        if key in keys:
            raise EvaluationError(f"Groupe canonique dupliqué : {sample_id}.")
        ids.add(sample_id)
        keys.add(key)
        year_counts[year] += 1
    if any(year_counts[year] != per_year for year in YEARS):
        raise EvaluationError(
            f"L'échantillon doit contenir {per_year} groupes par année ; "
            f"observé : {dict(year_counts)}."
        )


def _percent(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{100 * numerator / denominator:.2f}".replace(".", ",") + " %"


def render_report(
    sample_rows: list[dict[str, Any]],
    unresolved_rows: list[tuple[int, str, str | None, int]],
    *,
    seed: int = 42,
    per_year: int = 50,
) -> str:
    validate_sample(sample_rows, per_year=per_year)
    selected_by_type: Counter[tuple[int, str]] = Counter()
    variants_by_type: Counter[tuple[int, str]] = Counter()
    for row in sample_rows:
        key = (int(row["year"]), row["identifier_type"])
        selected_by_type[key] += 1
        if int(row["distinct_name_count"]) > 1:
            variants_by_type[key] += 1

    lines = [
        "# Évaluation de la résolution des identités titulaires",
        "",
        f"Échantillon reproductible : {per_year} groupes par année, graine {seed}.",
        "Périmètre : groupes résolus par identifiant typé dans les attributions",
        "initiales 2024 et 2025. La revue manuelle est réalisée par le propriétaire",
        "du projet.",
        "",
        "Labels : `correct` si les éléments disponibles confirment un seul",
        "titulaire, `incorrect` si le groupe mélange des titulaires distincts,",
        "`indeterminate` si les éléments ne suffisent pas. Les cas indéterminés",
        "et les labels encore vides sont exclus du dénominateur de précision,",
        "mais rapportés séparément.",
        "",
        "| Année | Groupes sélectionnés | Revue terminée | Corrects | Incorrects | Indéterminés | En attente | Dénominateur précision | Précision observée |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    overall = Counter()
    for year in YEARS:
        rows = [row for row in sample_rows if int(row["year"]) == year]
        counts = Counter(row["manual_review_label"] for row in rows)
        reviewed = sum(counts[label] for label in ("correct", "incorrect", "indeterminate"))
        denominator = counts["correct"] + counts["incorrect"]
        for key in ("correct", "incorrect", "indeterminate"):
            overall[key] += counts[key]
        overall["pending"] += counts[""]
        lines.append(
            f"| {year} | {len(rows)} | {reviewed} | {counts['correct']} | "
            f"{counts['incorrect']} | {counts['indeterminate']} | "
            f"{counts['']} | {denominator} | "
            f"{_percent(counts['correct'], denominator)} |"
        )
    overall_denominator = overall["correct"] + overall["incorrect"]
    lines.extend(
        [
            f"| **Total** | {len(sample_rows)} | "
            f"{overall['correct'] + overall['incorrect'] + overall['indeterminate']} | "
            f"{overall['correct']} | {overall['incorrect']} | "
            f"{overall['indeterminate']} | {overall['pending']} | "
            f"{overall_denominator} | "
            f"{_percent(overall['correct'], overall_denominator)} |",
            "",
            "La précision est le nombre de groupes `correct` divisé par les",
            "groupes décidables (`correct` + `incorrect`). Elle ne mesure pas le",
            "rappel ni les rapprochements manqués. Les résultats restent",
            "provisoires tant que des groupes sont en attente.",
            "",
            "## Composition de l'échantillon et variantes de noms",
            "",
            "| Année | Type d'identifiant | Groupes sélectionnés | Groupes avec plusieurs noms distincts |",
            "|---:|---|---:|---:|",
        ]
    )
    for year, identifier_type in sorted(selected_by_type):
        lines.append(
            f"| {year} | {identifier_type} | {selected_by_type[(year, identifier_type)]} | "
            f"{variants_by_type[(year, identifier_type)]} |"
        )
    lines.extend(
        [
            "",
            "La composition par type est descriptive ; l'échantillon ne permet",
            "pas de conclure sur la précision propre à chaque type. Les variantes",
            "observées sont détaillées dans `holder-review-name-variants.csv`.",
            "",
            "## Lignes non résolues hors échantillon",
            "",
            "| Année | Type d'identifiant | Statut | Lignes |",
            "|---:|---|---|---:|",
        ]
    )
    for year, status, identifier_type, line_count in unresolved_rows:
        type_label = "NULL" if identifier_type is None else identifier_type
        lines.append(f"| {year} | {type_label} | {status} | {line_count} |")
    lines.extend(
        [
            "",
            "Les lignes non résolues sont rapportées séparément et ne sont pas",
            "des groupes négatifs dans l'évaluation de précision. Les labels,",
            "l'échantillon et les sorties restent locaux.",
            "",
        ]
    )
    return "\n".join(lines)
