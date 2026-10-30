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

# Story 4.1 : dix questions synthétiques

Mesures uniquement, sans verdict. Commande :
`python src/spike_llm_capacite.py MODELE --dix-questions` (11 cas : un par question
de référence, construit avec les contrats réels de `marchegraph.graph.contracts`,
plus le cas vide). Données synthétiques, aucune donnée DECP envoyée au modèle.

## Conditions

- Même machine et mêmes options que la phase A. Neo4j, Streamlit (8501) et
  Ollama démarrés, tous sur `127.0.0.1`. Navigateurs fermés.
- Modèles exécutés l'un après l'autre ; les autres modèles sont déchargés avant
  chaque série. Journaux bruts : `data/spike41/*.log` (ignorés par Git ; leurs
  accents sont mal encodés par PowerShell, le contenu est retranscrit ici).

## Mémoire, latence et chiffres

| Modèle | Taille chargée | RAM libre avant / pendant | Durée par cas (min–max) | Durée totale (11 cas) | Jetons/s (min–max) | Chiffres inventés |
|---|---|---|---|---|---|---|
| llama3.1:8b | 5,6 Go | 5,9 / 1,8 Go | 8,4–38,0 s | 201,5 s | 3,7–5,9 | aucun |
| qwen3:8b | 5,9 Go | 7,1 / 0,7 Go | 63,4–110,4 s | 987,7 s | 3,5–4,7 | aucun |
| qwen3:4b-instruct | 3,2 Go | 6,6 / 2,5 Go | 4,6–23,9 s | 146,7 s | 5,5–8,9 | aucun |
| phi4-mini:3.8b | 3,1 Go | 6,0 / 3,3 Go | 5,3–16,2 s | 108,5 s | 7,2–10,1 | aucun |

La durée maximale inclut le chargement initial du modèle (6 à 12 s).
« Chiffres manquants » n'est pas résumé ici : pour Q3 et Q8, le résultat
contient treize valeurs et chaque modèle n'en reprend que quelques-unes.

## Écarts relevés à la lecture (non détectés par le contrôle des chiffres)

Relevés de l'agent, à confirmer par l'utilisateur.

| Modèle | Cas | Écart |
|---|---|---|
| llama3.1:8b | q2, q4, q6 | « Aucun résultat n'est disponible » alors que le JSON contient des lignes. |
| llama3.1:8b | q9 | « Aucun fournisseur n'a plusieurs écritures de son nom » : inverse du résultat. |
| llama3.1:8b | q7 | « Aucune limite n'est indiquée. Aucun résultat n'est disponible » alors qu'une ligne et une limite sont présentes. |
| llama3.1:8b | q10 | « Aucun résultat n'est disponible » puis cite les deux problèmes. |
| qwen3:8b | q3 | Réponse vide : les 400 jetons ont été consommés par le raisonnement. |
| qwen3:4b-instruct | q2 | « Aucun résultat n'est disponible pour les autres » : Titulaire Deux (17) est omis. |
| qwen3:4b-instruct | q9 | « Aucun résultat n'est disponible » alors qu'une ligne est présente. |
| qwen3:4b-instruct | q5 | Aucun des comptes (900, 400, 500) n'est repris. |
| phi4-mini:3.8b | q6 | « travaille avec trois acheteurs » : le résultat en compte deux. Chiffre écrit en lettres, donc non détecté. |
| phi4-mini:3.8b | q10 | Commentaire ajouté jugeant la limite « pas cohérente avec le contexte » ; les comptes 37 et 25 sont omis. |
| phi4-mini:3.8b | q2 | « Titulaire Deux SAS a été vu 17 fois » : mélange des deux variantes du nom. |

