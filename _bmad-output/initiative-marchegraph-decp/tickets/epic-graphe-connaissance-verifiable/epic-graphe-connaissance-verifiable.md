---
tracker_id: ""
id: 3
type: epic
title: "Graphe de connaissance vérifiable"
parent: initiative-marchegraph-decp
covers: ["R3", "R7"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: []
after: ["epic-fondation-decp-reproductible", "epic-resolution-identites-titulaires"]
refined: false
risk: high
---

# Graphe de connaissance vérifiable

## Description

Formaliser le modèle de domaine approuvé, construire localement le graphe DECP
et vérifier les dix questions de référence, en rendant les limites des données
visibles lorsqu'une réponse n'est pas étayée.

## Outcome

L'utilisateur peut interroger un graphe local dont les règles de validation et
les réponses de référence sont répétables et explicables.

## Done when

- Le modèle et les règles de validation retenus sont documentés et exécutables
  de façon répétable ; un enregistrement invalide peut être relié à sa règle.
- Le graphe consomme le jeu préparé et le résultat de rapprochement des
  titulaires, avec leurs limites conservées.
- Chaque question de référence a une réponse vérifiable ou une limite explicite
  liée aux données disponibles.
- La vérification intégrée s'exécute localement et les décisions de
  modélisation sont approuvées par l'utilisateur.

## Boundaries

- Owns: modèle de domaine, validation, chargement du graphe et requêtes de
  référence.
- Does not own: préparation DECP, rapprochement des identités ou dialogue et
  évaluation de l'assistant ; les contrats d'entrée sont produits par les
  epics 1 et 2, l'assistant relève de l'epic 4.
- Touch point: les fichiers de prototypes sous `docs/exemple/` sont des
  références à évaluer, pas une architecture de production imposée.
- Must not change: l'utilisateur décide des concepts, relations et arbitrages
  de l'ontologie.
- Must not change: les choix sur modifications et marchés multi-titulaires ne
  sont pas présumés ; ils sont décidés avec l'utilisateur.
- Must not change: le graphe et ses sorties restent locaux.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R3, R7; Constraints C2, C6–C8.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-1–AD-3, AD-5.

## Notes

- Waits on epic 1 because: la construction du graphe dépend du schéma stable
  et du jeu analytique préparé.
- Waits on epic 2 because: le graphe consomme le résultat de rapprochement des
  titulaires sans redéfinir ses règles.
