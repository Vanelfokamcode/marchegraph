# MarchéGraph — préparation DECP

Le pipeline prépare localement le snapshot `data/decp.parquet` avec DuckDB.
Il conserve les colonnes d'origine et toutes les lignes notifiées en 2024 et
2025, puis écrit le Parquet préparé, le manifeste de provenance et le rapport
initial dans `data/prepared/`. Les données restent locales et sont ignorées par
Git.

## Environnement et exécution

Python 3.12.3 et DuckDB 2.0.0 sont déclarés dans `pyproject.toml` et verrouillés
par `uv.lock`.

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
uv run --locked python src/marchegraph/data/prepare.py \
  --input data/decp.parquet \
  --output-dir data/prepared
```

Le manifeste JSON indique le chemin source, son SHA-256, sa taille en octets,
la date d'extraction (`null`, car inconnue) et les chemins des sorties. Le
rapport initial distingue les lignes et les `uid` distincts des attributions
initiales (`modification_id = 0`) des modifications (`modification_id > 0`).
Le profil détaillé des valeurs manquantes, anomalies de montant et délais de
publication sera ajouté dans l'étape suivante.

Le pipeline refuse un snapshot différent de celui profilé tant que ses
baselines n'ont pas été réévaluées. Une erreur de lecture, un snapshot
incompatible ou un échec d'écriture renvoie un code non nul et ne remplace pas
les sorties préparées existantes par un résultat incomplet.
