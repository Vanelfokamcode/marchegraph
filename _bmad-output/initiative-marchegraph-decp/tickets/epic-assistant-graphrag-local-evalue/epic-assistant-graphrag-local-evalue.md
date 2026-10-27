---
tracker_id: ""
id: 4
type: epic
title: "Assistant GraphRAG local évalué"
parent: initiative-marchegraph-decp
covers: ["R4", "R6"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md"]
companions: []
after: ["epic-graphe-connaissance-verifiable"]
refined: false
risk: high
---

# Assistant GraphRAG local évalué

## Description

Construire un assistant local qui répond en français aux questions prises en
charge, relie ses réponses aux preuves du graphe et s'abstient lorsque les
éléments disponibles ne suffisent pas. Mesurer ses résultats contre une
baseline sans graphe.

## Outcome

Un analyste peut questionner le graphe en français et vérifier les preuves ou
les limites de chaque réponse ; l'évaluation documente les performances, les
hallucinations et les coûts.

## Done when

- Pour les questions prises en charge, les réponses sont en français et
  fournissent un chemin vérifiable dans le graphe ou une abstention explicite.
- L'évaluation rapporte la correction par question et la comparaison à une
  baseline LLM sans graphe ; le seuil est fixé après mesure de la baseline.
- Les hallucinations observées et les coûts sont rapportés.
- La vérification intégrée s'exécute localement ; aucune mise en production,
  interface soignée ou gestion d'utilisateurs n'est incluse.

## Boundaries

- Owns: interaction GraphRAG locale, production des preuves, abstention et
  protocole d'évaluation comparative.
- Does not own: préparation des données, résolution des identités, ontologie,
  validation du graphe ou réponses de référence ; l'epic 3 fournit ces
  contrats.
- Touch point: graphe interrogeable et réponses de référence validées par
  l'epic 3.
- Must not change: le système ne répond pas au-delà des preuves disponibles.
- Must not change: la démonstration et les sorties dérivées restent locales.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R4, R6; Constraints C3, C7.

## Notes

- Waits on epic 3 because: l'assistant s'appuie sur le graphe interrogeable,
  les réponses de référence et le contrat de preuve établis par l'epic.
