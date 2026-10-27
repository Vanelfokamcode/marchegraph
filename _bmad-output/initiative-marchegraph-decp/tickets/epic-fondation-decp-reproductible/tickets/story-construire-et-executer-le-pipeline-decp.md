---
id: 1
type: story
title: "Construire et exécuter le pipeline DECP"
parent: epic-fondation-decp-reproductible
covers: [R1, R2]
after: []
hitl: true
risk: high
refined: true
---

# Construire et exécuter le pipeline DECP

## Description

Installe un socle reproductible avec Python 3.12.3 et DuckDB 2.0.0 verrouillés, une commande locale documentée et des tests intégrés. La personne exécute le pipeline sur le snapshot DECP identifié et vérifie le jeu préparé, sa provenance et les comptes annuels séparés des attributions initiales et des modifications.

## Requirements

1. **Installer et exécuter localement** (R1)
   **Given** le dépôt et le snapshot identifié présents localement,
   **When** la personne suit les instructions du projet pour synchroniser l'environnement verrouillé puis lance la commande documentée avec `data/decp.parquet` et `data/prepared/` comme entrées/sortie,
   **Then** Python 3.12.3 et DuckDB 2.0.0 sont déclarés dans le projet et verrouillés dans `uv.lock`, et la commande génère `data/prepared/decp.parquet`, `data/prepared/manifest.json` et `data/prepared/quality-report.md`,
   **And** ces données et sorties locales restent ignorées par Git.
   Une entrée absente ou illisible, ou un dossier de sortie inutilisable, produit une erreur explicite et un code de sortie non nul ; le manifeste et le rapport ne présentent pas une exécution comme réussie.

2. **Préparer le jeu analytique** (R1, R2)
   **Given** le snapshot local,
   **When** la commande prépare le Parquet,
   **Then** le fichier contient les colonnes d'origine et toutes les lignes dont `dateNotification` se situe en 2024 ou 2025, sans restriction géographique,
   **And** les lignes avec `modification_id = 0` et celles avec `modification_id > 0` restent présentes et distinguables dans le fichier.
   Les montants signalés, délais négatifs, valeurs manquantes et lignes avec plusieurs titulaires ne sont pas supprimés au titre de cette préparation.

3. **Tracer la provenance** (R1)
   **Given** une exécution réussie,
   **When** la personne consulte `data/prepared/manifest.json`,
   **Then** le JSON décrit le chemin du fichier source, son SHA-256, sa taille en octets, la date d'extraction comme inconnue (`null`) et le chemin des deux sorties.
   Pour le snapshot identifié, le SHA-256 est `b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0` et sa taille est de 250253419 octets.

4. **Séparer les comptes annuels** (R2)
   **Given** les lignes préparées dont la date de notification tombe en 2024 ou 2025,
   **When** la personne consulte `data/prepared/quality-report.md`,
   **Then** le rapport donne, pour chaque année, le nombre de lignes et le nombre de `uid` distincts parmi les attributions initiales (`modification_id = 0`), puis séparément ces deux comptes pour les modifications (`modification_id > 0`).
   Pour le snapshot identifié, les quatre comptes sont 2024 : 325470 lignes initiales / 288057 `uid` distincts et 220519 lignes de modification / 89737 `uid` distincts ; 2025 : 315998 / 273425 et 271210 / 104722 respectivement.

5. **Vérifier le pipeline** (R1, R2)
   **Given** l'environnement verrouillé,
   **When** la personne exécute les tests du projet puis la commande documentée sur le snapshot local,
   **Then** les tests couvrent les filtres d'année, la conservation des colonnes et des lignes, la séparation des comptes, la provenance et les erreurs d'entrée/sortie,
   **And** le contrôle intégré des comptes sur le snapshot préparé passe ; une divergence avec les baselines ci-dessus fait échouer la vérification.

Verify: `uv sync --locked`, puis les tests documentés du projet et la commande de préparation documentée sur `data/decp.parquet`. Contrôler que les trois sorties locales existent, que leur provenance est exacte, et que les comptes du rapport correspondent aux baselines ci-dessus.

## Boundaries

- Must not change: le périmètre comprend 2025 toutes régions, selon la région de l'acheteur, et 2024 comme comparaison secondaire.
- Must not change: les comptes d'attributions initiales utilisent les `uid` distincts avec `modification_id = 0` ; les lignes de modification restent présentes et comptées séparément.
- Must not change: aucune ligne n'est écartée pour une valeur manquante, un montant signalé ou un délai de publication négatif.
- Must not change: le snapshot, le Parquet préparé, le manifeste et le rapport restent locaux et non publiés.
- Out of scope: compléter les indicateurs détaillés de valeurs manquantes, d'anomalies de montants et de délais de publication, couverts par la story 1.2.

## References

- parent — `_bmad-output/initiative-marchegraph-decp/tickets/epic-fondation-decp-reproductible/epic-fondation-decp-reproductible.md`, Requirements R1–R2; Constraints C1–C5, C7; Done when.
- architecture — `_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md`, AD-1, AD-4; conventions données, qualité et erreurs.
- profile — `docs/profilage-initial.md`, Périmètre et méthode; Résultats observés.

## Notes

- Decision: 2026-10-27 — Utiliser `pyproject.toml` et `uv.lock` pour déclarer/verrouiller Python 3.12.3 et DuckDB 2.0.0 ; documenter une commande locale `uv run` qui prend le snapshot et le dossier de sortie comme arguments.
- Decision: 2026-10-27 — Conserver les colonnes d'origine et les lignes 2024/2025, y compris les modifications ; représenter la date d'extraction inconnue par `null` dans le manifeste JSON.
- Risk rationale: une erreur de sélection ou de comptage fausserait le jeu transmis aux epics de résolution des titulaires et de graphe.
- Contrôle supplémentaire du risque : comparer indépendamment les quatre comptes 2025 au snapshot local par une requête DuckDB directe.
