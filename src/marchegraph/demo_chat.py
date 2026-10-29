"""Démo locale : questions en français vers les requêtes préparées.

Déterministe, sans LLM. Neo4j en lecture seule, loopback uniquement.
"""
from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from urllib.parse import urlparse

from marchegraph.queries.interpretation import interpret

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

SUPPORTED = [
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


def _plain(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        obj = asdict(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def main() -> None:
    import streamlit as st
    from neo4j import READ_ACCESS, GraphDatabase

    from marchegraph.graph.load_initial_awards import DATASET_ID
    from marchegraph.queries.dispatch import run

    st.set_page_config(page_title="MarchéGraph (démo)")
    st.title("MarchéGraph : démo locale")
    st.caption("Réponses déterministes, sans LLM. Requêtes préparées, lecture seule.")

    password = os.environ.get("NEO4J_PASSWORD")
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    if not password:
        st.error("NEO4J_PASSWORD doit être défini dans l'environnement.")
        st.stop()
    if urlparse(uri).hostname not in LOCAL_HOSTS:
        st.error("Seule une URI Neo4j locale (loopback) est acceptée.")
        st.stop()

    @st.cache_resource
    def get_driver():
        user = os.environ.get("NEO4J_USERNAME", "neo4j")
        return GraphDatabase.driver(uri, auth=(user, password))

    def read_session():
        return get_driver().session(database=database, default_access_mode=READ_ACCESS)

    with st.sidebar:
        st.subheader("Contenu du graphe")
        try:
            with read_session() as s:
                counts = s.run(
                    "MATCH (m:Marche {source_id: $source}) "
                    "RETURN m.annee AS annee, count(*) AS marches ORDER BY annee",
                    source=DATASET_ID,
                ).data()
            st.table(counts) if counts else st.warning("Aucun marché trouvé.")
        except Exception as exc:  # démo : on affiche l'erreur telle quelle
            st.error(f"Connexion impossible : {exc}")
        st.subheader("Questions prises en charge")
        for example in SUPPORTED:
            st.markdown(f"- {example}")

    def show(response) -> None:
        st.write(f"{len(response.rows)} ligne(s) de résultat.")
        for limitation in response.limitations:
            st.warning(limitation)
        if response.rows:
            st.dataframe([_plain(r.result) for r in response.rows])
            with st.expander("Preuves issues du graphe"):
                for i, row in enumerate(response.rows[:10], start=1):
                    note = "" if row.evidence_complete else " (preuves tronquées)"
                    st.markdown(f"Ligne {i}{note}")
                    st.dataframe([asdict(e) for e in row.evidence[:20]])
        if response.metadata:
            st.caption(", ".join(f"{k} : {v}" for k, v in response.metadata))

    history = st.session_state.setdefault("history", [])
    for role, text in history:
        with st.chat_message(role):
            st.write(text)

    question = st.chat_input("Posez une question en français")
    if not question:
        return
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        plan = interpret(question)
        if plan is None:
            answer = ("Je ne sais pas répondre à cette question : je préfère "
                      "m'abstenir plutôt que d'inventer. Voir la liste à gauche.")
            st.write(answer)
        else:
            try:
                with read_session() as s:
                    response = run(s, plan)
                answer = f"Question reconnue : {plan.label}."
                st.write(answer)
                show(response)
            except Exception as exc:
                answer = f"Erreur pendant la requête : {exc}"
                st.error(answer)
    history.append(("user", question))
    history.append(("assistant", answer))


if __name__ == "__main__":
    main()
