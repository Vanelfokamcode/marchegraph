---
title: "Proposer des exemples et une saisie guidée issus des données"
ticket: 3
status: done
---

# Exemples et saisie guidée issus des données (5.3)

## Portée livrée

- `src/marchegraph/graph/dimension_values.py` : requêtes en lecture seule des
  valeurs les plus fréquentes (années prises en charge, régions connues,
  familles CPV à trois chiffres, procédures, natures, acheteurs les plus actifs
  de l'année la plus récente).
- `src/marchegraph/queries/suggestions.py` (pur) : questions d'exemple
  construites sur ces valeurs, toutes reconnues par `interpret` ; saisie
  guidée qui refuse toute valeur non proposée puis valide la combinaison par
  le catalogue (story 1) ; description lisible de la requête.
- `assistant.answer_guided` : catalogue puis formulation contrôlée (epic 4).
- `demo_chat.py` : exemples calculés au démarrage (repli sur la liste fixe si
  le graphe est indisponible) ; formulaire « Composer une question guidée »
  (listes avec recherche, nombre de marchés par valeur) ; refus expliqué.

## Vérification

- `tests/test_suggestions.py` : exemples reconnus pour plusieurs contenus,
  exemples qui changent avec les données, valeurs hors liste refusées (dont
  une saisie hostile), règles du catalogue conservées, lecture et filtrage
  des valeurs ; test Neo4j sur fixtures (valeurs lues, exemples avec résultat
  et preuves, requête guidée avec preuves).
- 2026-10-30 : story validée par l'utilisateur après démo sur le vrai graphe.

## Corrections faites pendant la story

- Formulation : une liste raccourcie pour le modèle porte son vrai total
  (`extrait`, `nombre_total`) ; la longueur d'un extrait n'est plus acceptée
  comme un chiffre (le modèle annonçait « 10 marchés modifiés »).
- Question 10 : chaque signal de qualité cite jusqu'à 5 marchés ou versions
  avec leur objet déclaré.
