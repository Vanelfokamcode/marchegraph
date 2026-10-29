"""Parcours de l'assistant : question → requête préparée → formulation contrôlée.

Commande de contrôle local (Neo4j et, si configuré, le modèle local) :
    python -m marchegraph.queries.assistant
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from marchegraph.graph.contracts import QueryResponse
from marchegraph.queries import dispatch
from marchegraph.queries.formulation import Formulation, Generate, formulate
from marchegraph.queries.interpretation import Interpretation, interpret
from marchegraph.queries.local_model import DEFAULT_MODEL_URL, OllamaClient

MODEL_ENV = "MARCHEGRAPH_LLM_MODEL"
MODEL_URL_ENV = "MARCHEGRAPH_LLM_URL"

EXAMPLES = [
    "Quels acheteurs ont attribué le plus de marchés en 2025 ?",
    "Quels titulaires reviennent le plus chez l'acheteur 12345678901234 ?",
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


def model_from_env() -> OllamaClient | None:
    """Client du modèle local si `MARCHEGRAPH_LLM_MODEL` est défini, sinon None."""
    model = os.environ.get(MODEL_ENV, "").strip()
    if not model:
        return None
    return OllamaClient(model, os.environ.get(MODEL_URL_ENV, DEFAULT_MODEL_URL))


def answer(question: str, session, generate: Generate | None) -> AssistantAnswer | None:
    """None si la question n'est pas prise en charge : l'appelant s'abstient."""
    interpretation = interpret(question)
    if interpretation is None:
        return None
    response = dispatch.run(session, interpretation)
    formulation = formulate(question, interpretation.label, response, generate)
    return AssistantAnswer(interpretation, response, formulation)


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
                f = result.formulation
                print(f"  question {result.interpretation.question_id}, "
                      f"{len(result.response.rows)} ligne(s), formulation : {f.source}")
                print(f"  texte : {f.text}" if f.text else f"  motifs : {f.problems}")
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
