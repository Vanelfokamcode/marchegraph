# Lancer la démo MarchéGraph sur Windows (PowerShell, sans WSL)

Fichier pour un agent. Objectif unique : lancer `src/marchegraph/demo_chat.py` en local et voir le graphe répondre. Exécute les étapes dans l'ordre, vérifie chaque résultat, et réponds à l'utilisateur en français. Contexte projet : `REPRISE-MARCHEGRAPH.md` (et `docs/handoff-copilot.md` s'il existe).

## Règles absolues
- Ne jamais afficher, journaliser ni commiter un mot de passe. Ne jamais commiter `.env`, `data/`, `.venv/`.
- Ne pas télécharger un nouveau snapshot DECP : les chiffres et les baselines dépendent du snapshot d'origine (SHA-256 ci-dessous). Les données doivent être copiées depuis la première machine.
- Tout reste local : Neo4j et Streamlit sur 127.0.0.1 uniquement. Aucun service distant, aucun envoi de données.
- Ne pas modifier le code du dépôt sans demander. Si une commande échoue à cause de Windows (chemins, signaux), décris l'erreur et propose un correctif minimal.
- Ne pas changer de branche ni pousser sans confirmation.

## Étape 1 : outils (PowerShell, rien n'est installé hormis Git)
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
Ferme et rouvre PowerShell. Puis :
    uv --version
    uv python install 3.12
Ignorer le message du Microsoft Store sur `python`. Utiliser uniquement `uv`.

## Étape 2 : dépôt et dépendances
    git status --short --branch
    git switch feature/refine-fondation-decp
    git pull
    uv sync --locked
    uv run --locked python -c "import streamlit, duckdb, neo4j; print('ok', streamlit.__version__)"
Vérifier que `src/marchegraph/demo_chat.py` existe. S'il manque, ou si `streamlit` n'est pas dans `uv.lock`, le dire à l'utilisateur (il faudra le commiter depuis la première machine).

## Étape 3 : tests sans Neo4j
    Remove-Item Env:NEO4J_PASSWORD -ErrorAction SilentlyContinue
    uv run --locked python -m unittest discover -s tests
Attendu : environ 42 tests réussis, un ignoré.

## Étape 4 : données (copie obligatoire, à demander à l'utilisateur)
Il faut `data\decp.parquet` et `data\prepared\` copiés depuis la première machine (clé USB ou partage réseau). Si absents, S'ARRÊTER et demander. Vérifier le snapshot :
    Get-FileHash data\decp.parquet -Algorithm SHA256
Valeur attendue : b39257f135aada4637797239489dce63365c9e9ac793688af45d9d06eed7b6f0
Si différente, s'arrêter et prévenir : ne pas continuer avec un autre snapshot.

## Étape 5 : Neo4j sans Docker
Docker Desktop exige WSL 2 ou Hyper-V, donc probablement un redémarrage : ne pas l'installer. Utiliser Neo4j Community 5.26 LTS en installation native.
1. Lire `compose.yaml` pour reprendre les réglages utiles (version, base `neo4j`, mémoire, extensions éventuelles, usage reporting désactivé).
2. Chercher dans la documentation officielle Neo4j la version de Java requise par Neo4j 5.26 et l'archive Windows de Neo4j Community 5.26 LTS. N'utiliser que cette version, depuis le site officiel, et ne pas inventer d'adresse de téléchargement.
3. Décompresser hors du dépôt (par exemple dans `C:\neo4j`). Configurer l'écoute sur 127.0.0.1 uniquement, et désactiver l'envoi de statistiques d'usage (vérifier les noms exacts des paramètres dans la documentation 5.26).
4. Définir le mot de passe initial avec la commande `neo4j-admin dbms set-initial-password` (à vérifier dans la documentation). Demander le mot de passe à l'utilisateur. Ne pas le choisir à sa place.
5. Démarrer en mode console dans un terminal dédié, puis attendre que Neo4j indique qu'il est démarré.
Si Neo4j n'arrive pas à démarrer, s'arrêter et rapporter l'erreur.

## Étape 6 : variables d'environnement pour la session (mot de passe saisi par l'utilisateur)
    $sec = Read-Host -AsSecureString "Mot de passe Neo4j"
    $env:NEO4J_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    $env:PYTHONPATH = "src"
L'URI par défaut des scripts est bolt://127.0.0.1:7687, avec l'utilisateur neo4j.

## Étape 7 : charger le graphe réel
    uv run --locked python -m marchegraph.graph.load_initial_awards
    uv run --locked python -m marchegraph.graph.load_modifications
Si un script demande des arguments, lire `--help`. Peut être long. Signaler toute erreur de mémoire en citant le message.

## Étape 8 : lancer la démo
    uv run --locked streamlit run src/marchegraph/demo_chat.py --server.address 127.0.0.1
Ouvrir http://127.0.0.1:8501. Critère de réussite : la barre latérale affiche des marchés par année (ordre de grandeur : 288 057 en 2024, 273 425 en 2025), et la question « Quels acheteurs ont attribué le plus de marchés en 2025 ? » renvoie un tableau avec des preuves. Une question hors sujet doit provoquer une abstention.

## Compte rendu attendu
Dire à l'utilisateur, en français, ce qui a réussi, ce qui a échoué, et ce qu'il doit faire lui-même. Ne pas marquer de story ni d'epic comme terminé.

## Exception décidée par l'utilisateur
Pour lancer la démo uniquement, un snapshot retéléchargé est accepté (le SHA-256 peut différer). Les chiffres seront légèrement différents de ceux de REPRISE-MARCHEGRAPH.md. Ne pas utiliser cette copie pour l'évaluation, ni pour les baselines de l'epic 2 ou 4.
