---
title: "Valider les données du graphe et tracer les rejets"
ticket: 4
status: built
---

# Validation locale et traçabilité des rejets

## Portée

- Appliquer les formes SHACL existantes au graphe synthétique RDF.
- Associer un identifiant stable `MG-VAL-*` à chaque règle déclarée.
- Pour chaque nœud rejeté, conserver ses triples RDF et les motifs de rejet,
  avec l'identifiant de règle, le chemin et la valeur en cause lorsqu'ils sont
  disponibles.
- Permettre l'écriture locale d'un rapport JSON Lines sans retirer de données
  du graphe source.

## Vérification

- Un SIRET synthétique invalide est signalé par `MG-VAL-TITULAIRE-SIRET-006`.
- Un marché sans acheteur est signalé par `MG-VAL-MARCHE-ACHETEUR-001`.
- Les rejets exposent toujours les triples du nœud concerné et leur motif ; le
  JSON Lines conserve ces données et leurs règles.
- Le graphe synthétique valide reste conforme aux formes SHACL.
