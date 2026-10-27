---
tracker_id: ""
id: 2
type: epic
title: "Résolution des identités titulaires"
parent: initiative-marchegraph-decp
covers: ["R5"]
sources: ["_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md", "docs/profilage-initial.md"]
companions: ["_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md"]
after: ["epic-fondation-decp-reproductible"]
refined: true
risk: high
---

# Résolution des identités titulaires

## Description

Produire localement un résultat dérivé qui rapproche les titulaires du jeu
analytique préparé par identifiant typé, puis mesurer la qualité de cette règle
sur un échantillon vérifié manuellement.

## Outcome

Les titulaires ayant le même type et la même valeur d'identifiant normalisés
sont rapprochés de façon reproductible ; les identifiants manquants et les
limites de cette règle sont documentés, et sa qualité est mesurée séparément
pour 2025 et 2024.

## Requirements

- R1 (parent R5) : Chaque ligne d'attribution initiale ayant un type
  d'identifiant et une valeur renseignés peut être rattachée de façon
  reproductible à une identité titulaire canonique définie par le couple
  normalisé de ces deux champs. Le contrôle vérifie que les mêmes couples
  produisent la même identité, que des types ou valeurs différents ne sont pas
  fusionnés et que les zéros initiaux sont conservés.
- R2 (parent R5) : La qualité de cette règle est mesurée sur un échantillon
  vérifié manuellement. Le rapport indique la taille et la composition de
  l'échantillon, les résultats corrects et incorrects, les métriques et leurs
  dénominateurs, ainsi que les limites de l'évaluation ; aucun seuil de réussite
  n'est fixé avant la mesure de la baseline.
- R3 (parent R5) : Le rapport rend visibles, par année et type d'identifiant,
  les lignes rapprochées et non rapprochées, et distingue explicitement les
  identifiants manquants afin que la différence de complétude entre 2024 et
  2025 soit interprétable.

## Done when

- Une commande locale produit un résultat dérivé reproductible qui rattache
  les lignes par couple type-valeur normalisé sans modifier le Parquet préparé.
- Les lignes sans type ou valeur d'identifiant restent non rapprochées et sont
  rapportées séparément ; aucune fusion automatique ne se fait par le nom seul.
- Un échantillon est vérifié manuellement ; le rapport publie les effectifs,
  métriques, dénominateurs et limites de l'évaluation sans seuil préétabli.
- Le rapport distingue 2025, périmètre principal, de 2024, comparaison
  secondaire, et expose l'écart de complétude des identifiants.
- Les tests vérifient la normalisation, la préservation des zéros initiaux,
  l'absence de fusion entre types différents, le traitement des valeurs
  manquantes et l'absence de modification du jeu préparé.
- La vérification intégrée s'exécute localement ; aucune donnée DECP ligne à
  ligne ni aucun résultat dérivé n'est publié.

## Boundaries

- Owns: normalisation et rapprochement des identités titulaires, échantillon
  vérifié et rapport de mesure.
- Does not own: rapprochement automatique par nom seul, regroupement des SIRET
  sous un SIREN, représentation ontologique des titulaires ni décisions sur
  les concepts et relations du graphe ; ces sujets restent hors de cet epic.
- Touch point: le schéma et les enregistrements titulaires préparés par l'epic
  1.
- Must not change: ne pas traiter une identité manquante comme une preuve
  d'absence de titulaire.
- Must not change: ne pas convertir les identifiants en nombres ni perdre les
  zéros initiaux.
- Must not change: distinguer le type d'identifiant de sa valeur ; ne pas
  fusionner des types différents ni rapprocher automatiquement sur le nom.
- Must not change: 2025 reste le périmètre principal et 2024 la comparaison
  secondaire ; la différence de complétude doit rester visible.
- Must not change: la logique de rapprochement dépend des contrats de données,
  pas de DuckDB ni d'un autre adaptateur de persistance ; seul l'adaptateur
  d'entrée/sortie importe le moteur de stockage.
- Must not change: aucune donnée DECP ligne à ligne ni aucun résultat dérivé
  n'est publié.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/initiative-marchegraph-decp.md`, Requirements R5; Constraints C2, C3, C7.
- source — `docs/profilage-initial.md`, Identifiants des titulaires en 2025; Valeurs manquantes.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-1, AD-4–AD-5; identifiers remain strings and retain leading zeros.

## Notes

- Waits on epic 1 because: le rapprochement doit consommer le jeu préparé et
  son contrat de données.
- Decision: 2026-10-27 — Utiliser le couple type-valeur d'identifiant
  normalisé comme clé de rapprochement ; ne pas fusionner automatiquement des
  titulaires sur le nom seul. Les variantes de nom sous une même clé peuvent
  être rapportées sans créer de rapprochement supplémentaire.
- Decision: 2026-10-27 — Normaliser le type en supprimant ses espaces externes
  et en le passant en majuscules ; ne retirer que les espaces externes de la
  valeur et préserver sa casse, sa ponctuation, ses espaces internes et ses
  zéros initiaux.
- Open question: Le plan de constitution de l'échantillon et le choix précis
  des métriques, ainsi que la personne qui réalisera la vérification manuelle,
  seront précisés au découpage en stories ; le seuil de réussite restera ouvert
  jusqu'à la mesure de la baseline.
- Decision: 2026-10-27 — La story qui demande l'adjudication manuelle de
  l'échantillon sera marquée `hitl = true` lors du découpage.
- Risk rationale: une fusion erronée ou une identité scindée biaiserait les
  comptes de titulaires et les analyses de réseau en aval ; la règle
  conservatrice et l'échantillon vérifié limitent ce risque.
