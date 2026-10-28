---
title: "Interroger montants et durées par CPV"
ticket: 6
status: done
---

# Agrégations par famille CPV avec limites et preuves

## Décisions appliquées

- Une famille CPV est le groupe indiqué par les trois premiers chiffres du
  code.
- Une valeur unique de montant ou durée est comptée une fois, même si d'autres
  lignes source sont sans valeur ; ces manques sont signalés.
- Les marchés à montants distincts multiples sont exclus du total monétaire ;
  les marchés à durées distinctes multiples sont exclus de la moyenne. Les
  deux catégories sont comptées et exposées séparément.
- Les sommes et moyennes sont calculées en `Decimal`. Les résultats portent
  sur les montants déclarés, et non les paiements ; un montant d'accord-cadre
  peut être un plafond.
- Chaque ligne de résultat porte des preuves CPV et mesure. Pour les agrégats
  volumineux, les preuves sont limitées à 25 marchés par mesure, tandis que
  les agrégats couvrent tous les marchés admissibles.

## Vérification

- Les fixtures déterministes couvrent un marché multi-titulaire, les montants
  et durées uniques, les manques source, les montants multivalués, les durées
  multivaluées et les marchés associés à plusieurs familles.
- Les valeurs non numériques font échouer explicitement la requête.
- L'exécution locale des questions 3 et 8 sur Neo4j a terminé avec des résultats
  structurés et des références de preuve ; les résultats dérivés ne sont pas
  inclus dans le dépôt.
