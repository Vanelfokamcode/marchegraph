"""Jeu d'évaluation de couverture, généré à partir du catalogue et des fixtures (pur).

Chaque cas porte les routes acceptées (question de référence ou requête du
catalogue avec leurs paramètres) ; aucune route signifie qu'une abstention est
attendue. Les références sont calculées ensuite par requête, jamais saisies.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from marchegraph.evaluation import dataset
from marchegraph.queries.catalogue import (
    GROUPINGS,
    MEASURES,
    CatalogueQuery,
    CatalogueRefusal,
    validate,
)
from marchegraph.queries.suggestions import Suggestions

CATALOGUE_ROUTE = 0

MEASURE_PHRASES = {
    "nombre_marches": "Quel est le nombre de marchés",
    "montant_total": "Quel est le montant total déclaré",
    "montant_moyen": "Quel est le montant moyen déclaré",
    "duree_moyenne": "Quelle est la durée moyenne des marchés",
    "nombre_modifications": "Quel est le nombre de modifications",
}
GROUPING_PHRASES = {
    "aucun": "",
    "acheteur": " par acheteur",
    "titulaire": " par titulaire",
    "famille_cpv": " par famille CPV",
    "region": " par région de l'acheteur",
    "procedure": " par procédure",
    "nature": " par nature de marché",
    "annee": " par année",
}
# Combinaisons du catalogue déjà couvertes par une question de référence.
EQUIVALENT_REFERENCES = {
    ("nombre_marches", "acheteur"): 1,
    ("montant_total", "famille_cpv"): 3,
    ("duree_moyenne", "famille_cpv"): 8,
}

PARAPHRASES = {
    1: ("Qui sont les principaux acheteurs en {y} ?",
        "Classement des acheteurs par nombre de marchés attribués en {y}",
        "Quels organismes publics passent le plus de marchés en {y} ?"),
    2: ("Quels fournisseurs reviennent le plus souvent chez l'acheteur {buyer} en {y} ?",
        "Avec quelles entreprises l'acheteur {buyer} travaille-t-il le plus en {y} ?"),
    3: ("Combien d'argent par famille CPV en {y} ?",
        "Montant attribué par catégorie CPV en {y}"),
    4: ("Quels contrats ont eu des avenants en {y} ?",
        "Combien de marchés ont été modifiés en {y} ?"),
    5: ("Quelles procédures de passation sont utilisées en {y} ?",
        "Répartition des marchés par nature en {y}"),
    6: ("Quels titulaires travaillent avec des acheteurs différents en {y} ?",
        "Quelles entreprises ont plusieurs clients publics en {y} ?"),
    7: ("Marchés liés à la voirie en Île-de-France en {y}",
        "Quels marchés portent sur la voirie dans la région Île-de-France en {y} ?"),
    8: ("Durée moyenne des contrats par famille CPV en {y}",
        "Combien de mois durent les marchés selon la famille CPV en {y} ?"),
    9: ("Quels titulaires ont des noms écrits de plusieurs façons ?",
        "Variantes de graphie des fournisseurs"),
    10: ("Quelles anomalies contiennent les données ?",
         "Où sont les données manquantes ?"),
}


@dataclass(frozen=True)
class Route:
    question_id: int | tuple[int, ...]
    params: tuple[tuple[str, object], ...] = ()

    @classmethod
    def of(cls, question_id, params: dict) -> Route:
        return cls(question_id, tuple(sorted(params.items())))


@dataclass(frozen=True)
class Case:
    category: str
    question: str
    routes: tuple[Route, ...] = ()  # vide : abstention attendue


def _reference_params(question_id: int, year: int) -> dict:
    return {
        2: {"buyer_id": dataset.BUYER_A, "year": year},
        7: {"theme": "voirie", "region_code": "11", "year": year},
        9: {},
        10: {},
    }.get(question_id, {"year": year})


def _catalogue_question(query: CatalogueQuery, s: Suggestions) -> str:
    text = MEASURE_PHRASES[query.measure] + GROUPING_PHRASES[query.grouping]
    labels = {v.value: v.label for v in s.regions}
    if query.region_code:
        text += f" en {labels[query.region_code]}"
    if query.cpv_family:
        text += f" pour la famille CPV {query.cpv_family}"
    if query.procedure:
        text += f" pour la procédure « {query.procedure} »"
    if query.nature:
        text += f" pour la nature « {query.nature} »"
    if query.buyer_id:
        text += f" chez l'acheteur {query.buyer_id}"
    if query.year_given:
        text += f" en {query.year}"
    return text + " ?"


def _catalogue_case(query: CatalogueQuery, s: Suggestions) -> Case:
    question = _catalogue_question(query, s)
    try:
        validate(query)
    except CatalogueRefusal:
        return Case("combinaison invalide", question)
    routes = [Route.of(CATALOGUE_ROUTE, {"query": query})]
    has_filter = any(getattr(query, name) for name in
                     ("region_code", "cpv_family", "procedure", "nature", "buyer_id"))
    equivalent = EQUIVALENT_REFERENCES.get((query.measure, query.grouping))
    if equivalent and not has_filter:
        routes.append(Route.of(equivalent, {"year": query.year}))
    return Case("catalogue", question, tuple(routes))


def build_cases(s: Suggestions) -> list[Case]:
    year = s.year
    cases = [
        Case("référence", item.question, (Route.of(item.question_id, item.params),))
        for item in dataset.REFERENCE_QUESTIONS
    ]
    for question_id, templates in PARAPHRASES.items():
        route = Route.of(question_id, _reference_params(question_id, year))
        cases += [Case("paraphrase", t.format(y=year, buyer=dataset.BUYER_A), (route,))
                  for t in templates]

    for measure in MEASURES:
        for grouping in GROUPINGS:
            query = CatalogueQuery(measure, grouping, year=year,
                                   year_given=grouping != "annee")
            cases.append(_catalogue_case(query, s))
        cases.append(_catalogue_case(
            CatalogueQuery(measure, "annee", year=year, year_given=True), s))
        base = CatalogueQuery(measure, year=year, year_given=True)
        filters = {
            "region_code": s.regions[:1], "cpv_family": s.cpv_families[:1],
            "procedure": s.procedures[:1], "nature": s.natures[:1],
            "buyer_id": s.buyers[:1],
        }
        for name, values in filters.items():
            for value in values:
                cases.append(_catalogue_case(replace(base, **{name: value.value}), s))

    cases += [
        Case("entité citée", f"Quels titulaires reviennent le plus chez Acheteur A en {year} ?",
             (Route.of(2, {"buyer_id": dataset.BUYER_A, "year": year}),)),
        Case("entité citée", "Quels titulaires reviennent le plus chez Acheteur 2024 en 2024 ?",
             (Route.of(2, {"buyer_id": dataset.BUYER_2024, "year": 2024}),)),
        Case("entité citée", f"Quels titulaires reviennent le plus chez Zorglub en {year} ?"),
        Case("entité citée", "Quels titulaires reviennent le plus chez la Mairie de Nulle-Part ?"),
    ]
    cases += [Case("hors périmètre", q) for q in dataset.ABSTENTION_QUESTIONS]
    return _merge_duplicates(cases)


def _merge_duplicates(cases: list[Case]) -> list[Case]:
    """Une même formulation n'est posée qu'une fois ; ses routes acceptées s'additionnent."""
    merged: dict[str, Case] = {}
    for case in cases:
        first = merged.get(case.question)
        if first is None:
            merged[case.question] = case
        else:
            routes = first.routes + tuple(r for r in case.routes if r not in first.routes)
            merged[case.question] = replace(first, routes=routes)
    return list(merged.values())