Constat sur le contrôle automatique : il ne compare que les nombres écrits en
chiffres. Les nombres en lettres (« deux », « trois », « six ») et les fausses
absences de résultat (« Aucun résultat n'est disponible ») lui échappent.

## Réponses brutes

### llama3.1:8b

- q1 : « Acheteur Alpha a attribué 1234 marchés en 2025. Acheteur Beta a attribué 987 marchés en 2025. Le classement couvre tout le territoire national. »
- q2 : « Aucun résultat n'est disponible. »
- q3 : « Le montant total par famille CPV en 2025 est de 81 234 567,50. Cette information est disponible pour la famille CPV 452. »
- q4 : « Aucun résultat n'est disponible. »
- q5 : « En 2025, les procédures utilisées sont l'appel d'offres ouvert et la procédure adaptée. Le marché est de la nature "Marché" avec 900 occurrences. Aucune autre information n'est disponible. »
- q6 : « Aucun résultat n'est disponible. »
- q7 : « La voirie est concernée dans la région 84 par les travaux de voirie communale. Aucune limite n'est indiquée. Aucun résultat n'est disponible. »
- q8 : « La durée moyenne par famille CPV en 2025 est de 14,5 mois. Cette valeur est basée sur les données disponibles. Il convient de noter que les limites indiquent que les montants et durées multivalués sont exclus des agrégats. »
- q9 : « Aucun fournisseur n'a plusieurs écritures de son nom. La limite indique que les variantes sont regroupées par identifiant, jamais par nom seul. »
- q10 : « Aucun résultat n'est disponible. La limite indiquée est : "Une valeur multiple n'est pas qualifiée d'erreur.". Les données manquantes ou incohérentes sont les issues de code "montant_multivalue" et "region_acheteur_manquante". »
- vide : « Aucun résultat n'est disponible. La liste des marchés modifiés en 2031 est vide. »

### qwen3:8b

- q1 : « Les acheteurs ayant attribué le plus de marchés en 2025 sont Acheteur Alpha avec 1234 marchés et Acheteur Beta avec 987 marchés. Le classement couvre tout le territoire national. Aucun autre acheteur n'a été mentionné dans les résultats. »
- q2 : « Les titulaires qui reviennent le plus chez l'acheteur 00000000000011 en 2025 sont Titulaire Un (42 retours) et Titulaire Deux (17 retours). Le titulaire avec le plus de retours est Titulaire Un »
- q3 : (vide)
- q4 : « En 2025, deux marchés ont été modifiés : le marché avec l'UID « uid-synth-1 » et celui avec l'UID « uid-synth-2 ». Le marché « uid-synth-1 » a été modifié avec les identifiants 1, 2 et 3, tandis que le marché « uid-synth-2 » a été modifié avec l'identifiant 1. Les limites indiquent que deux versions n'ont pas de marché initial dans le snapshot. »
- q5 : « En 2025, la nature de marché est "Marché" avec 900 occurrences. Les procédures utilisées incluent "Appel d'offres ouvert" (400) et "Procédure adaptée" (500). Les données sont séparées en nature et procédure, sans combinaison. »
- q6 : « Le titulaire "Titulaire Trois" travaille avec deux acheteurs en 2025. Le nombre de marchés associés est de 6. Aucun autre résultat n'est disponible. »
- q7 : « La voirie dans la région 84 concerne le marché "Travaux de voirie communale". Aucun autre marché n'est indiqué dans les résultats. Trois marchés sans région d'acheteur unique sont exclus. »
- q8 : « La durée moyenne par famille CPV en 2025 est de 14.5 mois. Les montants et durées multivalués sont exclus des agrégats. Aucun autre résultat n'est disponible. »
- q9 : « Le fournisseur avec le SIRET 00000000000041 a plusieurs écritures de son nom : "Société Exemple" et "SOCIETE EXEMPLE SAS". Les variantes sont regroupées par identifiant, jamais par nom seul. Aucun autre résultat n'est disponible. »
- q10 : « Les données manquantes ou incohérentes incluent 37 enregistrements avec le code d'erreur "montant_multivalue" et 25 enregistrements avec le code "region_acheteur_manquante". La limite indique qu'une valeur multiple n'est pas qualifiée d'erreur. Aucun autre résultat n'est disponible. »
- vide : « Aucun marché n'a été modifié en 2031 selon les données fournies. La liste des lignes est vide, ce qui indique l'absence de résultats. Aucune limite n'a été signalée dans le cadre de cette recherche. »

### qwen3:4b-instruct

- q1 : « L'Acheteur Alpha a attribué le plus de marchés en 2025 avec 1234 marchés. L'Acheteur Beta a attribué 987 marchés. Le classement couvre tout le territoire national. »
- q2 : « Les titulaires qui reviennent le plus chez l'acheteur 00000000000011 en 2025 sont Titulaire Un. Ce titulaire a un nombre de marché de 42. Aucun résultat n'est disponible pour les autres. »
- q3 : « Le montant total par famille CPV en 2025 est de 81234567.50. Ce montant est déclaré, pas un paiement effectué. Les montants et durées multivalués sont exclus des agrégats. »
- q4 : « Les marchés modifiés en 2025 sont celui ayant l'UID "uid-synth-1" et celui ayant l'UID "uid-synth-2". Deux marchés ont été modifiés. 2 versions n'ont pas de marché initial dans le snapshot. »
- q5 : « Les natures de marché utilisées en 2025 sont le marché. Les procédures utilisées sont l'appel d'offres ouvert et la procédure adaptée. Nature et procédure sont résumées séparément, sans paires. »
- q6 : « Le titulaire qui travaille avec plusieurs acheteurs en 2025 est Titulaire Trois. Il collabore avec les acheteurs ayant les identifiants 00000000000011 et 00000000000012. Le nombre de marchés associés est 6. »
- q7 : « Les marchés concernant la voirie dans la région 84 sont les travaux de voirie communale. Il est indiqué que 3 marchés sans région d'acheteur unique sont exclus. Aucun autre marché n'est mentionné. »
- q8 : « La durée moyenne par famille CPV en 2025 est de 14.5 mois. Cette durée est calculée à partir des données disponibles pour les familles avec des durées déclarées. Les durées multivaluées sont exclues des agrégats selon les limites indiquées. »
- q9 : « Aucun résultat n'est disponible. »
- q10 : « Les données manquantes ou incohérentes concernent les montants multiples et l'absence de région acheteur. Une valeur multiple n'est pas qualifiée d'erreur. Les enregistrements affectés sont respectivement 37 et 25. »
- vide : « Aucun résultat n'est disponible. »

### phi4-mini:3.8b

- q1 : « Acheteur Alpha a attribué 1234 marchés en 2025. Acheteur Beta a attribué 987 marchés en 2025. Le classement couvre tout le territoire national. »
- q2 : « Le titulaire qui revient le plus chez l'acheteur 00000000000011 en 2025 est Titulaire Un. Il a été vu 42 fois. Il n'y a pas de limite indiquée. Titulaire Deux SAS a été vu 17 fois. »
- q3 : « Le montant total par famille CPV en 2025 est de 81 234 567,50. Les montants sont des montants déclarés, pas des paiements. Les montants et durées multivalués sont exclus des agrégats. »
- q4 : « En 2025, deux marchés ont été modifiés. Les marchés modifiés sont identifiés par les UIDs "uid-synth-1" et "uid-synth-2". Il y a deux versions n'ayant pas de marché initial dans le snapshot. »
- q5 : « En 2025, le marché compte 900 entités. Il existe 400 appels d'offres ouverts et 500 procédures adaptées. La nature et la procédure sont résumées séparément, sans paires. »
- q6 : « Titulaire Trois travaille avec trois acheteurs. En 2025, Titulaire Trois est associé à six marchés. Il n'y a pas de limite indiquée. »
- q7 : « Dans la région 84, le marché concerné par la voirie est le Travaux de voirie communale. Il y a 3 marchés sans région d'acheteur unique. »
- q8 : « La durée moyenne par famille CPV en 2025 est de 14,5 mois. Les durées multivaluées sont excluses des agrégats. Les montants sont des montants déclarés, pas des paiements. »
- q9 : « Deux écritures du nom du fournisseur sont regroupées par identifiant. Les variantes sont regroupées par identifiant, jamais par nom seul. Le fournisseur est identifié par le SIRET 00000000000041. »
- q10 : « Les données manquantes ou incohérentes sont le fait que "Une valeur multiple n'est pas qualifiée d'erreur." Les deux lignes fournissent des informations sur des problèmes différents, mais le texte de la limite n'est pas cohérent avec le contexte des problèmes. »
- vide : « Aucun résultat n'est disponible. La liste des lignes est vide. Il n'y a pas de marchés modifiés en 2031. »

## Décision de l'utilisateur (story 4.1)

2026-10-29 : l'utilisateur retient `phi4-mini:3.8b`, jugé le meilleur compromis
entre durée (108,5 s pour 11 cas, 5 à 16 s par cas) et mémoire (3,1 Go chargés,
3,3 Go de RAM libre pendant le test). Ses écarts relevés (q6 « trois acheteurs »,
commentaire ajouté en q10, mélange de variantes en q2) restent à traiter par
le contrôle de la story 4.3.
