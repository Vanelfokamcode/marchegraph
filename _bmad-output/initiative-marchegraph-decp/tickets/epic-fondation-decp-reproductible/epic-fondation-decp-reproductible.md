---
tracker_id: ""
id: 1
type: epic
title: "Fondation DECP reproductible"
parent: initiative-marchegraph-decp
covers: ["R1", "R2"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: []
after: []
refined: false
risk: medium
---

# Fondation DECP reproductible

## Description

Construire une préparation DECP locale, documentée et rejouable, fondée sur le
snapshot identifié et le périmètre décidé. Elle fournit le jeu analytique 2025,
la comparaison 2024, leur provenance et leur profil de qualité.

## Outcome

Une personne peut reconstruire localement le jeu analytique et inspecter ses
comptes d'attributions initiales et de modifications sans les confondre.

## Done when

- Une commande locale documentée reconstruit le jeu sélectionné depuis le
  snapshot Parquet identifié.
- La provenance et le profil de qualité du jeu sont consultables, y compris
  les limites et anomalies observées.
- Les comptes d'attributions initiales reposent sur les `uid` distincts ;
  les modifications sont analysables séparément.
- La vérification intégrée s'exécute localement et les données de ligne ne sont
  pas publiées.

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
