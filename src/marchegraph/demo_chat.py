"""Démo locale : questions en français vers les requêtes préparées.

Reconnaissance déterministe ; formulation par le modèle local si
`MARCHEGRAPH_LLM_MODEL` est défini, contrôlée, sinon gabarit.
Neo4j en lecture seule, loopback uniquement.
"""
from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from decimal import Decimal

from marchegraph.queries.assistant import ABSTENTION_TEXT, EXAMPLES


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
    from marchegraph.graph.neo4j_config import (
        LocalNeo4jURLError,
        validate_local_neo4j_uri,
    )
    from marchegraph.queries.assistant import EntityChoice
    from marchegraph.queries.assistant import answer as ask
    from marchegraph.queries.assistant import model_from_env
    from marchegraph.queries.entity_lookup import option_label
    from marchegraph.queries.local_model import LocalModelURLError

    st.set_page_config(page_title="MarchéGraph (démo)")
    st.title("MarchéGraph : démo locale")

    password = os.environ.get("NEO4J_PASSWORD")
    uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    if not password:
        st.error("NEO4J_PASSWORD doit être défini dans l'environnement.")
        st.stop()
    try:
        validate_local_neo4j_uri(uri)
        generate = model_from_env()
    except (LocalNeo4jURLError, LocalModelURLError) as error:
        st.error(str(error))
        st.stop()
    mode = (f"formulation par le modèle local {generate.model}, contrôlée"
            if generate else "réponses par gabarit, sans modèle")
    st.caption(f"Requêtes préparées en lecture seule ; {mode}.")

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
        for example in EXAMPLES:
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

    pending = st.session_state.pop("choice", None)
    typed = st.chat_input("Posez une question en français")
    question = pending[0] if pending else typed
    if not question:
        return
    with st.chat_message("user"):
        st.write(question if not pending else f"{question} (choix : {pending[2]})")
    with st.chat_message("assistant"):
        try:
            with read_session() as s:
                result = ask(question, s, generate,
                             buyer_id=pending[1] if pending else None)
        except Exception as exc:
            answer = f"Erreur pendant la requête : {exc}"
            st.error(answer)
        else:
            if result is None:
                answer = f"{ABSTENTION_TEXT} Voir la liste à gauche."
                st.write(answer)
            elif isinstance(result, EntityChoice) and not result.options:
                answer = (f"Je ne trouve aucun acheteur correspondant à « "
                          f"{result.mention} » : je m'abstiens.")
                st.write(answer)
            elif isinstance(result, EntityChoice):
                answer = (f"Plusieurs acheteurs correspondent à « {result.mention} ». "
                          "Lequel voulez-vous dire ?")
                st.write(answer)
                st.caption("Les candidats viennent d'une recherche plein texte sur "
                           "les noms ; le score de pertinence n'est pas un fait.")
                for option in result.options:
                    label = option_label(option)
                    st.button(label, key=f"choice-{option.identifier}",
                              on_click=st.session_state.__setitem__,
                              args=("choice", (question, option.identifier, label)))
            else:
                st.caption(f"Question reconnue : {result.interpretation.label}.")
                formulation = result.formulation
                if formulation.text:
                    answer = formulation.text
                    st.write(answer)
                else:
                    answer = ("Je m'abstiens de formuler une réponse : le texte "
                              "proposé n'a pas passé le contrôle. Le résultat et "
                              "ses preuves sont affichés ci-dessous.")
                    st.warning(answer)
                    with st.expander("Motifs du contrôle"):
                        for problem in formulation.problems:
                            st.markdown(f"- {problem}")
                show(result.response)
    history.append(("user", question))
    history.append(("assistant", answer))


if __name__ == "__main__":
    main()
