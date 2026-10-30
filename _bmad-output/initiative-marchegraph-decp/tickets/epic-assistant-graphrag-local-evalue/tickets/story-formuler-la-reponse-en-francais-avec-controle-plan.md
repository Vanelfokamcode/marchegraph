---
title: "Formuler la réponse en français avec contrôle des chiffres"
ticket: 3
status: done
---

# Formulation contrôlée par le modèle local

## Portée livrée

- `src/marchegraph/queries/local_model.py` : `OllamaClient(model, base_url)`,
  bibliothèque standard uniquement ; refuse toute URL qui n'est pas `http` sur
  `localhost`, `127.0.0.1` ou `::1`. Options : `temperature 0`, `seed 42`,
  `num_predict 400` ; les blocs `<think>` sont retirés.
- `src/marchegraph/queries/formulation.py` :
  - `payload(response)` : valeurs et limites du résultat, sans les références
    de preuve ;
  - `formulate(question, label, response, generate)` : gabarit déterministe
    sans modèle ou sans ligne ; sinon texte du modèle contrôlé ;
  - `check(...)` rejette un texte vide, un chiffre absent du résultat, un
    nombre en lettres (deux à seize, dizaines, cent, mille) absent du
    résultat, ou une fausse absence (« aucun résultat », « aucun
    fournisseur… », « liste … vide ») alors que des lignes existent. Sont
    admis les nombres du résultat, de la question et les longueurs de listes.
- Décision de l'utilisateur : en cas d'échec du contrôle ou de modèle
  indisponible, abstention de formulation (`source = "abstention"`) ; le
  tableau, les limites et les preuves restent affichés (story 4.4).
- Les références de preuve ne passent jamais par le modèle.

## Vérification

- `tests/test_formulation.py` (9 tests, faux client de modèle, sans réseau) :
  texte fidèle accepté, chiffre inventé, nombre en lettres faux, fausses
  absences, réponse vide et modèle en échec mènent à l'abstention ; gabarit
  sans modèle ou sans ligne ; aucune preuve dans le prompt ; URL hors
  loopback refusée.
- Essai réel local avec `phi4-mini:3.8b` sur deux cas synthétiques : texte
  fidèle accepté pour le classement ; « trois acheteurs » (deux attendus)
  détecté et abstention de formulation pour les titulaires multi-acheteurs.
- Suite complète : 55 tests, intégration ignorée sans `NEO4J_PASSWORD` ;
  `compileall` et `git diff --check` passent.
