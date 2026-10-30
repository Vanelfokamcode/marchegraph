# Évaluation de l'epic 4 : baselines (story 4.5)

Données : jeu de fixtures de l'epic 3 (`src/marchegraph/evaluation/dataset.py`),
aucune donnée DECP. Référence : requêtes préparées de l'epic 3 sur ces fixtures
chargées dans Neo4j. Exécution locale le 2026-10-29 :
`python -m marchegraph.evaluation.run` ; détail brut dans
`data/evaluation/evaluation-baselines.json` (ignoré par Git).

- Baseline SQL : DuckDB directement sur le Parquet, même reconnaissance des
  questions, sans les règles de l'epic 3.
- Baseline sans graphe : `phi4-mini:3.8b` (3,1 Go en mémoire), ne reçoit que la
  question. Même modèle que l'assistant.

Mesures uniquement ; le seuil est fixé par l'utilisateur après lecture.

## Questions de référence (réponse attendue)

| Q | Baseline SQL | Modèle sans graphe (note automatique) | Correction proposée | Durée du modèle |
|---|---|---|---|---|
| 1 | correct | abstention à tort | — | 9,6 s |
| 2 | correct | abstention à tort | + entité inventée (« OFMIF ») | 6,9 s |
| 3 | correct | abstention à tort | — | 3,6 s |
| 4 | différent : 2 marchés modifiés au lieu de 1 (la version sans marché initial est comptée) | abstention à tort | — | 3,0 s |
| 5 | correct | incomplet | hallucination : catégories et procédures génériques absentes du résultat (« appels d'enchères », « marchés d'intérêt privé ») | 9,0 s |
| 6 | correct | abstention à tort | — | 7,0 s |
| 7 | correct | abstention à tort | + entité inventée (« DRTI ») | 6,1 s |
| 8 | correct | abstention à tort | — | 3,9 s |
| 9 | correct | abstention à tort | + entité inventée (« COVERS », office fédéral) | 10,5 s |
| 10 | différent : 4 indicateurs de colonnes vides au lieu des 14 signaux du graphe | abstention à tort | — | 9,2 s |

## Questions à abstention attendue

| Question | Baseline SQL | Modèle sans graphe (note automatique) | Correction proposée |
|---|---|---|---|
| Météo à Paris | abstention correcte | abstention correcte | — |
| Paiements de la mairie de Lyon | abstention correcte | abstention correcte | — |
| Acheteurs en 2019 | abstention correcte | réponse au lieu d'abstention | — |
| Acheteurs entre 2024 et 2025 | abstention correcte | abstention correcte | + entité inventée (« CDEC ») |
| Montant en 2026 | abstention correcte | abstention correcte | — |
| Titulaires d'un acheteur non précisé | abstention correcte | abstention correcte | — |
| Voirie sans région | abstention correcte | réponse au lieu d'abstention | — |
| Voirie en Bretagne et Normandie | abstention correcte | réponse au lieu d'abstention | — |
| Entreprise « la plus corrompue » | abstention correcte | abstention correcte | — |
| Habitants de la Bretagne | abstention correcte | réponse au lieu d'abstention (« 3 millions ») | — |

La baseline SQL partage la reconnaissance déterministe de l'assistant : ses
dix abstentions correctes viennent de cette reconnaissance, pas du SQL.

## Synthèse (notes automatiques, avant validation)

| Mesure | Baseline SQL | Modèle sans graphe |
|---|---|---|
| Références correctes | 8 / 10 | 0 / 10 |
| Abstentions correctes | 10 / 10 | 6 / 10 |
| Hallucinations chiffrées | 0 | 1 (« 3 millions ») |
| Entités ou faits inventés (lecture, à valider) | 0 | 5 (OFMIF, DRTI, COVERS, CDEC, Q5) |
| Durée par question | 0,04 à 0,10 s | 3,0 à 10,8 s |
| Preuves issues du graphe | aucune | aucune |

## Validation et seuil

2026-10-29, décision de l'utilisateur :

- Corrections de notation acceptées. Après correction, le modèle sans graphe
  compte 0 / 10 références correctes, 6 / 10 abstentions correctes et
  6 réponses contenant une hallucination (Q2, Q5, Q7, Q9, « entre 2024 et
  2025 », « habitants de la Bretagne »). La baseline SQL reste à 8 / 10 et
  10 / 10, sans hallucination.
- Seuil de réussite de l'assistant (story 4.6), sur le même jeu :
  au moins 9 / 10 questions de référence correctes (résultat structuré
  identique à la référence), 10 / 10 abstentions correctes et aucune
  hallucination dans les textes affichés.
