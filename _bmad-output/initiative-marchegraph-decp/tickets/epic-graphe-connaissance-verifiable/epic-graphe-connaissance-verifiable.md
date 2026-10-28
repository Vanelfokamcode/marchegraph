---
tracker_id: ""
id: 3
type: epic
title: "Graphe de connaissance vérifiable"
parent: initiative-marchegraph-decp
covers: ["R3", "R7"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: ["_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md"]
after: ["epic-fondation-decp-reproductible", "epic-resolution-identites-titulaires"]
refined: true
risk: high
status: in-progress
---

# Graphe de connaissance vérifiable

## Description

Formaliser le modèle de domaine approuvé, construire localement le graphe DECP
et vérifier les dix questions de référence, en rendant les limites des données
visibles lorsqu'une réponse n'est pas étayée.

## Outcome

L'utilisateur peut interroger un graphe local dont les règles de validation et
les réponses de référence sont répétables et explicables.

## Requirements

- R3 (parent R3) : Le graphe permet d'évaluer chacune des dix questions métier
  de référence avec une réponse attendue ou une limite explicite liée aux
  données disponibles.
- R7 (parent R7) : Le modèle de domaine approuvé dispose de règles de validation
  répétables et chaque enregistrement invalide peut être relié à la règle qu'il
  enfreint.

## Constraints

- C2 (parent C2) : Le snapshot comporte 271 210 lignes de modification
  notifiées en 2025 pour 104 722 `uid` distincts ; plusieurs lignes peuvent
  décrire un même marché, notamment du fait des titulaires.
- C6 (parent C6) : Les concepts, relations et arbitrages de l'ontologie sont
  décidés par l'utilisateur et documentés pour qu'il puisse les défendre.
- C7 (parent C7) : Les analyses restent neutres et agrégées ; la démonstration
  reste locale et aucune donnée DECP ligne à ligne ni aucun résultat dérivé
  n'est publié. La mise en production, une interface soignée et la gestion
  d'utilisateurs sont exclues.
- C8 (parent C8) : Le brief propose OWL pour l'ontologie, SKOS pour CPV et SHACL
  pour la validation ; ces formats restent soumis aux décisions de modélisation
  de l'utilisateur.
- AD-1 : Le graphe consomme le Parquet préparé et les contrats de données
  existants ; les modifications restent distinguables des attributions
  initiales.
- AD-2 : Neo4j est l'unique source de vérité modifiable du graphe ; le RDF est
  généré depuis Neo4j avec le mapping approuvé par l'utilisateur.
- AD-3 : Les requêtes utilisent des Cypher paramétrés et les résultats
  structurés conservent les références de preuve issues du graphe.
- AD-4 : Le traitement, Neo4j et les sorties restent locaux ; les données et
  sorties dérivées ne sont pas publiées.
- AD-5 : Les contrats de domaine restent indépendants de Neo4j et des
  bibliothèques d'interface ou de persistance.

## Done when

- Le modèle et les règles de validation retenus sont documentés et exécutables
  de façon répétable ; un enregistrement invalide peut être relié à sa règle.
- Le graphe consomme le jeu préparé et le résultat de rapprochement des
  titulaires, avec leurs limites conservées.
- Un export RDF est généré depuis Neo4j selon le mapping approuvé, sans créer
  un second chemin d'écriture du graphe.
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
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-1–AD-5.
- prototypes — `docs/exemple/ontologie.ttl`, `docs/exemple/formes.ttl`, `docs/exemple/neo4j.cypher`; exemples à évaluer, sans choix de modélisation imposé.

## Notes

- Waits on epic 1 because: la construction du graphe dépend du schéma stable
  et du jeu analytique préparé.
- Waits on epic 2 because: le graphe consomme le résultat de rapprochement des
  titulaires sans redéfinir ses règles.
- Decision: 2026-10-28 — L'utilisateur choisit de raffiner l'epic à partir du
  périmètre et de l'architecture approuvés sans lancer `bmad-architecture`
  auparavant.
- Decision: 2026-10-28 — Le tracer bullet est l'entrée 1 : approbation du
  modèle par l'utilisateur puis démonstration locale d'un cas synthétique
  traversant le chargement, la validation, une réponse avec preuve et l'export
  RDF.
- Decision: 2026-10-28 — Un `Marche` canonique par `uid` peut être relié à
  plusieurs titulaires ; les liens multiples ne créent pas de nouveaux
  marchés.
- Decision: 2026-10-28 — Chaque modification est représentée comme un nœud
  de version relié au marché initial, sans être comptée comme un marché
  initial supplémentaire.
- Decision: 2026-10-28 — Utiliser OWL pour le modèle, SKOS pour les concepts
  CPV et SHACL pour la validation ; l'export RDF est généré depuis Neo4j,
  source de vérité opérationnelle.
- Decision: 2026-10-28 — Le tracer bullet est uniquement synthétique ; il ne
  charge ni ne publie de données DECP.
- Decision: 2026-10-28 — Charger d'abord les attributions initiales, puis les
  modifications ; appliquer ensuite les validations, dérouler les requêtes de
  référence par groupes ordonnés, effectuer le refactor sweep et terminer par
  une vérification intégrée de bout en bout.
- Open question: Quelles bibliothèques locales assurent la sérialisation RDF
  et l'exécution SHACL avec les versions verrouillées du projet ?
