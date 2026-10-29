# MarchéGraph DECP — dossier de reprise

Ce document est le point d'entrée pour reprendre le projet dans un nouveau
chat. Il résume l'objectif, les décisions, l'organisation du dépôt, les
réalisations, l'état BMAD et le travail restant. Le backlog BMAD et le code
restent les sources de vérité détaillées.

## Reprise rapide

- Dépôt : `Vanelfokamcode/marchegraph`.
- Branche de travail : `feature/refine-fondation-decp`.
- Initiative BMAD : [`_bmad-output/initiative-marchegraph-decp/`](./_bmad-output/initiative-marchegraph-decp/).
- État BMAD au dernier contrôle : epics 1 à 3 terminées ; epic 4 raffinée
  en sept stories (approuvées le 2026-10-29), story 4.1 en cours.
- Prochaine action : poursuivre la story 4.1 (test de capacité du modèle
  local, voir `docs/spike-modele-local-resultats.md`) et faire trancher les
  questions ouvertes listées dans le fichier de l'epic 4.
- Ne pas marquer une story acceptée ni un epic terminé sans confirmation
  explicite de l'utilisateur.
- Les données DECP, les résultats dérivés, les exports et les labels de revue
  restent locaux et ne doivent pas être ajoutés à Git.

## But du projet et périmètre

MarchéGraph transforme un snapshot DECP Parquet en jeu analytique préparé,
résout les identités de titulaires, construit un graphe vérifiable et vise un
assistant GraphRAG local qui répond en français avec des preuves ou s'abstient.

- Périmètre principal : marchés notifiés en 2025, toutes régions ; comparaison
  secondaire : 2024.
- Une attribution initiale est une ligne avec `modification_id = 0`. Les
  statistiques de marchés initiaux comptent les `uid` distincts ; les
  modifications sont analysées séparément.
- La région étudiée est celle de l'acheteur.
- Le projet porte sur les DECP publiées, et non sur les paiements, factures ou
  l'exécution financière complète des marchés.
- Démonstration et traitements locaux uniquement ; pas de publication de
  données ligne à ligne ou de résultats dérivés.

## Source de données et mesures de profilage

Snapshot local : `data/decp.parquet`.

- Taille : 250 253 419 octets.
- SHA-256 :
  `b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0`.
- Date d'extraction : inconnue ; le manifeste doit la conserver comme `null`.
- Attribution initiale 2024 : 325 470 lignes et 288 057 `uid` distincts.
- Attribution initiale 2025 : 315 998 lignes et 273 425 `uid` distincts.
- Modifications 2024 : 220 519 lignes et 89 737 `uid` distincts.
- Modifications 2025 : 271 210 lignes et 104 722 `uid` distincts.
- Les identifiants sont conservés comme chaînes, notamment pour préserver les
  zéros initiaux. Les anomalies de montant et les délais de publication
  négatifs sont signalés, pas filtrés silencieusement.

Les chiffres proviennent du snapshot profilé. Si le snapshot change, le
pipeline refuse les baselines existantes tant qu'elles n'ont pas été
réévaluées.

## Décisions de conception à préserver

### Données et titulaires

- DuckDB prépare les données localement et produit un Parquet, un manifeste de
  provenance et un rapport de qualité.
- Les colonnes source et les lignes du périmètre 2024–2025 sont conservées.
- Une identité titulaire est déterminée par la paire
  `(type d'identifiant normalisé, valeur normalisée)`.
- Le type est nettoyé des espaces périphériques et mis en majuscules ; la
  valeur est nettoyée des espaces périphériques seulement. Casse, ponctuation,
  espaces internes et zéros initiaux sont conservés.
- Aucun rapprochement automatique par nom seul, et aucune fusion SIRET/SIREN.
  Les identifiants manquants restent non résolus, sans inférer que le titulaire
  n'existe pas.
- L'évaluation manuelle mesure la précision des groupes résolus ; elle ne
  prétend pas mesurer le rappel. Les cas indéterminés sont séparés du
  dénominateur.
- L'epic 2 a utilisé un échantillon reproductible de 100 groupes, 50 par
  année, avec graine 42. La revue manuelle est terminée et l'epic 2 est
  acceptée.

### Graphe et requêtes

- Un seul nœud `Marche` par `uid`, avec plusieurs relations titulaires possibles.
- Chaque modification est un nœud de version identifié par
  `(uid, modification_id)`, pas un nouveau marché initial.
