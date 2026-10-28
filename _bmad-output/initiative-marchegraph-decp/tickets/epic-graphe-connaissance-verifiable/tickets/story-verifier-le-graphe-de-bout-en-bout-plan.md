---
title: "Vérifier le graphe de bout en bout"
ticket: 9
status: built
---

# Vérification locale de bout en bout

## Parcours vérifié

- Une fixture Parquet couvre les attributions initiales de 2024 et 2025, les
  identités titulaires résolues, les valeurs manquantes et multivaluées, une
  modification reliée et une version sans marché initial.
- Les chargeurs locaux alimentent un espace de données Neo4j isolé ; les dix
  questions de référence sont exécutées sur ces nœuds, avec résultats et
  preuves.
- Le même test vérifie la conformité SHACL d'un graphe exporté en Turtle, puis
  un rejet traçable avec son identifiant de règle, ses triples et son rapport
  JSON Lines.
- Le test n'accepte qu'une connexion Neo4j locale, ne lit pas le snapshot DECP
  et nettoie les nœuds isolés en fin d'exécution. Les Parquet, l'export et les
  rejets restent dans un dossier temporaire.

## Vérification

- L'intégration Neo4j locale passe : `NEO4J_PASSWORD=… uv run --locked python
  -m unittest tests.test_graph_end_to_end` (1 test).
- La suite standard passe : 38 tests, dont le test d'intégration ignoré sans
  `NEO4J_PASSWORD`.
- Le contrôle local confirme qu'aucun nœud de fixture ne reste dans Neo4j.
- `compileall` et `git diff --check` passent ; aucun résultat dérivé n'est
  conservé dans le dépôt.
