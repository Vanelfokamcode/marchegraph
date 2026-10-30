---
title: "Retenir le modèle local après le test de capacité"
ticket: 1
status: done
---

# Test de capacité du modèle local

## Point de départ

- Phase A (`docs/spike-modele-local-resultats.md`) : `llama3.1:8b` et
  `qwen3:8b` sur trois cas synthétiques, Neo4j démarré, Ollama 0.40.13 en
  loopback, CPU seul. Mesures sans verdict.

## Portée

- `src/spike_llm_capacite.py --dix-questions` : un cas synthétique par question
  de référence, construit avec les contrats réels de
  `marchegraph.graph.contracts` (Q3 et Q8 partagent `CpvFamilyAggregate`),
  plus le cas vide. Aucune donnée DECP n'est envoyée au modèle.
- Mesures par modèle : taille chargée, RAM libre avant et pendant, durée et
  jetons/s par cas, chiffres manquants et inventés, réponses brutes ; Neo4j et
  Streamlit démarrés.
- Décision de l'utilisateur après lecture : modèle retenu, ou réponses
  uniquement déterministes et révision de R4/R6.

## Vérification

- Les dix cas se construisent et se sérialisent sans appel au modèle.
- Quatre modèles mesurés avec Neo4j et Streamlit démarrés (`llama3.1:8b`,
  `qwen3:8b`, `qwen3:4b-instruct`, `phi4-mini:3.8b`) ; rapport dans
  `docs/spike-modele-local-resultats.md`, section « Story 4.1 ».
- Décision de l'utilisateur (2026-10-29) : `phi4-mini:3.8b` retenu pour la
  durée et la mémoire.