- Une version sans attribution initiale dans le snapshot est conservée comme
  modification non liée ; aucun marché fictif n'est créé.
- Les champs source qui divergent entre lignes sont représentés comme
  ensembles de valeurs distinctes, avec les absences signalées. Aucune valeur
  n'est choisie arbitrairement.
- Neo4j Community 5.26 LTS est l'unique source de vérité modifiable du graphe.
  L'export RDF est généré depuis Neo4j ; OWL, SKOS et SHACL sont utilisés pour
  l'ontologie, CPV et validation.
- Contrat des questions : résultats structurés, preuves issues du graphe et
  limites explicites. Les requêtes Cypher sont préparées, paramétrées et en
  lecture seule côté application.
- Q1 : classement national 2025, sans filtre de région.
- Q5 : résumés séparés par nature et par procédure ; ne pas inventer les
  paires perdues par l'agrégation source.
- Q3/Q8 : familles CPV définies par les trois premiers chiffres. Une valeur
  unique de montant/durée compte une fois malgré d'autres lignes manquantes ;
  les valeurs multiples sont exclues de l'agrégat correspondant et rapportées.
- Q7 : recherche thématique par sous-chaîne insensible à la casse dans l'objet ;
  inclusion régionale seulement quand une valeur de région acheteur unique est
  disponible, avec les cas manquants ou multivalués explicités.
- Q9 : variantes de noms sous une identité titulaire déjà résolue ; le nom
  n'est jamais utilisé seul pour fusionner des titulaires.
- Q10 : absences et valeurs multiples sont distinguées ; l'hétérogénéité
  source n'est pas automatiquement qualifiée d'erreur.
- Un modèle local ne peut être retenu qu'après un test de capacité. Aucun
  service LLM distant ni envoi de contexte dérivé des DECP n'est autorisé.

## Architecture et structure du dépôt

