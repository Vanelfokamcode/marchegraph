---
id: 2
type: story
title: "Compléter le rapport de qualité DECP"
parent: epic-fondation-decp-reproductible
covers: [R1]
after: [1]
hitl: false
risk: medium
refined: true
---

# Compléter le rapport de qualité DECP

## Description

Complète le rapport initial des attributions DECP en y présentant, pour 2024 et 2025, les champs manquants, les anomalies de montant et les délais entre notification et publication. Chaque mesure indique son dénominateur ; les constats restent descriptifs et ne modifient pas le Parquet préparé.

## Requirements

1. **Rendre les valeurs manquantes visibles** (R1)
   **Given** le Parquet préparé par la story 1.1,
   **When** le rapport qualité est généré,
   **Then** il présente, pour chacune des années 2024 et 2025 et parmi les lignes d'attribution initiale (`modification_id = 0`), le nombre et le pourcentage de valeurs nulles pour `acheteur_id`, `titulaire_id`, `montant`, `codeCPV`, `objet`, `lieuExecution_code`, `acheteur_region_code` et `offresRecues`,
   **And** chaque pourcentage utilise comme dénominateur le nombre de lignes d'attribution initiale de l'année ; les taux sont affichés avec deux décimales, et tout taux positif inférieur à 0,01 % est affiché comme `<0,01 %` plutôt que `0,00 %`.
   Pour le snapshot identifié, les dénominateurs sont 325470 en 2024 et 315998 en 2025 ; les nombres manquants par champ sont respectivement (2024 / 2025) : `acheteur_id` 0 / 0, `titulaire_id` 38442 / 4930, `montant` 1864 / 557, `codeCPV` 2 / 6, `objet` 116 / 0, `lieuExecution_code` 245 / 5, `acheteur_region_code` 1687 / 2177, `offresRecues` 48159 / 43116.

2. **Décrire les anomalies de montant** (R1)
   **Given** les lignes d'attribution initiale de chaque année,
   **When** le rapport qualité est généré,
   **Then** il présente le compte et le pourcentage sur le total annuel pour chaque valeur distincte de `montant_anomalie`, y compris les valeurs nulles, sans les classer comme anomalie si la source ne le fait pas.
   Pour le snapshot identifié, les seules valeurs non nulles sont 2024 : `suspect` 6896 et `aberrant` 1184 ; 2025 : `suspect` 6811 et `aberrant` 1184.

3. **Décrire les délais de publication** (R1)
   **Given** les lignes d'attribution initiale d'une année,
   **When** le rapport qualité est généré,
   **Then** il indique le nombre de dates de publication manquantes parmi toutes les lignes de l'année, puis pour les dates présentes le nombre de délais calculables, le nombre et le pourcentage des délais négatifs, et les quantiles continus p10, p50, p90 et p99 en jours,
   **And** chaque délai est calculé comme le nombre de jours entre `dateNotification` et `datePublicationDonnees` ; les dates de publication manquantes ne sont pas incluses dans le dénominateur du taux négatif ou les quantiles.
   Pour le snapshot identifié, les dates de publication manquantes sont 30 en 2024 et 33 en 2025 ; les délais négatifs sont 12244 (3,76 % de 325440 délais calculables) en 2024 et 13395 (4,24 % de 315965 délais calculables) en 2025. Les quantiles p10/p50/p90/p99 sont 2024 : 0/25/266/751,61 jours ; 2025 : 0/20/194/458 jours.

4. **Préserver le jeu et les comptes existants** (R1)
   **Given** le rapport initial et le Parquet préparé de la story 1.1,
   **When** la préparation complète le rapport qualité,
   **Then** les comptes de lignes et `uid` distincts d'attributions initiales et de modifications de la story 1.1 restent présents et identiques,
   **And** les nombres de lignes du Parquet préparé restent inchangés ; aucune ligne n'est filtrée sur la base de valeurs manquantes, de `montant_anomalie` ou d'un délai négatif.

5. **Tester les indicateurs qualité** (R1)
   **Given** un petit Parquet de test dont les valeurs manquantes, catégories de montant, dates manquantes et délais sont connus,
   **When** les tests du projet calculent et rendent le rapport qualité,
   **Then** ils vérifient les dénominateurs, les comptes et taux, les quantiles, les valeurs nulles et la présence de toutes les lignes,
   **And** le contrôle d'intégration sur le snapshot identifié compare les métriques aux baselines ci-dessus et échoue en cas d'écart.

Verify: `uv sync --locked`, `uv run --locked python -m unittest discover -s tests`, puis exécuter la commande du pipeline documentée dans le README. Contrôler dans `data/prepared/quality-report.md` les huit champs et leurs dénominateurs, les catégories de montant et les quantiles/taux de délai ci-dessus ; vérifier que le Parquet préparé conserve son nombre de lignes et que les comptes de la story 1.1 sont toujours présents.

## Boundaries

- Must not change: les mesures de valeurs manquantes, de montant et de délai portent sur les attributions initiales (`modification_id = 0`) de chaque année.
- Must not change: le taux de délai négatif est calculé parmi les seules lignes dont les deux dates permettent un délai ; le nombre de dates de publication manquantes est rapporté séparément.
- Must not change: les montants signalés, délais négatifs et champs manquants sont décrits, jamais exclus automatiquement.
- Must not change: le jeu préparé, le rapport et les résultats restent locaux et non publiés.
- Out of scope: modifier le schéma ou le contenu du Parquet préparé, recalculer la résolution des titulaires, ou interpréter les anomalies comme une preuve d'erreur dans un marché.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/tickets/epic-fondation-decp-reproductible/epic-fondation-decp-reproductible.md`, Requirements R1; Constraints C3–C4, C7; Done when.
- source — `docs/profilage-initial.md`, Valeurs manquantes; Montants et dates de publication; Limites et prochaines vérifications.
- prerequisite — `story-construire-et-executer-le-pipeline-decp.md`, sortie Parquet et rapport initial.

## Notes

- Decision: 2026-10-27 — Calculer les taux de champs manquants sur toutes les lignes d'attribution initiale de l'année ; calculer le taux négatif et les quantiles de délai seulement sur les dates de publication présentes, et rapporter à part les dates manquantes.
- Risk rationale: un dénominateur ambigu ou une exclusion silencieuse ferait varier l'interprétation de la qualité et pourrait biaiser les analyses en aval.
