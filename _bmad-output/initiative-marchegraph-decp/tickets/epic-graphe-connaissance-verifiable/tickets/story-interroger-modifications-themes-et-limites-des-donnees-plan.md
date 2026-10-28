---
title: "Interroger modifications, thèmes et limites des données"
ticket: 7
status: done
---

# Requêtes de modifications, de thèmes et de qualité

## Décisions appliquées

- La question 4 filtre les versions par année de notification. Elle distingue
  les versions rattachées à un marché initial des versions orphelines du
  snapshot, sans créer de faux marchés ; les détails et preuves sont bornés.
- La question 7 recherche une sous-chaîne insensible à la casse dans les
  valeurs d'objet. Un marché n'est rattaché à une région que si une seule
  valeur régionale distincte est disponible ; les régions manquantes ou
  multivaluées sont comptées et exposées comme limites.
- Le chargement initial conserve les valeurs de région acheteur et leur
  marqueur de manque au niveau du marché. La question 1 reste nationale,
  conformément au périmètre décidé pour cette question.
- La question 9 regroupe les variantes sous l'identifiant titulaire typé déjà
  résolu. Les noms seuls ne fusionnent jamais des identités ; le cas sans
  titulaire multivalué retourne un résultat vide explicite.
- La question 10 présente les champs manquants et multivalués des marchés et
  versions de modification. Une valeur multivaluée est signalée comme
  hétérogénéité conservée, pas automatiquement comme erreur. Les preuves sont
  limitées à 25 exemples par signal et indiquent si elles sont complètes.
- Les preuves référencent désormais un type et un identifiant de nœud, afin de
  couvrir les marchés, titulaires et versions de modification.

## Vérification

- Les tests déterministes couvrent les quatre questions, les preuves, les
  limites, le plafonnement des résultats thématiques, les échantillons de
  preuves incomplets et l'absence de variantes de noms.
- La suite complète passe : 37 tests.
- Les questions 4, 7, 9 et 10 ont été exécutées sur Neo4j local après le
  chargement idempotent de la région acheteur.
- `compileall` et `git diff --check` passent. La documentation README décrit
  les requêtes et leurs limites ; aucun résultat dérivé n'est ajouté au dépôt.
