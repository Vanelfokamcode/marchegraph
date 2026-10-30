"""Catalogue des questions composables : mesure × regroupement × filtres.

Module pur : ni Neo4j ni interface. Une combinaison hors catalogue lève
`CatalogueRefusal` avec un motif en français ; l'appelant s'abstient.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from marchegraph.queries.interpretation import REGIONS, SUPPORTED_YEARS

MEASURES = {
    "nombre_marches": "Nombre de marchés",
    "montant_total": "Montant total déclaré",
    "montant_moyen": "Montant moyen déclaré",
    "duree_moyenne": "Durée moyenne (mois)",
    "nombre_modifications": "Nombre de modifications",
}

GROUPINGS = {
    "aucun": "Ensemble",
    "acheteur": "Acheteur",
    "titulaire": "Titulaire",
    "famille_cpv": "Famille CPV",
    "region": "Région de l'acheteur",
    "procedure": "Procédure",
    "nature": "Nature",
    "annee": "Année",
}

DEFAULT_LIMIT = 10
MAX_LIMIT = 100


class CatalogueRefusal(ValueError):
    """Combinaison non prise en charge ; le message explique pourquoi."""


@dataclass(frozen=True)
class CatalogueQuery:
    measure: str
    grouping: str = "aucun"
    year: int = 2025
    year_given: bool = False
    region_code: str | None = None
    buyer_id: str | None = None
    holder_type: str | None = None
    holder_value: str | None = None
    cpv_family: str | None = None
    procedure: str | None = None
    nature: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    theme: str | None = None
    limit: int = DEFAULT_LIMIT

    @property
    def label(self) -> str:
        if self.grouping == "aucun":
            return MEASURES.get(self.measure, self.measure)
        return f"{MEASURES.get(self.measure, self.measure)} par " \
               f"{GROUPINGS.get(self.grouping, self.grouping).lower()}"


def validate(query: CatalogueQuery) -> None:
    """Lève `CatalogueRefusal` si la combinaison n'est pas prise en charge."""
    if query.measure not in MEASURES:
        raise CatalogueRefusal(f"Mesure inconnue : {query.measure}.")
    if query.grouping not in GROUPINGS:
        raise CatalogueRefusal(f"Regroupement inconnu : {query.grouping}.")
    if query.year not in SUPPORTED_YEARS:
        raise CatalogueRefusal("Seules les années 2024 et 2025 sont disponibles.")
    if not 1 <= query.limit <= MAX_LIMIT:
        raise CatalogueRefusal(f"Le nombre de lignes doit être entre 1 et {MAX_LIMIT}.")
    if query.grouping == "annee" and query.year_given:
        raise CatalogueRefusal(
            "Un regroupement par année ne peut pas être limité à une seule année."
        )
    if query.measure == "nombre_modifications" and query.grouping in (
        "titulaire", "procedure"
    ):
        raise CatalogueRefusal(
            "Le nombre de modifications ne peut pas être réparti par titulaire "
            "ou par procédure : le lien entre version et titulaire est ambigu."
        )
    has_amount_range = query.amount_min is not None or query.amount_max is not None
    if has_amount_range and query.measure == "duree_moyenne":
        raise CatalogueRefusal(
            "Une tranche de montant ne se combine pas avec la durée moyenne."
        )
    if (
        query.amount_min is not None
        and query.amount_max is not None
        and query.amount_min > query.amount_max
    ):
        raise CatalogueRefusal("Le montant minimum dépasse le montant maximum.")
    if query.grouping == "titulaire" and not query.year_given:
        raise CatalogueRefusal(
            "Un regroupement par titulaire exige une année explicite."
        )
    if query.region_code is not None and query.region_code not in REGIONS:
        raise CatalogueRefusal(f"Code de région inconnu : {query.region_code}.")
    if query.cpv_family is not None and not re.fullmatch(r"\d{3}", query.cpv_family):
        raise CatalogueRefusal("Une famille CPV s'écrit avec trois chiffres.")
    if (query.holder_type is None) != (query.holder_value is None):
        raise CatalogueRefusal(
            "Un titulaire se désigne par son type et sa valeur d'identifiant."
        )
    for name in ("buyer_id", "holder_value", "procedure", "nature", "theme"):
        value = getattr(query, name)
        if value is not None and not value.strip():
            raise CatalogueRefusal(f"Le filtre {name} est vide.")
