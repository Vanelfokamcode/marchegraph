---
type: initiative
title: MarchéGraph DECP
parent: none
sources:
  - docs/brief.md
  - docs/profilage-initial.md
companions: []
after: []
risk: medium
---

# MarchéGraph DECP

## Description

MarchéGraph transforme les données d'attribution DECP en un graphe de
connaissances interrogeable et un assistant en français qui fournit des
réponses vérifiables. Cette initiative s'appuie sur le brief et le profilage
initial pour permettre à un analyste d'explorer les marchés publics tout en
rendant visibles les limites des données.

## Outcome

Un analyste peut explorer les attributions DECP de 2025 toutes régions,
comparer 2024 et poser les questions métier retenues dans un assistant
GraphRAG qui cite son chemin dans le graphe ou indique qu'il ne sait pas.

## Requirements

- R1 (brief — Critères de réussite) : Le jeu analytique DECP peut être
  reconstruit avec une commande documentée depuis un snapshot Parquet identifié,
  et son profil de qualité et sa provenance sont consultables.
- R2 (profilage — Périmètre et méthode) : Les statistiques d'attribution
  annuelle comptent les `uid` distincts des lignes où `modification_id = 0` ;
  les modifications restent analysables séparément sans gonfler les comptes
  d'attribution initiale.
- R3 (brief — Questions de référence) : Le graphe permet d'évaluer chacune des
  dix questions métier de référence avec une réponse attendue ou une limite
  explicite liée aux données disponibles.
- R4 (brief — Objectif; plan utilisateur — CH. 12) : Pour les questions prises
  en charge, l'assistant répond en français avec un chemin vérifiable dans le
  graphe et s'abstient lorsque les données ne permettent pas d'étayer une
  réponse.
- R5 (brief — Critères de réussite) : La qualité de la résolution d'entités
  titulaires est mesurée sur un échantillon vérifié manuellement et ses
  métriques sont rapportées.
- R6 (brief — Critères de réussite) : L'évaluation rapporte la correction par
  question, compare l'assistant à un LLM sans graphe et documente les
  hallucinations observées et les coûts.
- R7 (brief — Périmètre) : Le modèle de domaine approuvé dispose de règles de
  validation répétables et chaque enregistrement invalide peut être relié à la
  règle qu'il enfreint.

## Constraints

- C1 (brief — Données; profilage — Volume et répartition géographique) :
  2025 toutes régions est le périmètre principal et 2024 une comparaison
  secondaire ; la région est celle de l'acheteur. Dans le snapshot profilé,
  2025 compte 315 998 lignes d'attribution pour 273 425 `uid` distincts ;
  l'Île-de-France en représente 40 998 (14,99 %) et 1 999 marchés n'ont pas de
  région renseignée. Les profils mensuels 2024 et 2025 ont une saisonnalité
  similaire, sans rampe de collecte évidente au début de 2024.
- C2 (profilage — Volume et versions) : Le snapshot comporte 271 210 lignes de
  modification notifiées en 2025 pour 104 722 `uid` distincts ; plusieurs
  lignes peuvent décrire un même marché, notamment du fait des titulaires.
- C3 (profilage — Identifiants des titulaires; Valeurs manquantes) : Le champ
  `titulaire_id` manque sur 1,56 % des lignes d'attribution 2025 contre 11,81 %
  en 2024 ; toute comparaison de résolution d'entités entre années doit
  signaler cet écart. Le type `SIRET` est présent sur 97,93 % des lignes 2025,
  avec une variante de casse à normaliser.
