---
tracker_id: ""
id: 5
type: epic
title: "Couverture élargie des questions, factuelle et traçable"
parent: initiative-marchegraph-decp
covers: ["R4", "R6"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md", "docs/evaluation-assistant.md"]
companions: ["_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md"]
after: ["epic-assistant-graphrag-local-evalue"]
refined: true
risk: high
status: in-progress
---

# Couverture élargie des questions, factuelle et traçable

## Description

Passer de dix questions fixes à des questions composées à partir des
dimensions réelles des données (mesure × regroupement × filtres), en
reconnaissant les entités citées par leur nom, sans perdre la garantie
centrale du projet : chaque réponse provient d'une requête Neo4j préparée,
avec ses preuves, ou l'assistant s'abstient.

## Outcome

Un analyste pose des questions variées et représentatives des données
(acheteur, titulaire, région, CPV, procédure, montant, durée, période,
thème) ; il obtient un résultat factuel tiré du graphe avec ses preuves, ou
une abstention explicite, et peut choisir lui-même l'entité visée en cas
d'ambiguïté.

## Principe directeur

La recherche textuelle (BM25 plein texte Neo4j) et, si elle est approuvée, la
recherche sémantique servent uniquement à proposer des **points d'entrée**
dans le graphe : identifiants de nœuds candidats, avec leur score. Elles ne
produisent jamais la réponse. La réponse vient toujours d'une requête Cypher
préparée, exécutée sur des identifiants exacts, avec preuves et limites.
En dessous d'un seuil de confiance, ou si plusieurs candidats sont proches,
l'assistant demande à l'utilisateur de choisir ou s'abstient.

## Done when

- Les questions composées du catalogue approuvé renvoient un résultat
  structuré avec preuves, ou une abstention ; les dix questions de l'epic 4
  restent correctes.
- Les entités citées par leur nom sont résolues vers des identifiants exacts,
  avec choix explicite de l'utilisateur en cas d'ambiguïté ; aucun score de
  recherche n'est présenté comme un fait.
- Les exemples affichés sont calculés à partir du contenu du graphe.
- L'évaluation, générée à partir du catalogue sur fixtures, rapporte la
  couverture, la précision de reconnaissance, les abstentions et les
  hallucinations, face à un seuil fixé après mesure.
- Tout reste local ; aucun service distant.

## Boundaries

- Owns: catalogue de questions composables, constructeur de requêtes sur
  liste fermée, résolution d'entités par recherche plein texte, suggestions
  issues des données, évaluation de couverture.
- Does not own: modèle de domaine et chargement du graphe (epic 3), formulation
  contrôlée (epic 4, réutilisée).
- Must not change: le modèle ne génère ni n'exécute de Cypher ; les références
  de preuve viennent de la requête (AD-3).
- Must not change: aucune réponse n'est tirée d'un score de similarité ou de
  pertinence ; la recherche ne fournit que des candidats.
- Must not change: tout reste local (AD-4) ; aucune donnée DECP n'est envoyée
  à un service externe.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R4, R6; Constraints C7, C9.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-3–AD-5.
- evaluation — `docs/evaluation-assistant.md` (epic 4 : seuil non atteint sur les hallucinations affichées).

## Notes

- Waits on epic 4 because: l'epic réutilise la reconnaissance, la
  formulation contrôlée, l'interface et le harnais d'évaluation.
- Decision: 2026-10-29 — L'utilisateur demande d'élargir les questions pour
  qu'elles soient représentatives des données, en gardant Neo4j comme source
  factuelle et traçable ; la recherche sémantique et BM25 sont jugées
  risquées si elles produisent la réponse.
- Open question: Approuver le découpage en stories (`tickets/tickets.toml`).
  Résolu le 2026-10-30 : découpage approuvé tel quel.
- Decision: 2026-10-30 — Story 5 engagée : la décision 2 de l'epic 4 est
  modifiée (compréhension hybride, règles d'abord) et AD-3 est complétée
  (amendement du 2026-10-30).
- Decision: 2026-10-30 — Story 6 engagée avec le modèle d'embedding local
  `nomic-embed-text` via Ollama ; téléchargement à confirmer au démarrage de
  la story.
- Decision: 2026-10-30 — Libellés CPV : nomenclature officielle de l'UE
  (règlement (CE) n° 213/2008), chargée localement.
- Open question: Story 5 (compréhension par le modèle en structure fermée)
  exige de modifier la décision 2 de l'epic 4 et de compléter AD-3. Résolu le
  2026-10-30.
- Open question: Story 6 (recherche sémantique) : engager ou non, choix du
  modèle d'embedding local, coût de calcul sur processeur. Résolu le
  2026-10-30.
- Open question: Source des libellés CPV (nomenclature officielle) pour la
  recherche par libellé. Résolu le 2026-10-30.
- Open question: Nombre et contenu exact du catalogue (story 1) : à approuver
  par l'utilisateur avant implémentation.
