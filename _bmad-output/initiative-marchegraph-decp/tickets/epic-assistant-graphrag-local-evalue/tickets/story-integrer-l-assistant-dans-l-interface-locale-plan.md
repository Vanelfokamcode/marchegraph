---
title: "Intégrer l'assistant dans l'interface locale"
ticket: 4
status: done
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
- Suite complète : 63 tests, dont l'intégration Neo4j locale ; `compileall`
  et `git diff --check` passent.
- Contrôle sur le graphe local par l'utilisateur, avec `phi4-mini:3.8b`
  (snapshot retéléchargé, démo uniquement) : les dix questions sont
  reconnues ; Q1, Q3, Q4, Q5, Q7 et Q8 sont formulées ; Q2 (identifiant
  fictif) et Q9 n'ont aucune ligne et passent par le gabarit ; Q10 est en
  abstention de formulation (chiffre 18 inventé) ; la question hors sujet
  s'abstient.
- Correctifs issus de ce contrôle : le modèle reçoit au plus 10 lignes (et le
  total), des listes internes de 10 éléments au plus et des décimales
  arrondies à 2 chiffres ; une réponse en JSON ou en code mène à
  l'abstention. Avant correctif, Q3 et Q8 renvoyaient du JSON brut et Q6/Q7
  dépassaient le délai de 120 s.

## Observations pour l'évaluation (stories 4.5 et 4.6)

- Q10 : « les valeurs manquantes … sont incohérentes » contredit la limite
  (les valeurs multiples ne sont pas des erreurs) ; déformation sans chiffre,
  non détectée par le contrôle.
- Q8 : « la durée moyenne par famille CPV est de 26,60 mois » présente la
  valeur d'une seule famille comme une valeur générale.
- Q9 : la requête ne renvoie aucune ligne sur ce graphe ; cause non
  examinée (hors périmètre de l'assistant).
- Q6 : dépassement de délai avant la limitation des listes internes ; à
  revérifier.
