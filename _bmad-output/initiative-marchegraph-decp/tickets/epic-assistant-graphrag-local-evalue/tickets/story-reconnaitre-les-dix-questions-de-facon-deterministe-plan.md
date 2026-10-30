---
title: "Reconnaître les dix questions de façon déterministe ou s'abstenir"
ticket: 2
status: done
---

# Reconnaissance déterministe des questions

## Portée livrée

- `src/marchegraph/queries/interpretation.py` : module pur (ni Neo4j ni
  Streamlit, AD-5). `interpret(question)` renvoie `Interpretation`
  (identifiant de question, libellé, paramètres) ou `None` pour s'abstenir.
- `src/marchegraph/queries/dispatch.py` : associe chaque identifiant à la
  requête préparée de `graph/queries.py` et l'exécute.
- `src/marchegraph/demo_chat.py` délègue reconnaissance et exécution à ces
  modules ; la liste d'exemples couvre les dix questions.
- Les dix questions sont couvertes, dont Q7 (thème et région de l'acheteur,
  nouvelle) et la distinction Q3 (montant), Q8 (durée) et Q3+Q8.
- Paramètres extraits : année (2024 ou 2025, 2025 par défaut), identifiant
  d'acheteur à 14 chiffres, région (code INSEE ou nom, dont « région 84 »),
  thème (texte d'origine, accents conservés).
- Abstention : aucune règle reconnue ; année hors 2024–2025 ou plusieurs
  années ; région citée hors Q7 ; plusieurs régions ou code inconnu ; Q7 sans
  thème ; Q2 sans identifiant d'acheteur ; année citée pour Q9 ou Q10, qui ne
  sont pas filtrées par année ; « famille CPV » sans montant ni durée.

## Choix retenu

- Emplacement : `src/marchegraph/queries/`, conforme à la carte de
  l'architecture ; les requêtes Cypher restent dans `graph/queries.py`.
  Accepté avec la story le 2026-10-29.

## Vérification

- `tests/test_question_interpretation.py` : 16 formulations reconnues avec
  leurs paramètres, 14 abstentions, couverture des dix questions et
  compatibilité des paramètres avec la signature de chaque requête ; sans Neo4j.
- Suite complète : 46 tests, intégration ignorée sans `NEO4J_PASSWORD`.
- `compileall` et `git diff --check` passent.
