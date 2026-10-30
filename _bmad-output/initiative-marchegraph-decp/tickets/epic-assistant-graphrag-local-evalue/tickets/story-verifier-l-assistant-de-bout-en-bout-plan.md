---
title: "Vérifier l'assistant de bout en bout"
ticket: 7
status: done
---

# Vérification de bout en bout de l'epic 4

## Vérifications

- Suite complète : 69 tests passés, dont l'intégration Neo4j locale de
  l'epic 3 ; `compileall` et `git diff --check` passent.
- Exécution locale sur fixtures : `python -m marchegraph.evaluation.run`
  (story 4.5) puis `--assistant` (story 4.6) ; dix questions de référence
  reconnues et acheminées, dix abstentions correctes, fixtures chargées sous un
  `source_id` dédié puis supprimées.
- Contrôle sur le graphe local (story 4.4) : dix questions et une abstention.
- Aucun appel distant : Neo4j, Ollama et Streamlit en loopback ; le modèle ne
  reçoit jamais de références de preuve. Aucune donnée DECP ni sortie dérivée
  dans Git (`data/` ignoré).

## Dettes et limites consignées

- Seuil de la story 4.6 non atteint sur le critère « aucune hallucination
  affichée » (Q6, Q8) ; pistes : contrôle des noms propres et rattachement des
  valeurs aux lignes.
- Latence sur processeur seul : 7 à 43 s par question formulée.
- Q9 ne renvoie aucune ligne sur le graphe du snapshot retéléchargé ; cause
  non examinée.
- Les chargeurs et requêtes lisent `DATASET_ID` comme constante de module ;
  l'évaluation la remplace temporairement, comme le test de l'epic 3.
- Les tests de `test_prepare` et `test_entity_resolution` exigent
  `PYTHONUTF8=1` sous Windows (lecture sans encodage explicite).
