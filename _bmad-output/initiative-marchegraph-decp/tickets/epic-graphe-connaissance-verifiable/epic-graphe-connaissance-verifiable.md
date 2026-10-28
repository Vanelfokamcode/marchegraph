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
- Source conflict: 2026-10-28 — Le Parquet initial contient plusieurs valeurs
  non nulles pour un même `uid` sur `objet` (5 734 marchés), `montant` (564),
  `procedure` (32), `dureeMois` (127) et `nature` (3). Pour `montant`, 17
  autres marchés ont à la fois une valeur et une valeur manquante ; pour
  `dureeMois`, 23. Le compte de marchés par `uid` reste univoque, mais une
  propriété scalaire unique ferait perdre des valeurs source ou en choisirait
  une arbitrairement.
- Decision: 2026-10-28 — L'utilisateur approuve un `Marche` par `uid` avec
  toutes les valeurs distinctes de `objet`, `montant`, `procedure`, `dureeMois`
  et `nature` conservées comme valeurs multiples ; la présence de lignes source
  sans valeur est signalée séparément. Une requête ne doit pas agréger
  silencieusement les montants multi-valués.
- Decision: 2026-10-28 — Pour les agrégations de montants, inclure une fois les
  marchés avec une seule valeur distincte, même si d'autres lignes sont sans
  montant en signalant ces absences ; exclure les marchés multi-valués du total
  et en rapporter le nombre. La story 3.5 établit le contrat commun de requête
  et de preuve que la story 3.6 réutilise.
- Source conflict: 2026-10-28 — Parmi les modifications notifiées en 2024–2025,
  83 500 `uid` distincts (65 953 en 2024 et 37 109 en 2025) n'ont aucune
  attribution initiale dans le Parquet préparé. Cela concerne 182 283 couples
  `uid`/`modification_id` (116 605 en 2024 et 65 678 en 2025) ; les relier à un
  marché initial exigerait d'élargir la portée ou de représenter explicitement
  l'absence de ce marché.
- Source conflict: 2026-10-28 — Plusieurs lignes source partagent une même
  version `(uid, modification_id)` ; les valeurs varient notamment sur
  `objet` (776 versions), `dureeMois` (378), `montant` (298), `procedure`
  (214), `titulaire_id` (63 644) et `nature` (1). Une propriété scalaire
  ferait perdre des valeurs.
- Decision: 2026-10-28 — Conserver chaque version de modification comme nœud
  identifié par `(uid, modification_id)` ; la relier au marché initial
  uniquement s'il existe dans le Parquet 2024–2025. Sinon, conserver le nœud
  sans lien, le marquer explicitement comme marché initial absent et rapporter
  le nombre de cas. Ne pas créer de marché placeholder ni compter ces versions
  comme des attributions initiales. Comme pour les marchés initiaux, conserver
  les valeurs distinctes et signaler séparément les valeurs manquantes au lieu
  de choisir arbitrairement une ligne source.
