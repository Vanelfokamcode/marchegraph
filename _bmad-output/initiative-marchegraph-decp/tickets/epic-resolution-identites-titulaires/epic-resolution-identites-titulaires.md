---
tracker_id: ""
id: 2
type: epic
title: "Résolution des identités titulaires"
parent: initiative-marchegraph-decp
covers: ["R5"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: []
after: ["epic-fondation-decp-reproductible"]
refined: false
risk: high
---

# Résolution des identités titulaires

## Description

Rapprocher les identités de titulaires présentes dans le jeu analytique préparé
selon des règles auditables, puis mesurer la qualité du rapprochement sur un
échantillon vérifié manuellement.

## Outcome

Les rapprochements de titulaires et leurs limites sont documentés et évalués,
en tenant compte des identifiants manquants et des différences de complétude
entre 2024 et 2025.

## Done when

- Les règles de rapprochement et leurs sorties sont reproductibles sur le jeu
  analytique fourni par l'epic 1.
- Un échantillon de résultats est vérifié manuellement et des métriques de
  qualité sont rapportées.
- Les limites, notamment les identifiants absents et la complétude différente
  entre années, sont explicites.
- La vérification intégrée s'exécute localement sans publier de données ou de
  résultats dérivés.

## Boundaries

- Owns: normalisation et rapprochement des identités titulaires, échantillon
  vérifié et rapport de mesure.
- Does not own: représentation ontologique des titulaires ni décisions sur les
  concepts et relations du graphe ; elles relèvent de l'utilisateur et de
  l'epic 3.
- Touch point: le schéma et les enregistrements titulaires préparés par l'epic
  1.
- Must not change: ne pas traiter une identité manquante comme une preuve
  d'absence de titulaire.
- Must not change: aucune donnée DECP ligne à ligne ni aucun résultat dérivé
  n'est publié.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R5; Constraints C2, C3, C7.

## Notes

- Waits on epic 1 because: le rapprochement doit consommer le jeu préparé et
  son contrat de données.
