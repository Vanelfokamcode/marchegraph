"""Jeu d'évaluation de l'epic 4.

Les lignes reprennent les fixtures de la story 3.9 ; seuls les identifiants
d'acheteur sont remplacés par des valeurs à 14 chiffres, comme dans les DECP,
pour que la question 2 puisse les citer. Aucune donnée DECP réelle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

SOURCE_ID = "epic-4-evaluation-fixture"

BUYER_A = "21000000000011"
BUYER_B = "21000000000022"
BUYER_2024 = "21000000000024"
BUYER_ORPHAN = "21000000000099"
HOLDER = "00000000000001"

COLUMNS = (
    "uid VARCHAR, id VARCHAR, modification_id SMALLINT, dateNotification DATE, "
    "nature VARCHAR, acheteur_id VARCHAR, acheteur_nom VARCHAR, "
    "acheteur_region_code VARCHAR, titulaire_id VARCHAR, "
    "titulaire_typeIdentifiant VARCHAR, titulaire_nom VARCHAR, objet VARCHAR, "
    "montant DOUBLE, type VARCHAR, codeCPV VARCHAR, procedure VARCHAR, "
    "dureeMois SMALLINT"
)

ROWS = [
    ("eval-market-2024", "initial-2024", 0, "2024-02-01", "Travaux", BUYER_2024,
     "Acheteur 2024", "11", HOLDER, "SIRET", "Titulaire Alpha", "Travaux 2024",
     50.0, "Marché", "45000000", "Appel d'offres", 12),
    ("eval-market-a", "initial-a-1", 0, "2025-02-01", "Travaux", BUYER_A,
     "Acheteur A", "11", HOLDER, "SIRET", "Titulaire Alpha", "Travaux de voirie",
     100.0, "Marché", "45000000", "Appel d'offres", 12),
    ("eval-market-a", "initial-a-2", 0, "2025-02-01", "Services", BUYER_A,
     "Acheteur A", None, HOLDER, "siret", "Alpha SAS", None, None, "Marché",
     "45000000", "Appel d'offres", None),
    ("eval-market-b", "initial-b", 0, "2025-03-01", "Fournitures", BUYER_B,
     "Acheteur B", "84", HOLDER, "SIRET", "Titulaire Alpha", "Fournitures",
     200.0, "Marché", "30000000", "Procédure adaptée", 6),
    ("eval-market-2024", "modification-2024", 1, "2024-06-01", "Travaux",
     BUYER_2024, "Acheteur 2024", "11", HOLDER, "SIRET", "Titulaire Alpha",
     "Avenant 2024", 55.0, "Marché", "45000000", "Appel d'offres", 13),
    ("eval-market-a", "modification-a", 1, "2025-04-01", "Travaux", BUYER_A,
     "Acheteur A", "11", HOLDER, "SIRET", "Titulaire Alpha", "Avenant voirie",
     110.0, "Marché", "45000000", "Appel d'offres", 14),
    ("eval-orphan", "modification-orphan", 1, "2025-05-01", None, BUYER_ORPHAN,
     "Acheteur sans marché initial", None, None, None, None, None, None, None,
     None, None, None),
]

IDENTITIES = [
    (2024, "resolved", "SIRET", HOLDER, 1),
    (2025, "resolved", "SIRET", HOLDER, 3),
]


@dataclass(frozen=True)
class ReferenceQuestion:
    question: str
    question_id: int | tuple[int, ...]
    params: dict = field(default_factory=dict)


REFERENCE_QUESTIONS = [
    ReferenceQuestion("Quels acheteurs ont attribué le plus de marchés en 2025 ?",
                      1, {"year": 2025}),
    ReferenceQuestion(f"Quels titulaires reviennent le plus chez l'acheteur "
                      f"{BUYER_A} en 2025 ?", 2,
                      {"buyer_id": BUYER_A, "year": 2025}),
    ReferenceQuestion("Quel montant total est attribué par famille de codes CPV "
                      "en 2025 ?", 3, {"year": 2025}),
    ReferenceQuestion("Quels marchés ont été modifiés après attribution en 2025, "
                      "et combien de fois ?", 4, {"year": 2025}),
    ReferenceQuestion("Quelles procédures sont utilisées selon la nature du "
                      "marché en 2025 ?", 5, {"year": 2025}),
    ReferenceQuestion("Quels titulaires travaillent avec plusieurs acheteurs "
                      "différents en 2025 ?", 6, {"year": 2025}),
    ReferenceQuestion("Quels marchés concernant la voirie ont été attribués en "
                      "Île-de-France en 2025 ?", 7,
                      {"theme": "voirie", "region_code": "11", "year": 2025}),
    ReferenceQuestion("Quelle est la durée moyenne des marchés par famille CPV "
                      "en 2025 ?", 8, {"year": 2025}),
    ReferenceQuestion("Quels fournisseurs apparaissent sous plusieurs écritures "
                      "de leur nom ?", 9, {}),
    ReferenceQuestion("Quels marchés ont des données manquantes ou "
                      "incohérentes ?", 10, {}),
]

# Validées par l'utilisateur le 2026-10-29.
ABSTENTION_QUESTIONS = [
    "Quelle est la météo à Paris ?",
    "Combien la mairie de Lyon a-t-elle payé à ses fournisseurs en 2025 ?",
    "Quels acheteurs ont attribué le plus de marchés en 2019 ?",
    "Quels acheteurs ont attribué le plus de marchés entre 2024 et 2025 ?",
    "Quel sera le montant des marchés en 2026 ?",
    "Quels titulaires reviennent le plus chez un acheteur donné ?",
    "Quels marchés concernent la voirie ?",
    "Quels marchés concernent la voirie en Bretagne et en Normandie ?",
    "Quelle entreprise est la plus corrompue ?",
    "Combien d'habitants compte la Bretagne ?",
]


def write_fixtures(directory: Path) -> tuple[Path, Path]:
    """Écrit le Parquet préparé et les identités titulaires du jeu d'évaluation."""
    source_path = directory / "evaluation-decp.parquet"
    identities_path = directory / "evaluation-holder-identities.parquet"
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE decp ({COLUMNS})")
        connection.executemany(
            f"INSERT INTO decp VALUES ({', '.join('?' * 17)})", ROWS
        )
        connection.execute("COPY decp TO ? (FORMAT PARQUET)", [str(source_path)])
        connection.execute(
            "CREATE TABLE identities (year INTEGER, status VARCHAR, "
            "normalized_type VARCHAR, normalized_value VARCHAR, "
            "source_line_count BIGINT)"
        )
        connection.executemany("INSERT INTO identities VALUES (?, ?, ?, ?, ?)",
                               IDENTITIES)
        connection.execute("COPY identities TO ? (FORMAT PARQUET)",
                           [str(identities_path)])
    finally:
        connection.close()
    return source_path, identities_path