- C4 (profilage — Montants et dates de publication) : Les délais de publication
  négatifs (4,24 % en 2025, 3,76 % en 2024) et les montants signalés `suspect`
  ou `aberrant` (7 995 lignes d'attribution initiale en 2025) ne sont pas
  exclus automatiquement ; leur traitement doit être mesuré et documenté.
- C5 (brief — Données; Hors périmètre) : Le périmètre porte sur les DECP
  publiées, notamment les marchés soumis au seuil de 40 000 euros HT ; il ne
  couvre pas l'ensemble de la commande publique, les paiements, les factures
  ou l'exécution financière.
- C6 (plan utilisateur — Règle d'or) : Les concepts, relations et arbitrages de
  l'ontologie sont décidés par l'utilisateur et documentés pour qu'il puisse
  les défendre.
- C7 (brief — Risques; Hors périmètre) : Les analyses restent neutres et
  agrégées ; la démonstration reste locale et aucune donnée DECP ligne à ligne
  ni aucun résultat dérivé n'est publié. La fiche de la source indique la
  Licence Ouverte 2.0, qui ne règle pas à elle seule les données personnelles.
  La mise en production, une interface soignée et la gestion d'utilisateurs
  sont exclues.
- C8 (brief — Périmètre) : Le brief propose OWL pour l'ontologie, SKOS pour CPV
  et SHACL pour la validation ; ces formats restent soumis aux décisions de
  modélisation de l'utilisateur.

## Done when

- Une commande documentée reconstruit le jeu sélectionné à partir d'un snapshot
  identifié et produit un rapport de provenance et de qualité.
- Les comptes d'attribution initiale utilisent des `uid` distincts et les
  modifications peuvent être analysées sans double comptage.
- Les dix questions de référence ont des résultats vérifiables ou une limite
  documentée ; le rapport de test présente la correction par question et le
  seuil retenu.
- La résolution d'entités titulaires est évaluée sur un échantillon vérifié
  manuellement.
- Les données du graphe passent les contraintes de validation retenues, les
  enregistrements rejetés indiquent la règle concernée et les choix de
  modélisation sont documentés et défendables par l'utilisateur.
- L'assistant GraphRAG fournit un chemin vérifiable ou s'abstient, et son
  évaluation compare ses réponses à une baseline sans graphe tout en rapportant
  les hallucinations et les coûts.

## Boundaries

- Touch point: DECP Parquet, profilage et transformation — owner: epic à définir
  au découpage.
- Touch point: graphe de connaissances, requêtes et assistant GraphRAG — owner:
  epic à définir au découpage.
- Tracer path: snapshot DECP → profilage et transformations documentés → graphe
  interrogeable → réponse en français avec preuve ou abstention.
- Must not change: le projet ne prétend pas décrire les paiements ou
  l'exécution financière des marchés.
- Must not change: aucune accusation ni aucun jugement sur des acteurs nommés.
- Must not change: la démonstration et les sorties dérivées des données restent
  locales.

## References

- source — `docs/brief.md`, Objectif; Données; Questions de référence; Périmètre;
  Hors périmètre; Critères de réussite; Risques.
- source — `docs/profilage-initial.md`, Périmètre et méthode; Résultats
  observés; Décisions de périmètre proposées; Limites et prochaines
  vérifications.
- user direction — plan du projet transmis dans cette conversation, Règle
  d'or; CH. 12.

## Notes

- Decision: 2026-10-27 — 2025 toutes régions est le périmètre principal, 2024
  la comparaison secondaire, et la région est celle de l'acheteur.
- Decision: 2026-10-27 — Les attributions initiales sont comptées par `uid`
  distinct et les modifications restent analysables séparément.
- Decision: 2026-10-27 — GraphRAG fait partie de cette initiative.
- Decision: 2026-10-27 — Mesurer d'abord une baseline sur les dix questions,
  puis fixer un seuil de réussite ; la proposition de huit sur dix n'est pas
  un critère immédiat.
- Open question: Neo4j comme base principale et l'export RDF limité restent des
  propositions d'architecture à valider.
- Open question: Comment représenter les versions de modification et les
  marchés avec plusieurs titulaires sans fixer ici la modélisation ?
- Decision: 2026-10-27 — Identifier le Parquet local par le SHA-256
  `b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0` et sa
  taille de 250 253 419 octets ; cette empreinte ne donne pas sa date
  d'extraction.
- Decision: 2026-10-27 — Garder la démonstration locale et ne publier ni les
  lignes DECP ni les résultats dérivés.
- Decision: 2026-10-27 — Décider à la fin du projet si le code et la
  documentation technique seront publiés ; les données et résultats restent
  locaux.
- Open question: Quelles règles de protection et d'agrégation s'appliquent
  avant toute publication de données potentiellement personnelles ?
