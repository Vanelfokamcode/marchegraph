---
title: "Interroger acheteurs, titulaires et procédures"
ticket: 5
status: done
---

# Contrat commun de requête et de preuve

## Portée livrée

- Types partagés pour les réponses structurées, les lignes de résultat, les
  limites explicites et les références de preuve vers le graphe.
- Question 1 : classement des acheteurs par nombre de `uid` distincts, filtré
  par année ; 2025 par défaut et périmètre national faute de région chargée.
- Question 2 : classement des titulaires récurrents pour un acheteur demandé,
  avec preuve des liens marché–acheteur et marché–titulaire.
- Question 5 : comptes distincts par valeur de nature et de procédure,
  présentés séparément ; valeurs absentes et multivaluées comptées.
- Question 6 : titulaires liés à plusieurs acheteurs, avec preuves des deux
  relations pour chaque marché.
- Les classements sont limités à dix résultats par défaut et permettent de
  fournir une autre limite.

## Vérification

- Fixtures déterministes couvrant les quatre contrats de réponse et les
  références de preuve.
- Suite complète : `uv run --locked python -m unittest discover -s tests`
  (28 tests passés).
- Exécution locale contre Neo4j : les questions 1, 2, 5 et 6 ont retourné
  respectivement 10, 10, 15 et 10 lignes.
- `git diff --check` ne signale aucune erreur.
