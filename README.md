# MarchéGraph — préparation DECP

Le pipeline prépare localement le snapshot `data/decp.parquet` avec DuckDB.
Il conserve les colonnes d'origine et toutes les lignes notifiées en 2024 et
2025, puis écrit le Parquet préparé, le manifeste de provenance et le rapport
de qualité dans `data/prepared/`. Les données restent locales et sont ignorées
par Git.

## Environnement et exécution

Python 3.12.3, DuckDB 2.0.0, le pilote Neo4j 6.4.1, RDFLib 7.1.4 et PySHACL
0.30.1 sont déclarés dans `pyproject.toml` et verrouillés par `uv.lock`.

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

## Démonstration locale du graphe

Le tracer bullet utilise uniquement des données synthétiques : un acheteur,
un marché `uid`, deux titulaires reliés au même marché et une modification
représentée par un nœud de version. Il charge ce cas dans Neo4j, répond à la
question de référence 1 avec ses références de preuve, valide le graphe RDF
avec SHACL et écrit un export local. Il ne lit pas le snapshot DECP.

Au premier démarrage, définissez un mot de passe local non partagé. Conservez
la même valeur pour ce volume Neo4j ; changer seulement la variable
d'environnement ne modifie pas les identifiants déjà initialisés. Démarrez
Neo4j et lancez la démonstration :

```bash
export NEO4J_PASSWORD='choose-a-local-password'
docker compose up -d --wait
uv sync --locked
PYTHONPATH=src uv run --locked python -m marchegraph.graph.demo
```

Neo4j et son port Bolt sont liés à `127.0.0.1`. `docker compose up -d --wait`
peut être utilisé pour attendre la disponibilité complète. Le mot de passe est
fourni par l'environnement et ne doit pas être enregistré dans le dépôt.
Les commandes de démonstration et d'import refusent une `NEO4J_URI` qui ne
pointe pas vers `localhost`, `127.0.0.1` ou `::1`.
L'export est écrit dans `data/prepared/graph-demo/graph-demo.ttl`, sous un
chemin ignoré par Git.

### Import réel des attributions initiales

Après la préparation des identités titulaires, le chargeur importe localement
les attributions initiales 2024 et 2025 depuis les deux Parquet préparés :

```bash
PYTHONPATH=src uv run --locked python -m marchegraph.graph.load_initial_awards
```

Le chargeur conserve un seul marché par `uid`, relie les titulaires dont
l'identité typée est résolue et conserve les valeurs distinctes des attributs
qui varient entre lignes. Les valeurs manquantes sont signalées séparément ;
aucune identité non résolue ne crée de lien titulaire. Les lots sont idempotents
et la commande vérifie les comptes annuels de marchés, titulaires résolus et
liens contre les Parquet. Elle n'affiche que ces comptes agrégés.

Après l'import initial, les versions de modification se chargent séparément :

```bash
PYTHONPATH=src uv run --locked python -m marchegraph.graph.load_modifications
```

Le chargeur crée une version par couple `(uid, modification_id)`. Il relie
chaque version à un marché initial existant ; si le snapshot ne contient pas
ce marché, il conserve la version sans lien, marque explicitement cette limite
et en rapporte le nombre, sans créer de marché fictif.

### Vérification bout en bout sur fixture locale

Le test d'intégration charge des Parquet synthétiques dans Neo4j local,
exécute les dix questions de référence, puis charge et relit le tracer bullet
synthétique dans Neo4j avant de vérifier la validation SHACL et son export RDF.
Il vérifie aussi la traçabilité JSON Lines d'un rejet. Il refuse toute URI
Neo4j qui ne pointe pas vers `localhost`, `127.0.0.1` ou `::1`, et supprime ses
nœuds de fixture à la fin. Il n'utilise ni le snapshot DECP ni de service
distant ; les fichiers d'export et de rejet restent dans un dossier temporaire.

Après avoir démarré Neo4j local et défini `NEO4J_PASSWORD`, lancez :

```bash
uv run --locked python -m unittest tests.test_graph_end_to_end
```

Sans `NEO4J_PASSWORD`, ce test d'intégration est ignoré ; la suite standard
reste exécutable sans Neo4j.

### Validation locale et rejets

