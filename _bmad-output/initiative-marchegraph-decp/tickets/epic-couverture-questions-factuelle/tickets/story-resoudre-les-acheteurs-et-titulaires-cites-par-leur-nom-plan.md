---
title: "Résoudre les acheteurs et titulaires cités par leur nom avec choix explicite"
ticket: 2
status: done
---

# Résolution des entités par leur nom (5.2a)

## Décision

- 2026-10-30 : l'utilisateur ne retient que la partie acheteurs et titulaires ;
  les libellés CPV deviennent la story 8, reportée.

## Portée livrée

- `src/marchegraph/graph/entity_search.py` : commande
  `python -m marchegraph.graph.entity_search` qui crée deux index plein texte
  (`acheteur_noms`, `titulaire_noms`) sur `nom_values`, analyseur
  `standard-folding` (sans accents) ; écriture de schéma réservée au pipeline
  (AD-3). Recherche en lecture seule : candidats avec identifiant exact, noms,
  score et nombre de marchés.
- `src/marchegraph/queries/entity_lookup.py` (pur) : requête Lucene échappée
  (mots obligatoires, tolérance d'une faute sur les mots de 5 lettres et
  plus) ; décision : nom identique ou candidat 1,5 fois devant le suivant →
  retenu ; sinon choix parmi 5 au plus ; aucun candidat → abstention.
- `interpretation.py` : Q2 accepte « chez <nom> » ; une mention générique
  (« un acheteur donné ») ou une région hors du nom donne une abstention ; le
  SIRET reste prioritaire.
- `assistant.py` : `EntityChoice` (choix ou introuvable) ; la requête n'est
  lancée qu'avec l'identifiant exact ; `buyer_id` porte le choix de
  l'utilisateur.
- `demo_chat.py` : boutons de choix (nom, identifiant, nombre de marchés) et
  mention que le score n'est pas un fait.

## Vérification

- `tests/test_entity_lookup.py` : normalisation, échappement d'une saisie
  hostile, décisions, reconnaissance de Q2 par nom, résolution dans
  l'assistant sans requête en cas de choix ou d'absence ; test Neo4j sur
  fixtures (index créés et en ligne, nom exact, variante sans accents, nom
  inexistant).
- 2026-10-30 : 10 tests OK, dont le test Neo4j sur fixtures (index créés et
  en ligne, analyseur `standard-folding` accepté, nom exact, variante sans
  accents, nom inexistant) ; suite complète 87 tests (le seul échec, un
  conflit de nom de paramètre avec `Session.run`, a été corrigé).
