---
tracker_id: ""
id: 1
type: epic
title: "Fondation DECP reproductible"
parent: initiative-marchegraph-decp
covers: ["R1", "R2"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: ["_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md"]
after: []
refined: true
risk: medium
status: in-progress
---

# Fondation DECP reproductible

## Description

Construire une préparation DECP locale, documentée et rejouable, fondée sur le
snapshot identifié et le périmètre décidé. Elle fournit le jeu analytique 2025,
la comparaison 2024, leur provenance, leur profil de qualité et le socle local
minimal qui permet de rejouer le pipeline.

## Outcome

Une personne peut reconstruire localement le jeu analytique et inspecter ses
comptes d'attributions initiales et de modifications sans les confondre.

## Requirements

- R1 (parent R1) : Le jeu analytique DECP peut être reconstruit avec une
  commande documentée depuis un snapshot Parquet identifié, et son profil de
  qualité et sa provenance sont consultables.
- R2 (parent R2) : Les statistiques d'attribution annuelle comptent les `uid`
  distincts des lignes où `modification_id = 0` ; les modifications restent
  analysables séparément sans gonfler les comptes d'attribution initiale.

## Constraints

- C1 (parent C1) : 2025 toutes régions, selon la région de l'acheteur, est le
  périmètre principal ; 2024 est une comparaison secondaire.
- C2 (parent C2) : Le volume de lignes de modification n'est pas assimilé au
  nombre de marchés distincts ni aux statistiques d'attribution initiale.
- C3 (parent C3) : Le profil de qualité signale l'écart de valeurs
  `titulaire_id` manquantes entre 2024 et 2025.
- C4 (parent C4) : Les anomalies de montant et les délais de publication
  négatifs ne sont pas exclus automatiquement ; leur traitement est documenté.
- C5 (parent C5) : Le jeu décrit les DECP publiées et ne prétend pas couvrir
  les paiements ou l'exécution des marchés.
- C7 (parent C7) : Le traitement et les sorties restent locaux ; aucune donnée
  DECP ligne à ligne ni aucun résultat dérivé n'est publié.

## Done when

- Une commande locale documentée reconstruit le jeu 2025 principal et la
  comparaison 2024 depuis le snapshot Parquet identifié, et produit le jeu
  préparé, le manifeste de provenance et le rapport de qualité prévus par
  l'architecture.
- Le manifeste inclut l'empreinte SHA-256 et la taille du snapshot ; si la date
  d'extraction ne peut pas être établie, elle est indiquée comme inconnue.
- Le rapport de qualité rend consultables les limites, champs manquants et
  anomalies observés, sans les masquer ni les supprimer silencieusement.
- Les comptes d'attributions initiales reposent sur les `uid` distincts ;
  les modifications sont analysables séparément.
- La vérification intégrée s'exécute localement, sans publier de données de
  ligne ni de résultats dérivés.

## Boundaries

- Owns: lecture du snapshot, profilage, transformations et contrat du jeu
  analytique préparé.
- Does not own: rapprochement des titulaires, ontologie, graphe ou assistant ;
  ces résultats relèvent des epics suivants.
- Touch point: DECP Parquet et script existant de profilage.
- Must not change: 2025 toutes régions reste le périmètre principal ; 2024
  reste une comparaison secondaire.
- Must not change: les montants signalés et dates incohérentes ne sont pas
  exclus automatiquement.
- Must not change: le snapshot et les résultats dérivés restent locaux.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R1–R2; Constraints C1, C3–C5, C7.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-1, AD-4–AD-5.

## Notes

- Decision: 2026-10-27 — L'empreinte et la taille identifient la copie du
  snapshot, mais pas sa date d'extraction ; inscrire cette date comme inconnue
  dans le manifeste si elle ne peut pas être établie.
- Decision: 2026-10-27 — Laisser aux stories le schéma exact du manifeste,
  l'organisation des fichiers préparés et le découpage des tests ; le contrat
  de sortie est Parquet préparé, manifeste et rapport de qualité.
- Decision: 2026-10-27 — Le tracer bullet est la story 1, « Construire et
  exécuter le pipeline DECP », qui établit la commande locale reproductible et
  le contrat de sortie (`data/prepared/decp.parquet`,
  `data/prepared/manifest.json`, `data/prepared/quality-report.md`) ; la story
  2 complète le rapport de qualité après ce pipeline. Les sorties restent
  locales et non suivies par Git ; le détail des schémas reste à fixer dans
  les tickets détaillés.
