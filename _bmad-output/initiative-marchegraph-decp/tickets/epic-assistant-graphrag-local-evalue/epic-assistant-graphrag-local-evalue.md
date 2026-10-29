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
refined: true
risk: high
status: in-progress
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
- Must not change: aucun service LLM distant n'est appelé ; un modèle local
  n'est retenu qu'après un test de capacité.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R4, R6; Constraints C3, C7, C9.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-3–AD-5.

## Notes

- Waits on epic 3 because: l'assistant s'appuie sur le graphe interrogeable,
  les réponses de référence et le contrat de preuve établis par l'epic.
- Decision: 2026-10-29 — Cible : projet complet. Compréhension de la question
  déterministe ; AD-3 inchangée. Questions prises en charge : les dix
  questions de référence de l'epic 3.
- Decision: 2026-10-29 — Une réponse est correcte si son résultat structuré
  est identique à la référence, ou si l'abstention attendue est effective.
  Hallucination : tout fait, chiffre ou entité du texte absent du résultat
  structuré reçu. Coûts : latence et mémoire locales.
- Decision: 2026-10-29 — Baseline obligatoire : le même modèle local sans
  graphe. Baseline SQL DuckDB sur le Parquet : option à faire approuver.
- Decision: 2026-10-29 — Découpage en sept stories approuvé par l'utilisateur
  (`tickets/tickets.toml`). Le test de capacité de la phase A
  (`docs/spike-modele-local-resultats.md`, `llama3.1:8b` et `qwen3:8b`,
  données synthétiques) est le point de départ de la story 1, pas un livrable
  accepté.
- Open question: La story 3.9 est en revue ; l'epic 3 doit être clos avant de
  démarrer cet epic. Résolu le 2026-10-29 : l'epic 3 est clos.
- Open question: Données d'évaluation : fixtures de l'epic 3 ou snapshot
  d'origine (SHA-256 `b39257f1…`) ; un snapshot retéléchargé est exclu.
- Open question: Notation de la baseline sans graphe (texte libre) : manuelle,
  extraction des chiffres comparée à la référence, ou les deux.
- Open question: Inclure ou non la baseline SQL DuckDB.
- Open question: Nombre et rédaction des questions à abstention attendue.
- Open question: Échec du contrôle des chiffres : repli sur le gabarit
  déterministe (proposé) ou abstention.
- Open question: Emplacement du code (`src/marchegraph/queries/` et `app.py`
  selon l'architecture, contre `graph/queries.py` et `demo_chat.py`
  aujourd'hui).
- Open question: Ajouter un modèle d'environ 4 milliards de paramètres au test
  de la story 1 (0,5 Go de RAM libre observée avec `qwen3:8b` et Neo4j).
  Résolu le 2026-10-29 : `qwen3:4b-instruct` et `phi4-mini:3.8b` testés.
- Decision: 2026-10-29 — Story 1 : l'utilisateur retient `phi4-mini:3.8b`
  (3,1 Go chargés, 5 à 16 s par cas sur CPU, aucun chiffre inventé en
  chiffres) pour la durée et la mémoire. Le même modèle sert à la baseline
  sans graphe.
- Note pour la story 3: le test a montré des erreurs que le contrôle des
  chiffres ne voit pas : nombres écrits en lettres (« trois acheteurs » au
  lieu de deux) et fausses absences (« Aucun résultat n'est disponible » alors
  que le résultat contient des lignes).