La validation SHACL de `marchegraph.graph.validation.validate_graph` ne modifie
pas le graphe : chaque nœud qui enfreint une règle reste dans les données et le
rapport expose ses triples RDF, l'identifiant stable de chaque règle et son
motif. Les rejets peuvent être conservés localement en JSON Lines, un
enregistrement par nœud, avec les triples et motifs associés :

```python
from pathlib import Path

from marchegraph.graph.validation import validate_graph, write_rejections

report = validate_graph(data_graph, shapes_graph, ontology_graph)
if not report.conforms:
    write_rejections(report, Path("data/prepared/graph-demo/rejections.jsonl"))
```

Les identifiants `MG-VAL-*` définis dans `docs/exemple/formes.ttl` sont
retournés avec chaque motif. Le fichier de rejets est local et doit rester
ignoré par Git, comme les autres sorties dérivées.

### Questions de référence sur les acheteurs et titulaires

Le module `marchegraph.graph.queries` expose un contrat commun :
chaque réponse porte son ou ses numéros de question, ses résultats structurés,
les références aux marchés et relations qui les étayent, ainsi que les limites
connues. Les requêtes sont en lecture seule et paramétrées. Exemple sur le
graphe des attributions initiales chargé localement dans Neo4j :

```python
from neo4j import GraphDatabase

from marchegraph.graph.queries import (
    find_holders_with_multiple_buyers,
    rank_buyers,
    rank_holders_for_buyer,
    summarize_nature_and_procedures,
)

with GraphDatabase.driver(uri, auth=(username, password)) as driver:
    with driver.session() as session:
        buyers = rank_buyers(session, year=2025)
        recurrent_holders = rank_holders_for_buyer(session, "buyer-id", year=2025)
        procedures = summarize_nature_and_procedures(session, year=2025)
        multi_buyer_holders = find_holders_with_multiple_buyers(session, year=2025)
```

Les `rows` contiennent les objets `result` et leurs `evidence` ; chaque preuve
identifie le type de nœud, son identifiant, le lien ou la propriété interrogée
et sa valeur. La question 1 classe les acheteurs au niveau national. La
question 5 fournit des décomptes distincts par nature et par procédure, sans
fabriquer de paires nature–procédure à partir de valeurs multivaluées. Les
nombres de valeurs absentes et multiples sont inclus dans les limites de cette
réponse. Les classements des questions 1, 2 et 6
retournent les dix premiers résultats par défaut ; le paramètre `limit` permet
de choisir une autre limite, reportée dans les limites de la réponse.

La même API couvre les questions 3 et 8 :

```python
from marchegraph.graph.queries import aggregate_amounts_and_durations_by_cpv

amounts_and_durations = aggregate_amounts_and_durations_by_cpv(session, year=2025)
```

Le résultat regroupe par groupe CPV (les trois premiers chiffres). Les montants
sont additionnés en `Decimal` ; un marché à montant ou durée unique compte une
fois même si d'autres lignes source sont manquantes. Les valeurs distinctes
multiples sont exclues de l'agrégat correspondant et rapportées séparément.
Chaque famille fournit les comptes et les preuves, avec au plus 25 marchés de
preuve par mesure ; `evidence_complete` indique si l'échantillon est complet.
Les montants restent des montants déclarés, pas des paiements ; un montant
d'accord-cadre peut représenter un plafond.

Les questions 4, 7, 9 et 10 réutilisent le même contrat :

```python
from marchegraph.graph.queries import (
    find_holder_name_variants,
    find_theme_in_buyer_region,
    summarize_graph_data_issues,
    summarize_modification_history,
)

history = summarize_modification_history(session, year=2025)
themed_markets = find_theme_in_buyer_region(
    session, theme="voirie", region_code="11", year=2025
)
name_variants = find_holder_name_variants(session)
data_issues = summarize_graph_data_issues(session)
```

Le chargement initial conserve maintenant les codes régionaux acheteur par
marché et les marqueurs de valeurs manquantes. La recherche thématique utilise
une sous-chaîne insensible à la casse dans l'objet et ne rattache un marché à
une région que si une seule région source est disponible. L'historique sépare
les versions reliées des versions sans marché initial ; la recherche de
variantes de titulaires utilise uniquement les identifiants typés déjà
résolus, jamais le nom seul. Le rapport de données distingue les champs absents
des champs multivalués ; ces derniers sont signalés sans être automatiquement
qualifiés d'erreurs. Les listes de preuves sont échantillonnées lorsque le
volume est important, et chaque ligne indique si l'échantillon est complet.

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
