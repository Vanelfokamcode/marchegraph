"""Commande d'évaluation de l'epic 4, sur le jeu de fixtures (aucune donnée DECP).

    python -m marchegraph.evaluation.run [--assistant] [--output data/evaluation]

Par défaut, mesure les deux baselines (story 4.5) : le modèle local sans graphe
(`MARCHEGRAPH_LLM_MODEL`) et la baseline SQL DuckDB. `--assistant` ajoute
l'assistant GraphRAG (story 4.6). Neo4j et le modèle restent en loopback ; les
fixtures sont chargées sous un `source_id` dédié puis supprimées.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from marchegraph.evaluation import dataset, scoring, sql_baseline
from marchegraph.queries import assistant, dispatch
from marchegraph.queries.formulation import payload
from marchegraph.queries.interpretation import interpret

BASELINE_PROMPT = (
    "Réponds en français, en trois phrases au maximum, à la question suivante "
    "sur les marchés publics français (données essentielles de la commande "
    "publique). Si tu ne disposes pas de l'information, dis-le.\n\n"
    "Question : {question}\n\nRéponse :"
)


@contextmanager
def scoped_fixture_graph(session):
    """Charge les fixtures sous `dataset.SOURCE_ID` et les supprime à la sortie."""
    from marchegraph.graph import load_initial_awards, load_modifications, queries

    # Les chargeurs et requêtes lisent cette constante de module, sans paramètre.
    with TemporaryDirectory() as directory, \
            patch.object(load_initial_awards, "DATASET_ID", dataset.SOURCE_ID), \
            patch.object(load_modifications, "DATASET_ID", dataset.SOURCE_ID), \
            patch.object(queries, "DATASET_ID", dataset.SOURCE_ID):
        source_path, identities_path = dataset.write_fixtures(Path(directory))
        cleanup = "MATCH (node {source_id: $source_id}) DETACH DELETE node"
        session.run(cleanup, source_id=dataset.SOURCE_ID).consume()
        try:
            load_initial_awards.load_initial_awards(session, source_path, identities_path)
            load_modifications.load_modification_versions(session, source_path)
            yield source_path
        finally:
            session.run(cleanup, source_id=dataset.SOURCE_ID).consume()


def _model_memory(base_url: str) -> list[dict]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/api/ps", timeout=10) as reply:
        return [{"model": m.get("name"), "size_bytes": m.get("size")}
                for m in json.load(reply).get("models", [])]


def _timed(function, *args):
    start = time.perf_counter()
    value = function(*args)
    return value, round(time.perf_counter() - start, 2)


def evaluate(session, source_path: Path, generate, with_assistant: bool) -> dict:
    records = []
    for item in dataset.REFERENCE_QUESTIONS:
        recognized = interpret(item.question)
        reference_response = dispatch.run(session, recognized) if recognized else None
        reference = scoring.core_facts(item.question_id, reference_response)
        allowed_text = json.dumps(payload(reference_response), ensure_ascii=False)
        record = {
            "question": item.question,
            "attendu": "réponse",
            "question_id": item.question_id,
            "reconnaissance_correcte": bool(
                recognized and recognized.question_id == item.question_id
                and dict(recognized.params) == item.params
            ),
            "reference": [list(map(str, fact)) for fact in reference],
        }
        record["sql"] = _sql(source_path, item.question, reference)
        if generate:
            record["llm_sans_graphe"] = _llm(generate, item.question, reference,
                                             allowed_text)
        if with_assistant:
            record["assistant"] = _assistant(session, generate, item, reference,
                                             allowed_text)
        records.append(record)
    for question in dataset.ABSTENTION_QUESTIONS:
        record = {"question": question, "attendu": "abstention"}
        record["sql"] = _sql(source_path, question, None)
        if generate:
            record["llm_sans_graphe"] = _llm(generate, question, None, "")
        if with_assistant:
            result, seconds = _timed(assistant.answer, question, session, generate)
            record["assistant"] = {
                "score": asdict(scoring.Score(
                    "abstention correcte" if result is None
                    else "réponse au lieu d'abstention")),
                "secondes": seconds,
            }
        records.append(record)
    return {"questions": records}


def _sql(source_path: Path, question: str, reference) -> dict:
    recognized = interpret(question)
    if recognized is None or not isinstance(recognized.question_id, int):
        label = "abstention correcte" if reference is None else "abstention à tort"
        return {"score": asdict(scoring.Score(label)), "lignes": None}
    rows, seconds = _timed(sql_baseline.run, source_path, recognized.question_id,
                           dict(recognized.params))
    facts = scoring.normalize_facts(rows)
    if reference is None:
        score = scoring.Score("réponse au lieu d'abstention")
    else:
        score = scoring.score_structured(facts, reference)
    return {"score": asdict(score), "lignes": [list(map(str, f)) for f in facts],
            "secondes": seconds}


def _llm(generate, question: str, reference, allowed_text: str) -> dict:
    try:
        text, seconds = _timed(generate, BASELINE_PROMPT.format(question=question))
    except Exception as error:  # le modèle en échec est un résultat à rapporter
        return {"score": asdict(scoring.Score("erreur")), "texte": str(error)}
    score = scoring.score_text(text, question, reference, allowed_text)
    return {"score": asdict(score), "texte": text, "secondes": seconds}


def _assistant(session, generate, item, reference, allowed_text: str) -> dict:
    result, seconds = _timed(assistant.answer, item.question, session, generate)
    if result is None:
        return {"score": asdict(scoring.Score("abstention à tort")), "secondes": seconds}
    facts = scoring.core_facts(item.question_id, result.response) \
        if isinstance(item.question_id, int) else None
    structured = scoring.score_structured(facts, reference)
    formulation = result.formulation
    text_score = (scoring.score_text(formulation.text, item.question, reference,
                                     allowed_text)
                  if formulation.text else None)
    return {
        "score": asdict(structured),
        "formulation": formulation.source,
        "texte": formulation.text,
        "motifs": list(formulation.problems),
        "score_texte": asdict(text_score) if text_score else None,
        "secondes": seconds,
    }


def main() -> int:
    from neo4j import GraphDatabase

    from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--assistant", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/evaluation"))
    args = parser.parse_args()

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("NEO4J_PASSWORD doit être défini dans l'environnement.")
        return 1
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    validate_local_neo4j_uri(uri)
    generate = assistant.model_from_env()
    if generate is None:
        print(f"{assistant.MODEL_ENV} n'est pas défini : la baseline sans graphe "
              "ne sera pas mesurée.")

    auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), password)
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
        database=os.environ.get("NEO4J_DATABASE", "neo4j")
    ) as session, scoped_fixture_graph(session) as source_path:
        report = evaluate(session, source_path, generate, args.assistant)

    report["modele"] = generate.model if generate else None
    if generate:
        report["memoire_modele"] = _model_memory(
            os.environ.get(assistant.MODEL_URL_ENV, "http://127.0.0.1:11434"))
    args.output.mkdir(parents=True, exist_ok=True)
    name = "assistant" if args.assistant else "baselines"
    output = args.output / f"evaluation-{name}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    for record in report["questions"]:
        labels = {key: record[key]["score"]["label"]
                  for key in ("sql", "llm_sans_graphe", "assistant") if key in record}
        print(f"- {record['question']}\n  {labels}")
    print(f"\nRapport détaillé : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
