# Évaluation de l'epic 4 : assistant GraphRAG face aux baselines (story 4.6)

Même jeu de fixtures et même référence que `docs/evaluation-baselines.md`.
Exécution locale le 2026-10-29 : `python -m marchegraph.evaluation.run
--assistant` ; détail brut dans `data/evaluation/evaluation-assistant.json`
(ignoré par Git). Modèle : `phi4-mini:3.8b` (3,1 Go en mémoire), en loopback.

Seuil fixé par l'utilisateur avant cette mesure : au moins 9 / 10 questions de
référence correctes, 10 / 10 abstentions correctes, aucune hallucination dans
les textes affichés.

## Questions de référence

« Résultat » = faits essentiels du résultat structuré comparés à la référence.
« Texte » = ce que l'utilisateur voit.

| Q | Résultat | Texte affiché | Note automatique du texte | Durée |
|---|---|---|---|---|
| 1 | correct | « Les deux acheteurs ont attribué un marché chacun en 2025. Le classement est limité aux 10 premiers acheteurs. … » | incomplet (« un » en lettres) | 13,9 s |
| 2 | correct | « Les 10 premiers titulaires sont limités. … Alpha SAS, Titulaire Alpha, est le premier. Le nombre de lignes fournies est de 1. … » | correct | 10,7 s |
| 3 | correct | aucun : abstention de formulation (« chiffre absent du résultat : 400.00 ») | — | 30,3 s |
| 4 | correct | « Un marché a été modifié après attribution en 2025. Il y a eu 1 modification. Il y a 1 version(s) n'ont pas de marché initial dans le snapshot. » | incomplet | 18,7 s |
| 5 | correct | « … incluent l'appel d'offres et la procédure adaptée. … Fournitures, Services et Travaux. … » | incomplet (comptes omis) | 22,1 s |
| 6 | correct | « En 2025, le Titulaire Alpha SAS travaille avec deux acheteurs différents. … » | incomplet | 7,4 s |
| 7 | correct | « Le marché concerné est le "Travaux de voirie". … Il n'y a qu'un seul marché attribué en Île-de-France en 2025. » | correct | 11,0 s |
| 8 | correct | « La durée moyenne des marchés par famille CPV en 2025 est de 6 mois. Il y a 2 lignes fournies. … » | incomplet (12 mois omis) | 19,3 s |
| 9 | correct | « Les variantes Alpha SAS et Titulaire Alpha sont regroupées sous l'identité titulaire déjà résolue … » | incomplet | 20,2 s |
| 10 | correct | « … Il y a un total de 14 lignes, mais seulement 10 lignes ont été fournies. Les valeurs manquantes reflètent les indicateurs source, et les valeurs multiples indiquent une hétérogénéité conservée, pas une erreur … » | incomplet | 42,8 s |

Les tableaux, limites et preuves restent affichés sous chaque texte (story 4.4).

## Questions à abstention attendue

Les dix questions sont reconnues comme non prises en charge : 10 / 10
abstentions correctes, sans appel au graphe ni au modèle (moins de 0,01 s).

## Comparaison

| Mesure | Assistant | Baseline SQL | Modèle sans graphe |
|---|---|---|---|
| Références correctes (résultat structuré) | 10 / 10 | 8 / 10 | 0 / 10 |
| Abstentions correctes | 10 / 10 | 10 / 10 | 6 / 10 |
| Hallucinations chiffrées affichées | 0 (une bloquée en Q3) | 0 | 1 |
| Entités ou faits inventés affichés | à juger (Q6, Q8) | 0 | 5 |
| Preuves issues du graphe | oui | non | non |
| Durée par question | 7,4 à 42,8 s | < 0,2 s | 3,4 à 12,5 s |

Le résultat structuré de l'assistant provient des requêtes de l'epic 3, qui
servent aussi de référence : son 10 / 10 mesure la reconnaissance des questions
et l'acheminement vers la bonne requête, pas une réponse indépendante.

## Points à juger par l'utilisateur

Ces deux textes ont passé le contrôle automatique (aucun chiffre inventé) :

- Q6 : « le Titulaire Alpha SAS » fusionne les deux variantes de nom
  (« Titulaire Alpha » et « Alpha SAS ») en un nom qui n'existe pas dans le
  résultat.
- Q8 : « La durée moyenne … par famille CPV … est de 6 mois » présente la valeur
  d'une seule famille (300) comme une valeur générale ; la famille 450
  (12 mois) est omise.

Selon qu'ils sont jugés ou non comme hallucinations, le critère « aucune
hallucination affichée » est atteint ou non. Les deux autres critères du seuil
(9 / 10 et 10 / 10) sont atteints.

## Coûts locaux

- Mémoire : 3,1 Go pour le modèle, en plus de Neo4j.
- Latence de l'assistant : 7,4 à 42,8 s par question sur processeur seul ; la
  plus longue (Q10) correspond au résultat le plus volumineux.
- Aucun appel distant ; aucune donnée DECP dans ce jeu.

## Décision de l'utilisateur

2026-10-29 : application stricte de la définition de l'epic (« tout fait,
chiffre ou entité du texte absent du résultat structuré reçu »). Q6 (nom
« Titulaire Alpha SAS » absent du résultat) et Q8 (durée de la seule famille
300 présentée comme valeur générale) sont des hallucinations affichées.

| Critère du seuil | Mesure | Atteint |
|---|---|---|
| Références correctes ≥ 9 / 10 | 10 / 10 | oui |
| Abstentions correctes 10 / 10 | 10 / 10 | oui |
| Aucune hallucination affichée | 2 (Q6, Q8) | non |

Le seuil n'est pas atteint sur ce run. Pistes : contrôle des noms propres
(chaque nom du texte doit figurer tel quel dans le résultat) et, pour les
résultats à plusieurs lignes, obligation de rattacher chaque valeur à sa
ligne.
