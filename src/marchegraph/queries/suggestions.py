"""Exemples et saisie guidée tirés du contenu du graphe (module pur).

Les valeurs proposées viennent de `graph.dimension_values` ; la saisie guidée
n'accepte que ces valeurs et produit une requête du catalogue validée.
"""
from __future__ import annotations

from dataclasses import dataclass

from marchegraph.queries.catalogue import (
    DEFAULT_LIMIT,
    CatalogueQuery,
    CatalogueRefusal,
    validate,
)
from marchegraph.queries.interpretation import DEFAULT_YEAR

REGION_NAMES = {
    "01": "Guadeloupe", "02": "Martinique", "03": "Guyane", "04": "La Réunion",
    "06": "Mayotte", "11": "Île-de-France", "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté", "28": "Normandie", "32": "Hauts-de-France",
    "44": "Grand Est", "52": "Pays de la Loire", "53": "Bretagne",
    "75": "Nouvelle-Aquitaine", "76": "Occitanie", "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur", "94": "Corse",
    "975": "Saint-Pierre-et-Miquelon", "977": "Saint-Barthélemy",
    "978": "Saint-Martin", "986": "Wallis-et-Futuna", "987": "Polynésie française",
    "988": "Nouvelle-Calédonie",
}
EXAMPLE_THEME = "les travaux"


@dataclass(frozen=True)
class Value:
    value: str
    label: str
    market_count: int


@dataclass(frozen=True)
class Suggestions:
    """Valeurs présentes dans le graphe, les plus fréquentes d'abord."""

    year: int
    years: tuple[Value, ...] = ()
    regions: tuple[Value, ...] = ()
    cpv_families: tuple[Value, ...] = ()
    procedures: tuple[Value, ...] = ()
    natures: tuple[Value, ...] = ()
    buyers: tuple[Value, ...] = ()  # les plus actifs de `year`


def example_year(years: tuple[Value, ...]) -> int:
    present = [int(v.value) for v in years if v.market_count]
    return max(present) if present else DEFAULT_YEAR


def examples(s: Suggestions) -> list[str]:
    """Questions d'exemple, toutes reconnues par `interpret`, construites sur les données."""
    year = s.year
    questions = [f"Quels acheteurs ont attribué le plus de marchés en {year} ?"]
    buyer = next((b for b in s.buyers if len(b.value) == 14 and b.value.isdigit()), None)
    if buyer is not None:
        questions.append(f"Quels titulaires reviennent le plus chez l'acheteur "
                         f"{buyer.value} en {year} ?")
    if s.regions:
        questions.append(f"Quels marchés concernent {EXAMPLE_THEME} en "
                         f"{s.regions[0].label} en {year} ?")
    questions += [
        f"Quel montant total par famille CPV en {year} ?",
        f"Quelle durée moyenne par famille CPV en {year} ?",
        f"Quels marchés ont été modifiés en {year} ?",
        f"Quelles procédures et natures de marché sont utilisées en {year} ?",
        f"Quels titulaires travaillent avec plusieurs acheteurs en {year} ?",
        "Quels fournisseurs ont plusieurs écritures de leur nom ?",
        "Quelles données sont manquantes ou incohérentes ?",
    ]
    return questions


def guided_query(
    s: Suggestions,
    *,
    measure: str,
    grouping: str,
    year: int,
    region_code: str | None = None,
    cpv_family: str | None = None,
    procedure: str | None = None,
    nature: str | None = None,
    buyer_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> CatalogueQuery:
    """Requête du catalogue ; toute valeur non proposée est refusée."""
    offered = {
        "année": (str(year), s.years),
        "région": (region_code, s.regions),
        "famille CPV": (cpv_family, s.cpv_families),
        "procédure": (procedure, s.procedures),
        "nature": (nature, s.natures),
        "acheteur": (buyer_id, s.buyers),
    }
    for name, (value, values) in offered.items():
        if value is not None and value not in {v.value for v in values}:
            raise CatalogueRefusal(f"Valeur non proposée pour le filtre {name} : {value}.")
    query = CatalogueQuery(
        measure, grouping, year=year, year_given=grouping != "annee",
        region_code=region_code, cpv_family=cpv_family, procedure=procedure,
        nature=nature, buyer_id=buyer_id, limit=limit,
    )
    validate(query)
    return query


def describe(query: CatalogueQuery, s: Suggestions) -> str:
    """Formulation lisible de la requête guidée, pour l'historique et le modèle."""
    labels = {
        "region_code": {v.value: v.label for v in s.regions},
        "buyer_id": {v.value: v.label for v in s.buyers},
        "cpv_family": {v.value: v.label for v in s.cpv_families},
    }
    parts = [] if query.grouping == "annee" else [str(query.year)]
    for name in ("region_code", "buyer_id", "cpv_family", "procedure", "nature"):
        value = getattr(query, name)
        if value is not None:
            parts.append(labels.get(name, {}).get(value, value))
    return f"{query.label} ({', '.join(parts)})" if parts else query.label
