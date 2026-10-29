---
title: "Évaluer l'assistant face à la baseline"
ticket: 6
status: built
---

# Évaluation comparative de l'assistant

## Portée livrée

- `python -m marchegraph.evaluation.run --assistant` : mêmes 20 questions que
  la story 4.5, assistant mesuré avec `phi4-mini:3.8b` ; résultat structuré,
  texte affiché, motifs d'abstention de formulation et durée par question.
- Rapport : `docs/evaluation-assistant.md`.

## Résultat (2026-10-29)

- Assistant : 10 / 10 références (résultat structuré), 10 / 10 abstentions ;
  une hallucination chiffrée bloquée par le contrôle (Q3).
- Décision stricte de l'utilisateur : Q6 et Q8 sont des hallucinations
  affichées. Seuil non atteint sur le critère « aucune hallucination ».
- Baselines du même run : SQL 8 / 10 et 10 / 10 ; modèle sans graphe 0 / 10 et
  6 / 10.

## Suite à décider

- Clore la story avec le seuil non atteint, ou renforcer le contrôle de
  formulation (story 4.3) puis remesurer.
