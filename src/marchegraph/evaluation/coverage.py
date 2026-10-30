"""Évaluation de couverture de l'epic 5, sur fixtures (aucune donnée DECP).

    python -m marchegraph.evaluation.coverage [--llm-baseline] [--output data/evaluation]

Le jeu est généré à partir du catalogue et des valeurs des fixtures ; chaque
référence est calculée par requête. Systèmes mesurés : l'assistant (texte
libre), la baseline SQL de l'epic 4 et, avec `--llm-baseline`, le modèle local
sans graphe. Le seuil est fixé ensuite par l'utilisateur.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from marchegraph.evaluation import scoring, sql_baseline
from marchegraph.evaluation.coverage_cases import CATALOGUE_ROUTE, Case, Route, build_cases
from marchegraph.evaluation.run import _llm, _timed, scoped_fixture_graph
from marchegraph.queries import assistant, dispatch
from marchegraph.queries.formulation import payload
from marchegraph.queries.interpretation import LABELS, Interpretation, interpret

SYSTEMS = ("assistant", "sql", "llm_sans_graphe")
ANSWERED = {"correct", "différent", "mauvaise question", "réponse au lieu d'abstention",
            "hallucination", "incomplet"}


def reference(session, route: Route):
    params = dict(route.params)
    if route.question_id == CATALOGUE_ROUTE:
        from marchegraph.graph.catalogue_queries import run_catalogue

        return run_catalogue(session, params["query"])
    return dispatch.run(session, Interpretation(route.question_id,
                                                LABELS[route.question_id], params))


def _facts(route: Route, response) -> list[tuple]:
    return scoring.core_facts(route.question_id, response)


def _no_answer(case: Case) -> str:
    return "abstention à tort" if case.routes else "abstention correcte"


def _assistant(session, generate, case: Case, references: dict) -> dict:
    result, seconds = _timed(assistant.answer, case.question, session, generate)
    record: dict = {"secondes": seconds}
    if result is None or (isinstance(result, assistant.EntityChoice) and not result.options):
        return {**record, "label": _no_answer(case)}
    if isinstance(result, assistant.EntityChoice):
        label = "choix demandé" if case.routes else "réponse au lieu d'abstention"
        return {**record, "label": label}
    route = Route.of(result.interpretation.question_id, dict(result.interpretation.params))
    text = result.formulation.text
    record.update(route=repr(route), formulation=result.formulation.source, texte=text)
    if text and route.question_id in scoring.CORE_FACTS:
        own = json.dumps(payload(result.response), ensure_ascii=False)
        text_score = scoring.score_text(text, case.question,
                                        _facts(route, result.response), own)
        record["texte_halluciné"] = text_score.label == "hallucination"
        record["inventés"] = list(text_score.invented)
    if not case.routes:
        label = "réponse au lieu d'abstention"
    elif route not in case.routes:
        label = "mauvaise question"
    else:
        label = scoring.score_structured(_facts(route, result.response),
                                         _facts(route, references[route])).label
    return {**record, "label": label}


def _sql(source_path: Path, case: Case, references: dict) -> dict:
    recognized = interpret(case.question)
    if (recognized is None or not isinstance(recognized.question_id, int)
            or "buyer_name" in recognized.params):
        return {"label": _no_answer(case)}
    route = Route.of(recognized.question_id, dict(recognized.params))
    if not case.routes:
        return {"label": "réponse au lieu d'abstention"}
    if route not in case.routes:
        return {"label": "mauvaise question"}
    rows, seconds = _timed(sql_baseline.run, source_path, route.question_id,
                           dict(route.params))
    score = scoring.score_structured(scoring.normalize_facts(rows),
                                     _facts(route, references[route]))
    return {"label": score.label, "secondes": seconds}


def _llm_baseline(generate, case: Case, references: dict) -> dict:
    route = case.routes[0] if case.routes else None
    expected = _facts(route, references[route]) if route else None
    allowed = json.dumps(payload(references[route]), ensure_ascii=False) if route else ""
    result = _llm(generate, case.question, expected, allowed)
    label = result["score"]["label"]
    return {"label": label, "texte": result.get("texte"),
            "texte_halluciné": label == "hallucination",
            "secondes": result.get("secondes")}


def evaluate(session, source_path: Path, cases: list[Case], generate,
             llm_baseline: bool) -> list[dict]:
    references = {route: reference(session, route)
                  for case in cases for route in case.routes}
    records = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.category} : {case.question}", flush=True)
        record = {"catégorie": case.category, "question": case.question,
                  "attendu": "réponse" if case.routes else "abstention",
                  "routes": [repr(r) for r in case.routes],
                  "assistant": _assistant(session, generate, case, references),
                  "sql": _sql(source_path, case, references)}
        if llm_baseline and generate:
            record["llm_sans_graphe"] = _llm_baseline(generate, case, references)
        records.append(record)
    return records


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def summarize(records: list[dict]) -> dict:
    """Indicateurs par système et par catégorie, plus un total."""
    categories = list(dict.fromkeys(r["catégorie"] for r in records)) + ["total"]
    summary: dict = {}
    for system in SYSTEMS:
        rows = [r for r in records if system in r]
        if not rows:
            continue
        summary[system] = {}
        for category in categories:
            subset = [r for r in rows if category in ("total", r["catégorie"])]
            labels = Counter(r[system]["label"] for r in subset)
            answers = sum(r["attendu"] == "réponse" for r in subset)
            abstentions = len(subset) - answers
            answered = sum(labels[label] for label in ANSWERED)
            times = [r[system]["secondes"] for r in subset
                     if r[system].get("secondes") is not None]
            summary[system][category] = {
                "questions": len(subset),
                "couverture": _rate(labels["correct"], answers),
                "precision": _rate(labels["correct"], answered),
                "abstentions_correctes": _rate(labels["abstention correcte"], abstentions),
                "hallucinations_affichees": sum(
                    bool(r[system].get("texte_halluciné")) for r in subset),
                "latence_moyenne_s": round(sum(times) / len(times), 2) if times else None,
                "libelles": dict(sorted(labels.items())),
            }
    return summary


def to_markdown(summary: dict) -> str:
    lines = []
    for system, categories in summary.items():
        lines += [f"### {system}", "",
                  "| Catégorie | Questions | Couverture | Précision | Abstentions "
                  "correctes | Hallucinations affichées | Latence moy. (s) |",
                  "|---|---|---|---|---|---|---|"]
        for category, m in categories.items():
            cells = [m["questions"], m["couverture"], m["precision"],
                     m["abstentions_correctes"], m["hallucinations_affichees"],
                     m["latence_moyenne_s"]]
            lines.append(f"| {category} | " + " | ".join(
                "—" if c is None else str(c) for c in cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    from neo4j import GraphDatabase

    from marchegraph.graph.dimension_values import load_suggestions
    from marchegraph.graph.entity_search import create_search_indexes
    from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--llm-baseline", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/evaluation"))
    args = parser.parse_args()

    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        print("NEO4J_PASSWORD doit être défini dans l'environnement.")
        return 1
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    validate_local_neo4j_uri(uri)
    generate = assistant.model_from_env()

    auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), password)
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
        database=os.environ.get("NEO4J_DATABASE", "neo4j")
    ) as session, scoped_fixture_graph(session) as source_path:
        create_search_indexes(session)
        cases = build_cases(load_suggestions(session))
        records = evaluate(session, source_path, cases, generate, args.llm_baseline)

    summary = summarize(records)
    report = {"modele": generate.model if generate else None,
              "resume": summary, "questions": records}
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "evaluation-couverture.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                      encoding="utf-8")
    print(to_markdown(summary))
    print(f"Rapport détaillé : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
