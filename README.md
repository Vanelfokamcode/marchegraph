# MarchéGraph — préparation DECP

Le pipeline prépare localement le snapshot `data/decp.parquet` avec DuckDB.
Il conserve les colonnes d'origine et toutes les lignes notifiées en 2024 et
2025, puis écrit le Parquet préparé, le manifeste de provenance et le rapport
de qualité dans `data/prepared/`. Les données restent locales et sont ignorées
par Git.

## Environnement et exécution

Python 3.12.3 et DuckDB 2.0.0 sont déclarés dans `pyproject.toml` et verrouillés
par `uv.lock`.

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked python src/marchegraph/data/prepare.py \
  --input data/decp.parquet \
  --output-dir data/prepared
uv run --locked python src/marchegraph/entity_resolution/prepare.py \
  --input data/prepared/decp.parquet \
  --output-dir data/prepared
uv run --locked python src/marchegraph/entity_resolution/evaluate.py \
  --input data/prepared/decp.parquet \
  --identities data/prepared/holder-identities.parquet \
  --output-dir data/prepared/holder-review
```

Le manifeste JSON indique le chemin source, son SHA-256, sa taille en octets,
la date d'extraction (`null`, car inconnue) et les chemins des sorties. Le
rapport de qualité distingue les lignes et les `uid` distincts des attributions
initiales (`modification_id = 0`) des modifications (`modification_id > 0`).
Il présente aussi, pour les attributions initiales de chaque année, les
comptes et taux de valeurs manquantes, les catégories de `montant_anomalie`,
les dates de publication manquantes et les quantiles des délais calculables.
Les anomalies sont signalées sans exclure de lignes.

La commande de résolution consomme ce Parquet préparé et écrit localement
`holder-identities.parquet` et `holder-resolution-report.md` dans le même
dossier. Elle regroupe les lignes d'attribution initiale par type et valeur
d'identifiant normalisés, conserve les identifiants manquants dans des
catégories non résolues, et ne rapproche pas les titulaires sur leur nom.

La commande d'évaluation crée localement un échantillon reproductible de
100 groupes résolus, 50 par année (graine 42), avec leurs variantes de noms.
Dans `holder-review-sample.csv`, renseignez `manual_review_label` avec
`correct`, `incorrect` ou `indeterminate`, et ajoutez éventuellement une note.
`correct` signifie que les éléments disponibles soutiennent un titulaire
unique ; `incorrect` signale un groupe qui semble mélanger plusieurs titulaires ;
`indeterminate` indique que les éléments sont insuffisants. Consultez
`holder-review-name-variants.csv` par `sample_id`, puis relancez la commande
pour recalculer le rapport. Les labels vides sont comptés comme en attente ;
les cas indéterminés sont exclus du dénominateur de précision et rapportés
séparément. L'échantillon, les noms et les labels restent locaux.

Le pipeline refuse un snapshot différent de celui profilé tant que ses
baselines n'ont pas été réévaluées. Une erreur de lecture, un snapshot
incompatible ou un échec d'écriture renvoie un code non nul et ne remplace pas
les sorties préparées existantes par un résultat incomplet.
