"""Parcours de l'assistant : question → requête préparée → formulation contrôlée.

Commande de contrôle local (Neo4j et, si configuré, le modèle local) :
    python -m marchegraph.queries.assistant
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace

from marchegraph.graph.contracts import QueryResponse
from marchegraph.queries import dispatch
from marchegraph.queries.catalogue import CatalogueQuery
from marchegraph.queries.entity_lookup import Candidate, Resolution
from marchegraph.queries.formulation import Formulation, Generate, formulate
from marchegraph.queries.interpretation import Interpretation, interpret
from marchegraph.queries.local_model import DEFAULT_MODEL_URL, OllamaClient

MODEL_ENV = "MARCHEGRAPH_LLM_MODEL"
MODEL_URL_ENV = "MARCHEGRAPH_LLM_URL"

EXAMPLES = [
    "Quels acheteurs ont attribué le plus de marchés en 2025 ?",
    "Quels titulaires reviennent le plus chez l'acheteur 12345678901234 ?",
    "Quels titulaires reviennent le plus chez la Ville de Rennes ?",
    "Quel montant total par famille CPV ?",
    "Quels marchés ont été modifiés en 2025 ?",
    "Quelles procédures et natures de marché sont utilisées ?",
    "Quels titulaires travaillent avec plusieurs acheteurs ?",
    "Quels marchés concernent la voirie en Bretagne ?",
    "Quelle durée moyenne par famille CPV ?",
    "Quels fournisseurs ont plusieurs écritures de leur nom ?",
    "Quelles données sont manquantes ou incohérentes ?",
]

ABSTENTION_TEXT = (
    "Je ne sais pas répondre à cette question : je préfère m'abstenir plutôt "
    "que d'inventer."
)


@dataclass(frozen=True)
class AssistantAnswer:
    interpretation: Interpretation
    response: QueryResponse
    formulation: Formulation


@dataclass(frozen=True)
class EntityChoice:
    """L'entité citée est ambiguë (options) ou introuvable (aucune option)."""

    interpretation: Interpretation
    kind: str
    mention: str
    options: tuple[Candidate, ...]


def _resolve(session, kind: str, mention: str) -> Resolution:
    from marchegraph.graph.entity_search import resolve

    return resolve(session, kind, mention)


def model_from_env() -> OllamaClient | None:
    """Client du modèle local si `MARCHEGRAPH_LLM_MODEL` est défini, sinon None."""
    model = os.environ.get(MODEL_ENV, "").strip()
    if not model:
        return None
    return OllamaClient(model, os.environ.get(MODEL_URL_ENV, DEFAULT_MODEL_URL))


def answer(
    question: str, session, generate: Generate | None, *, buyer_id: str | None = None
) -> AssistantAnswer | EntityChoice | None:
    """None : question non prise en charge. `buyer_id` : choix fait par l'utilisateur."""
    interpretation = interpret(question)
    if interpretation is None:
        return None
    params = dict(interpretation.params)
    mention = params.pop("buyer_name", None)
    if mention is not None:
        if buyer_id is None:
            resolution = _resolve(session, "acheteur", mention)
            if resolution.status != "resolved":
                return EntityChoice(interpretation, "acheteur", mention,
                                    resolution.options)
            buyer_id = resolution.chosen.identifier
        interpretation = replace(interpretation, params={**params, "buyer_id": buyer_id})
    response = dispatch.run(session, interpretation)
    formulation = formulate(question, interpretation.label, response, generate)
    return AssistantAnswer(interpretation, response, formulation)


def answer_guided(
    query: CatalogueQuery, description: str, session, generate: Generate | None
) -> AssistantAnswer:
    """Requête composée par la saisie guidée : catalogue, puis formulation contrôlée."""
    from marchegraph.graph.catalogue_queries import CATALOGUE_QUESTION_ID, run_catalogue

    response = run_catalogue(session, query)
    formulation = formulate(description, query.label, response, generate)
    return AssistantAnswer(Interpretation(CATALOGUE_QUESTION_ID, query.label),
                           response, formulation)


def main() -> int:
    from neo4j import READ_ACCESS, GraphDatabase

    from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("NEO4J_PASSWORD doit être défini dans l'environnement.")
        return 1
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    validate_local_neo4j_uri(uri)
    generate = model_from_env()
    print(f"Modèle : {generate.model if generate else 'aucun (gabarit)'}\n")
    questions = EXAMPLES + ["Quelle est la météo à Paris ?"]
    auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), password)
    with GraphDatabase.driver(uri, auth=auth) as driver:
        with driver.session(
            database=os.environ.get("NEO4J_DATABASE", "neo4j"),
            default_access_mode=READ_ACCESS,
        ) as session:
            for question in questions:
                result = answer(question, session, generate)
                print(f"Q : {question}")
                if result is None:
                    print(f"  abstention : {ABSTENTION_TEXT}\n")
                    continue
                if isinstance(result, EntityChoice):
                    names = [f"{o.identifier} {o.names[:1]}" for o in result.options]
                    print(f"  « {result.mention} » : "
                          f"{names or 'aucun acheteur correspondant'}\n")
                    continue
                f = result.formulation
                print(f"  question {result.interpretation.question_id}, "
                      f"{len(result.response.rows)} ligne(s), formulation : {f.source}")
                print(f"  texte : {f.text}" if f.text else f"  motifs : {f.problems}")
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
