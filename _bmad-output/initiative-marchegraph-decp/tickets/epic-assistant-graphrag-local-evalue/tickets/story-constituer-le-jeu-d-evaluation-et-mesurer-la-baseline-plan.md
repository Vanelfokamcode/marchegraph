---
title: "Constituer le jeu d'évaluation et mesurer la baseline sans graphe"
ticket: 5
status: in-progress
---

# Jeu d'évaluation et baselines

## Portée

- `src/marchegraph/evaluation/dataset.py` : lignes des fixtures de la story
  3.9, identifiants d'acheteur remplacés par des valeurs à 14 chiffres pour la
  question 2 ; dix questions de référence (une par question, paramètres
  attendus) et dix questions à abstention attendue validées par l'utilisateur.
- Référence : résultat des requêtes préparées de l'epic 3 sur ces fixtures
  chargées dans Neo4j sous un `source_id` dédié, supprimé ensuite. Les faits
  essentiels comparés par question sont définis dans `scoring.CORE_FACTS`.
- `src/marchegraph/evaluation/sql_baseline.py` : baseline SQL DuckDB directe
  sur le Parquet, avec la même reconnaissance ; sans les règles de l'epic 3.
- Baseline sans graphe : `phi4-mini:3.8b` ne reçoit que la question.
- `src/marchegraph/evaluation/scoring.py` : notation automatique (correct,
  incomplet, hallucination, abstention correcte ou à tort, réponse au lieu
  d'abstention), puis validation par l'utilisateur.
- `python -m marchegraph.evaluation.run` : mesure les deux baselines et écrit
  `data/evaluation/evaluation-baselines.json` (ignoré par Git).
- L'assistant n'est mesuré qu'avec `--assistant` (story 4.6), après la fixation
  du seuil.

## Vérification

- `tests/test_evaluation.py` (sans Neo4j) : reconnaissance des 20 questions,
  baseline SQL sur le Parquet des fixtures, notation structurée et textuelle.
- Suite complète : 69 tests, dont l'intégration Neo4j locale.

## Reste à faire

- Exécution locale par l'utilisateur, rapport de baseline, validation des
  libellés et fixation du seuil par l'utilisateur.
