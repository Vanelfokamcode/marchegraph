# Brief du projet : MarchéGraph

## Dépôt
- Nom : `marchegraph`
- Description GitHub : Knowledge graph of French public procurement (DECP open data): data cleaning, entity resolution, OWL/SKOS ontology, Neo4j, and a GraphRAG assistant that cites its graph path.
- Sujets (topics) : knowledge-graph, ontology, neo4j, graphrag, duckdb, open-data, public-procurement, data-engineering

## Contexte
La commande publique française publie ses attributions de marchés en open data (DECP, data.gouv.fr). Les données sont nombreuses mais hétérogènes : sources multiples, versions successives d'un même marché, fournisseurs écrits de plusieurs façons, champs de texte libre. Elles décrivent l'attribution du marché, pas les paiements.

## Problème
Il est difficile de répondre à des questions simples sur ces données (qui achète quoi, auprès de qui, selon quelle procédure) sans nettoyer, relier et modéliser les informations. Un LLM seul répond de façon plausible mais sans preuve.

## Objectif
Construire un graphe de connaissances de la commande publique, fondé sur une ontologie, puis un assistant qui répond en français en citant le chemin suivi dans le graphe.

## Pour qui
- Utilisateur fictif de l'assistant : un analyste qui veut comprendre la commande publique sans écrire de requête.

## Données
- Source : DECP consolidées au format tabulaire (Parquet), data.gouv.fr. Schéma publié, identifiant global d'un marché : `uid`.
- Couverture : seuls les marchés d'au moins 40 000 euros HT sont concernés par l'obligation de publication. Le projet ne couvre donc pas toute la commande publique.
- Régime de publication : nouveau cadre depuis le 1er janvier 2024 (arrêtés du 22 décembre 2022).
- Année retenue : 2025 (année complète et close). 2024 est écartée comme base car la publication a démarré en cours d'année, avec un risque de disparité.
- Sous-ensemble de départ : Île-de-France, selon la région de l'acheteur (et non du lieu d'exécution). À confirmer par le profilage.
- Étude de cas : 2024 contre 2025, pour mesurer la montée en charge de la publication.
- Licence et données personnelles (entrepreneurs individuels) : à vérifier avant toute publication.

## Périmètre 
- Profilage et nettoyage des DECP (DuckDB).
- Résolution d'entités sur les fournisseurs.
- Ontologie (OWL, SKOS pour les codes CPV) et contraintes SHACL.
- Graphe Neo4j, avec un export RDF d'un sous-ensemble.
- Assistant GraphRAG et évaluation.

## Hors périmètre
- Paiements, factures, exécution des marchés (non couverts par les DECP).
- Mise en production, interface soignée, gestion d'utilisateurs.
- Accusations ou jugements sur des acteurs nommés : analyses agrégées et neutres seulement.

## Questions de référence (à valider)
1. Quels acheteurs ont attribué le plus de marchés sur l'année et le territoire retenus ?
2. Quels titulaires reviennent le plus chez un acheteur donné ?
3. Quel montant total est attribué par famille de codes CPV ?
4. Quels marchés ont été modifiés après attribution, et combien de fois ?
5. Quelles procédures sont utilisées selon la nature du marché ?
6. Quels titulaires travaillent avec plusieurs acheteurs différents ?
7. Quels marchés d'un thème donné (à partir du texte de l'objet) ont été attribués dans la région ?
8. Quelle est la durée moyenne des marchés par famille CPV ?
9. Quels fournisseurs apparaissent sous plusieurs écritures de leur nom ?
10. Quels marchés ont des données manquantes ou incohérentes ?

## Critères de réussite (propositions, à décider après le profilage)
- Le pipeline se rejoue de bout en bout avec une seule commande.
- Le taux d'erreur de la résolution d'entités est mesuré sur un échantillon vérifié à la main.
- Au moins 8 questions de référence sur 10 reçoivent une réponse correcte et vérifiable.
- L'assistant fait mieux qu'un LLM seul sur le même jeu de questions, ou on explique pourquoi non.
- Je peux expliquer chaque choix de modélisation sans notes.

## Jalons (parties du plan)
1. Cadrage et BMAD : brief, PRD, architecture, epics.
2. Données : profilage, nettoyage, versions, résolution d'entités.
3. Ontologie : étude de l'existant, modèle, OWL, SKOS, SHACL.
4. Graphe : chargement Neo4j, requêtes Cypher et SPARQL.
5. IA : extraction depuis le texte, GraphRAG, évaluation (partie optionnelle).
6. Finalisation : tests, coûts, README, démo.
Le minimum présentable correspond aux parties 1 à 4.

## Risques principaux
- Qualité et couverture inégales des sources et des mois.
- Biais de la région : région de l'acheteur, pas du lieu d'exécution.
- Extraction par LLM plus lourde que prévu : la partie 05 est optionnelle.
- Montants déclarés à la notification : pour les accords-cadres, ce sont des maximums.

## Décisions ouvertes
- Confirmer Île-de-France et 2025 après profilage mensuel 2024 contre 2025.
- Base principale : Neo4j, avec RDF seulement en export limité (proposition).
