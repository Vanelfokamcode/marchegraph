# Exploration : capacité d'un modèle local à reformuler un résultat structuré (phase A, epic 4)

Exploration hors tickets. Mesures uniquement, sans verdict : le choix du modèle appartient à l'utilisateur.
Données de test **synthétiques** (`src/spike_llm_capacite.py`, trois cas). Aucune donnée DECP envoyée au modèle.

## Conditions

- Date : 2026-10-29. Machine : Windows, 15,6 Go de RAM visibles, sans GPU NVIDIA.
- Ollama 0.40.13, écoute sur `127.0.0.1:11434` uniquement. Exécution 100 % CPU, contexte 4096.
- Options : `temperature 0`, `seed 42`, `num_predict 400`.
- Neo4j 5.26.32 démarré (graphe complet chargé, processus `java` ≈ 2,2 Go).
- Modèles testés : `llama3.1:8b` et `qwen3:8b`, choisis par l'utilisateur. **Aucun modèle de 4 milliards de paramètres testé** (non retenu à ce stade, alors que le fichier de phase A en recommandait un).
- RAM libre : `FreePhysicalMemory` (indicateur du fichier de phase A). « Pendant » = relevé juste après le dernier cas, modèle encore chargé.

## Mémoire

| Modèle | Taille chargée (`ollama ps`) | RAM libre avant | RAM libre pendant | Remarque |
|---|---|---|---|---|
| llama3.1:8b (run 1) | 5,6 Go | 2,2 Go | 1,1 Go | Chrome, Edge et VS Code ouverts (≈ 4,7 Go cumulés), swap probable |
| llama3.1:8b (run 2) | 5,6 Go | 7,6 Go | 1,9 Go | Navigateurs fermés |
| qwen3:8b | 5,9 Go | 6,5 Go | 0,5 Go | Navigateurs fermés |

## Latence et débit par cas

Durée totale = appel HTTP complet, chargement inclus.

| Modèle | Cas | Durée totale | Chargement | Jetons/s |
|---|---|---|---|---|
| llama3.1:8b (run 1) | classement | 44,1 s | 14,6 s | 3,7 |
| llama3.1:8b (run 1) | limites | 21,8 s | 0,1 s | 4,6 |
| llama3.1:8b (run 1) | vide | 7,7 s | 0,0 s | 5,2 |
| llama3.1:8b (run 2) | classement | 37,4 s | 10,1 s | 3,2 |
| llama3.1:8b (run 2) | limites | 28,1 s | 0,3 s | 3,4 |
| llama3.1:8b (run 2) | vide | 8,7 s | 0,0 s | 4,6 |
| qwen3:8b | classement | 103,4 s | 11,8 s | 4,0 |
| qwen3:8b | limites | 97,0 s | 0,1 s | 4,5 |
| qwen3:8b | vide | 61,4 s | 0,0 s | 4,4 |

`qwen3:8b` est un modèle à raisonnement : les jetons de `<think>` sont générés puis retirés de la réponse, d'où une durée plus longue à débit comparable. Aucune réponse vide observée.

## Contrôle automatique des chiffres

| Modèle | Cas | Chiffres manquants | Chiffres inventés |
|---|---|---|---|
| llama3.1:8b (runs 1 et 2) | classement | aucun | aucun |
| llama3.1:8b (runs 1 et 2) | limites | 452, 5120 | aucun |
| llama3.1:8b (runs 1 et 2) | vide | aucun | aucun |
| qwen3:8b | classement | aucun | aucun |
| qwen3:8b | limites | 452, 5120 | aucun |
| qwen3:8b | vide | aucun | aucun |

Les deux modèles omettent la famille CPV (« 452 ») et le nombre de marchés (5120) dans le cas « limites ». Le contrôle ne détecte que les nombres : un fait non numérique ajouté n'est pas repéré automatiquement.

## Réponses brutes

Les deux runs de `llama3.1:8b` donnent des réponses identiques.

### llama3.1:8b

- **classement** : « Acheteur Alpha a attribué 1234 marchés en 2025. Acheteur Beta a attribué 987 marchés en 2025. Acheteur Gamma a attribué 456 marchés en 2025. »
- **limites** : « Le montant total par famille CPV est de 81 234 567,50. La limite indiquée est que 37 marchés ont plusieurs montants et sont exclus de l'agrégat de montant. Aucun résultat n'est disponible pour les autres familles CPV. »
- **vide** : « Aucun résultat n'est disponible. La liste des marchés modifiés en 2031 est vide. »

### qwen3:8b

- **classement** : « Acheteur Alpha a attribué le plus de marchés en 2025 avec 1234 marchés. Acheteur Beta a attribué 987 marchés. Acheteur Gamma a attribué 456 marchés. »
- **limites** : « Le montant total par famille CPV est de 81234567,50. Cet agrégat exclut 37 marchés ayant plusieurs montants. Une seule famille CPV est disponible dans les résultats. »
- **vide** : « Aucun marché n'a été modifié en 2031 selon les données fournies. La liste des lignes est vide, ce qui indique l'absence de résultats. Aucune limite n'a été signalée dans le cadre de cette recherche. »

## Points à juger par l'utilisateur

À remplir après relecture des réponses ci-dessus.

| Critère | llama3.1:8b | qwen3:8b |
|---|---|---|
| Français correct | | |
| Aucun fait ajouté (y compris non numérique) | | |
| Limite signalée (cas « limites ») | | |
| Comportement sur le cas vide | | |
| Latence acceptable pour la démo | | |
| Marge mémoire acceptable avec Neo4j | | |

Éléments à examiner en particulier :
- llama3.1:8b, cas « limites » : la phrase « Aucun résultat n'est disponible pour les autres familles CPV » n'est pas dans le JSON reçu.
- qwen3:8b, cas « limites » : « Une seule famille CPV est disponible dans les résultats » est une déduction tirée du nombre de lignes.
- qwen3:8b, cas « vide » : « Aucun marché n'a été modifié en 2031 » affirme un fait sur le monde, alors que le JSON dit seulement que la liste est vide.
- Les deux modèles, cas « limites » : la famille CPV « 452 » et le nombre de marchés (5120) sont omis.
- Mémoire : avec `qwen3:8b` chargé, il restait 0,5 Go de RAM libre (Neo4j démarré ; présence de Streamlit non vérifiée).
