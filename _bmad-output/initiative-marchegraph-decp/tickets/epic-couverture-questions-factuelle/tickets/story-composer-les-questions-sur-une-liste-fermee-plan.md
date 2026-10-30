---
title: "Composer les questions sur une liste fermée de mesures, regroupements et filtres"
ticket: 1
status: done
---

# Catalogue de questions composables

## Catalogue approuvé (2026-10-30)

- Mesures : nombre de marchés, montant total déclaré, montant moyen déclaré,
  durée moyenne, nombre de modifications.
- Regroupements : aucun, acheteur, titulaire, famille CPV, région de
  l'acheteur, procédure, nature, année.
- Filtres : année, région, acheteur, titulaire, famille CPV, procédure,
  nature, tranche de montant, thème dans l'objet.
- Refusés avec motif : modifications par titulaire ou procédure ; tranche de
  montant avec durée moyenne ; regroupement par titulaire sans année explicite ;
  regroupement par année avec une année fixée.
- Q4, Q9 et Q10 gardent leurs requêtes ; les dix questions de l'epic 4 ne
  changent pas.

## Portée livrée

- `src/marchegraph/queries/catalogue.py` : module pur, `CatalogueQuery` et
  `validate` (refus explicites).
- `src/marchegraph/graph/catalogue_queries.py` : `build_cypher` (fragments
  fixes, valeurs en paramètres), `aggregate` (règles de l'epic 3 : uid
  distincts, valeurs multiples exclues et comptées, montants en `Decimal`,
  familles CPV par la même fonction que Q3/Q8, preuves limitées à 25 marchés
  par groupe), `run_catalogue`.
- `src/marchegraph/graph/contracts.py` : `CatalogueRow`.

## Vérification

- `tests/test_catalogue.py` : refus motivés, acceptation de toutes les autres
  combinaisons, aucune valeur saisie dans le texte Cypher, agrégations (montant,
  moyennes, groupes multiples, marchés non rattachés, tranche de montant,
  famille CPV, limite) ; test Neo4j sur fixtures : cohérence avec Q1, Q3, Q8 et
  exécution de toutes les combinaisons.
- 2026-10-30 : `tests/test_catalogue.py` 8 tests OK, dont l'exécution sur le
  graphe de fixtures Neo4j (catégories identiques à Q1, Q3 et Q8 ; toutes les
  combinaisons acceptées exécutées avec preuves et limites) ; suite complète
  77 tests OK.
