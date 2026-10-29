---
title: "Intégrer l'assistant dans l'interface locale"
ticket: 4
status: built
---

# Assistant dans l'interface Streamlit locale

## Portée livrée

- `src/marchegraph/queries/assistant.py` : `answer(question, session,
  generate)` enchaîne reconnaissance, requête préparée et formulation
  contrôlée ; `None` signifie abstention. `model_from_env()` lit
  `MARCHEGRAPH_LLM_MODEL` (par exemple `phi4-mini:3.8b`) et
  `MARCHEGRAPH_LLM_URL` (loopback, `http://127.0.0.1:11434` par défaut) ;
  sans modèle, les réponses passent par le gabarit.
- `src/marchegraph/demo_chat.py` : affiche la réponse en français, ou un
  avertissement d'abstention de formulation avec ses motifs, puis le tableau,
  les limites et les preuves. Lecture seule ; Neo4j et modèle en loopback
  uniquement (`validate_local_neo4j_uri`, `LocalModelURLError`).
- Commande de contrôle : `python -m marchegraph.queries.assistant` exécute les
  dix exemples et une question hors sujet sur le graphe local.

## Vérification

- `tests/test_assistant.py` (sans Neo4j, requête simulée) : les exemples
  couvrent les dix questions ; une question hors sujet s'abstient sans
  interroger le graphe ; les preuves restent celles de la requête ; un
  chiffre inventé mène à l'abstention de formulation ; configuration du
  modèle optionnelle et loopback uniquement.
- Suite complète : 59 tests, intégration ignorée sans `NEO4J_PASSWORD` ;
  `compileall` et `git diff --check` passent.
- À faire par l'utilisateur (secret local requis) : commande de contrôle sur
  le graphe local, avec et sans `MARCHEGRAPH_LLM_MODEL`.
