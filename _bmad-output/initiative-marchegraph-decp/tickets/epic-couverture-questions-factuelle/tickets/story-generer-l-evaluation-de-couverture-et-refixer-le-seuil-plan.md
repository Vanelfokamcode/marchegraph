---
title: "Générer l'évaluation de couverture et refixer le seuil"
ticket: 4
status: done
---

# Évaluation de couverture (5.4)

## Portée

- `src/marchegraph/evaluation/coverage_cases.py` (pur) : jeu généré à partir
  du catalogue et des valeurs des fixtures — 10 questions de référence,
  paraphrases, combinaisons du catalogue (mesure × regroupement, mesure ×
  filtre), combinaisons invalides (abstention attendue), entités citées par
  leur nom (existantes et inexistantes), 10 questions hors périmètre de
  l'epic 4. Chaque cas porte ses routes acceptées ; une combinaison déjà
  couverte par une question de référence accepte les deux routes.
- `src/marchegraph/evaluation/coverage.py` : références calculées par
  requête ; mesure de l'assistant (texte libre), de la baseline SQL et, avec
  `--llm-baseline`, du modèle sans graphe ; indicateurs par catégorie :
  couverture, précision, abstentions correctes, hallucinations affichées,
  latence. Rapport `data/evaluation/evaluation-couverture.json` et tableau
  Markdown.
- Commande : `python -m marchegraph.evaluation.coverage [--llm-baseline]`.

## Vérification

- `tests/test_coverage.py` : tailles et catégories, routes du catalogue
  valides, combinaisons invalides en abstention, équivalences, génération
  déterministe, calcul des indicateurs ; test Neo4j sur fixtures (questions de
  référence correctes, hors périmètre en abstention, entités résolues ou
  abstention).

## Corrections faites pendant la story

- Formulations identiques fusionnées (une même question accepte plusieurs
  routes) ; 2026-10-30 : `tests.test_coverage` 6 tests OK.
- Index `Marche.source_id` et `Modification.source_id` créés au chargement :
  sans eux, les requêtes sur fixtures parcouraient tout le snapshot et
  dépassaient le délai de connexion.
- Progression affichée question par question.

## Mesure initiale (2026-10-30, sans modèle, 114 questions)

| Catégorie | Assistant couverture | Assistant précision | SQL couverture |
|---|---|---|---|
| référence (10) | 1,0 | 1,0 | 0,8 |
| paraphrase (21) | 0,714 | 1,0 | 0,524 |
| catalogue (62) | 0,016 | 0,034 | 0,016 |
| entité citée (4) | 1,0 (abstentions 1,0) | 1,0 | 0,0 |
| combinaison invalide (7) | abstentions 0,571 | — | abstentions 0,571 |
| hors périmètre (10) | abstentions 1,0 | — | abstentions 1,0 |

- Constat principal : 31 réponses à une autre question que celle posée
  (28 du catalogue, 3 combinaisons invalides), surtout des questions sur les
  modifications, procédures, natures ou familles CPV avec un filtre ou un
  regroupement que la question de référence n'applique pas.
- Les hallucinations affichées restent à mesurer avec le modèle
  (`MARCHEGRAPH_LLM_MODEL`), à faire lors de la comparaison de la story 5.

## Seuil décidé par l'utilisateur (2026-10-30)

- Questions de référence : couverture 100 %.
- Catalogue en texte libre : couverture ≥ 80 % avec précision 100 %.
- Paraphrases : couverture ≥ 80 %.
- Abstentions correctes (hors périmètre, combinaisons invalides, entités
  inexistantes) : 100 % ; hallucinations affichées : 0.
- Réponse à une autre question que celle posée : tolérée si l'interface
  affiche clairement la question reconnue. Note : la précision 100 % exigée
  sur le catalogue l'exclut de fait pour cette catégorie.