Architecture : monolithe modulaire Python, commandes distinctes pour le
pipeline et l'interface, Neo4j local comme service de base de données. Le
domaine et les contrats ne doivent pas dépendre de l'interface ou des pilotes.
Voir [l'architecture BMAD](./_bmad-output/initiative-marchegraph-decp/architecture-marchegraph-decp/architecture-marchegraph-decp.md).

```text
.
├── _bmad-output/initiative-marchegraph-decp/
│   ├── initiative-marchegraph-decp.md
│   ├── architecture-marchegraph-decp/
│   └── tickets/
│       ├── tickets.toml
│       ├── epic-fondation-decp-reproductible/
│       ├── epic-resolution-identites-titulaires/
│       ├── epic-graphe-connaissance-verifiable/
│       └── epic-assistant-graphrag-local-evalue/
├── docs/
│   ├── brief.md
│   ├── profilage-initial.md
│   └── exemple/                 # ontologie, formes SHACL, RDF et Cypher
├── src/
│   ├── profilage_01.py
│   └── marchegraph/
│       ├── data/                # préparation DuckDB
│       ├── entity_resolution/   # normalisation et évaluation titulaires
│       └── graph/               # Neo4j, imports, requêtes, RDF et SHACL
├── tests/                       # tests unitaires et intégration Neo4j
├── compose.yaml                 # Neo4j local
├── pyproject.toml
├── uv.lock
├── README.md
└── REPRISE-MARCHEGRAPH.md       # ce document
```

Les sorties se trouvent sous `data/`, ignoré par Git : Parquet préparé,
manifestes, rapports, échantillons de revue, export RDF et rejets. L'installation
locale de BMAD (`_bmad/`, `.agents/skills/`, `skills-lock.json`) est également
ignorée ; les artefacts projet BMAD suivis sont sous `_bmad-output/`.

### Modules principaux

- [`src/marchegraph/data/prepare.py`](./src/marchegraph/data/prepare.py) :
  préparation DECP et rapport de qualité.
- [`src/marchegraph/entity_resolution/identity.py`](./src/marchegraph/entity_resolution/identity.py) :
  normalisation et clés d'identité typées.
- [`src/marchegraph/entity_resolution/prepare.py`](./src/marchegraph/entity_resolution/prepare.py) :
  préparation des identités titulaires.
- [`src/marchegraph/entity_resolution/evaluate.py`](./src/marchegraph/entity_resolution/evaluate.py)
  et [`evaluation.py`](./src/marchegraph/entity_resolution/evaluation.py) :
  échantillon et calcul de précision.
- [`src/marchegraph/graph/contracts.py`](./src/marchegraph/graph/contracts.py) :
  contrats de réponses et preuves indépendants de Neo4j.
- [`src/marchegraph/graph/load_initial_awards.py`](./src/marchegraph/graph/load_initial_awards.py)
  et [`load_modifications.py`](./src/marchegraph/graph/load_modifications.py) :
  imports idempotents.
- [`src/marchegraph/graph/queries.py`](./src/marchegraph/graph/queries.py) :
  les dix questions de référence.
- [`src/marchegraph/graph/validation.py`](./src/marchegraph/graph/validation.py)
  et [`rdf_export.py`](./src/marchegraph/graph/rdf_export.py) :
  validation SHACL, traçage des rejets et export RDF.
- [`src/marchegraph/graph/demo.py`](./src/marchegraph/graph/demo.py) :
  tracer bullet synthétique local.

## Travail réalisé

### Profilage, cadrage et fondation reproductible

- Profilage du snapshot et production du brief et du rapport de profilage.
- Initiative BMAD MarchéGraph DECP créée, puis découpée en quatre epics.
- Epic 1 implémentée : pipeline DuckDB reproductible, manifeste, contrôle de
  snapshot, rapport qualité, champs manquants, anomalies de montant et
  statistiques de délais de publication.
- Les limites mémoire du traitement complet ont été traitées avec une limite
  DuckDB de 768 Mo, un seul thread et un répertoire de spill temporaire.
- Epic 1 et ses stories 1.1/1.2 sont `done`.

### Résolution des identités titulaires

- Epic 2 implémentée : rapprochement déterministe par identifiant typé,
  catégories non résolues, rapports annuels et évaluation manuelle.
- Échantillon de revue local, reproductible, noms variantes et rapport de
  précision ; les données et labels ne sont pas dans Git.
- Story 2.1, story 2.2 et epic 2 sont `done`.

### Graphe vérifiable

- Story 3.1 : modèle et tracer bullet synthétique Neo4j, preuves et export RDF
  validé par SHACL.
- Story 3.2 : import idempotent des attributions initiales et liens titulaires.
- Story 3.3 : versions de modifications, y compris les versions sans marché
  initial dans le snapshot.
- Story 3.4 : validation SHACL, identifiants de règle et traçage des rejets.
- Stories 3.5–3.7 : dix questions de référence, contrats de réponse/preuve,
  limites explicites et gestion des valeurs manquantes/multivaluées.
- Story 3.8 : revue de refactor et vérification des dettes différées.
- Story 3.9 : intégration locale de bout en bout avec fixtures Parquet, imports,
  dix questions, validation, export et rejets. Une revue de clôture a conduit
  à corriger les contrats de résultat et la restriction des connexions à
  loopback ; la story est repassée en revue après ces corrections.
- Stories 3.1–3.8 : `done`. Story 3.9 : `built` / `review`, en attente de
  l'acceptation utilisateur. Epic 3 : `in-progress`.

### Validation connue

Au dernier contrôle de l'implémentation du graphe :

- Suite standard : 42 tests réussis, un test d'intégration ignoré si
  `NEO4J_PASSWORD` n'est pas défini.
- Test E2E Neo4j local : un test réussi avec le secret local défini.
- `compileall` et `git diff --check` réussis.
- Les identifiants Neo4j des fixtures ont été contrôlés comme nettoyés après
  l'intégration.

Relancer les validations avant toute nouvelle clôture ou présentation.

## Commandes de travail

Environnement : Python 3.12.3, uv, DuckDB 2.0.0, pilote Neo4j 6.4.1,
RDFLib 7.1.4 et PySHACL 0.30.1. Installer/synchroniser avec le lock :

```bash
uv sync --locked
uv run --locked python -m unittest discover -s tests
```

Préparation des données et résolution des identités :

```bash
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

Démarrage et démonstration Neo4j synthétique :

```bash
export NEO4J_PASSWORD='<mot-de-passe local>'
docker compose up -d --wait
PYTHONPATH=src uv run --locked python -m marchegraph.graph.demo
```

Importer les données réelles dans le Neo4j local :

```bash
PYTHONPATH=src uv run --locked python -m marchegraph.graph.load_initial_awards
PYTHONPATH=src uv run --locked python -m marchegraph.graph.load_modifications
```

Test d'intégration locale (il est ignoré dans la suite standard sans le secret
`NEO4J_PASSWORD`) :

```bash
uv run --locked python -m unittest tests.test_graph_end_to_end
```

Toutes les commandes d'import et de démo doivent refuser une URI Neo4j
distante ; utiliser uniquement `localhost`, `127.0.0.1` ou `::1`.

## État BMAD et chemin jusqu'à la fin

La source de suivi est
[`_bmad-output/initiative-marchegraph-decp/`](./_bmad-output/initiative-marchegraph-decp/).
Le dernier `tickets.py status` a rapporté 12 éléments sur 13 `done`, et une
story `review`.

| Epic | État | Éléments |
|---|---|---|
| 1 — Fondation DECP reproductible | `done` | Stories 1.1 et 1.2 `done`. |
| 2 — Résolution des identités titulaires | `done` | Stories 2.1 et 2.2 `done`. |
| 3 — Graphe de connaissance vérifiable | `done` | Stories 3.1–3.9 `done`. |
| 4 — Assistant GraphRAG local évalué | `in-progress` | Raffinée : stories 4.1–4.7 ; 4.1 en cours. |

Étapes restantes :

1. Représenter à l'utilisateur l'état final corrigé de la story 3.9 et recueillir
   son acceptation. Ne pas présumer que l'acceptation antérieure couvre les
   corrections de revue.
2. Après acceptation, passer 3.9 à `done`, vérifier les critères de clôture et
   dépendances BMAD, puis demander confirmation avant de terminer l'epic 3.
3. Rouvrir l'epic 4 comme prochaine étape. La raffiner à partir des exigences
   R4/R6 et des règles AD-3–AD-5 de l'architecture ; faire approuver son
   découpage en stories avant leur implémentation.
4. Construire l'assistant local : réponses en français, preuves du graphe,
   abstention quand les preuves manquent, interface locale selon le périmètre
   approuvé.
5. Évaluer par question face à une baseline LLM sans graphe ; fixer tout seuil
   après mesure de la baseline, et documenter correction, hallucinations et
   coûts. Aucun LLM distant ni envoi de données DECP dérivées.
6. Exécuter les vérifications d'initiative, mettre à jour les tickets BMAD et
   vérifier que les livrables de démo restent locaux.
7. Ne déclarer l'initiative terminée qu'après la revue des critères de fin et
   confirmation de l'utilisateur.

Le périmètre détaillé de l'epic 4 est dans
[`epic-assistant-graphrag-local-evalue.md`](./_bmad-output/initiative-marchegraph-decp/tickets/epic-assistant-graphrag-local-evalue/epic-assistant-graphrag-local-evalue.md).
Ne pas inventer de stories ni fixer un seuil d'évaluation avant le travail de
raffinement et l'observation de la baseline.

## Git, commits et reprise de branche

La branche de travail utilisée est `feature/refine-fondation-decp` et elle
trace `origin/feature/refine-fondation-decp`. Pour connaître l'état exact lors
de la reprise :

```bash
git status --short --branch
git log --oneline --decorate -20
git log --oneline origin/feature/refine-fondation-decp..HEAD
```

Les jalons principaux de l'historique :

- Profilage initial et définition de l'initiative : `0f20130`, `28c3e71`,
  `e111c4f`, `ccfa4e1`.
- Fondation reproductible et qualité : `901e3ca`, `29956be`, `6a6a511`.
- Résolution des titulaires et évaluation : `083ea54`, `1aa37eb`, `c5383a4`,
  `ff3e647`.
- Graphe et décisions techniques : `b4eb260`, `e75ff10`, `52a4d57`,
  `079557c`, `94c072a`, `40ca2b9`, `fb6258e`, `d80b493`, `9949f67`,
  `9b22b9a`.
- Le commit `9b22b9a` corrige l'architecture des contrats partagés et la
  validation loopback après la revue de la story 3.9.

La liste complète et l'ordre exact sont consultables avec `git log`. Ne pas
modifier ni pousser une autre branche simplement parce qu'elle existe
localement ; confirmer la branche courante et son upstream avant toute
opération Git. Chaque nouveau commit doit inclure le trailer :

```text
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```
