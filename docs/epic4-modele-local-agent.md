# Epic 4 : test du modèle local, puis raffinement (fichier pour un agent)

Fichier autonome pour un agent dans VS Code. Réponds à l'utilisateur en français. Contexte projet : `REPRISE-MARCHEGRAPH.md`, `docs/handoff-copilot.md` (s'il existe), `docs/epic4-notes-raffinement.md`, l'architecture (`AD-3` à `AD-5`) et le fichier de l'epic 4 sous `_bmad-output/initiative-marchegraph-decp/tickets/`.

## Objectif
Projet complet pour la démo : assistant déterministe (compréhension de la question par règles, requêtes préparées existantes) + formulation en français par un modèle local, avec contrôle automatique des chiffres, comparés à une baseline sans graphe.

## Règles absolues
- Aucun service LLM distant. Aucune donnée DECP ni résultat dérivé envoyé à un modèle ou à un service externe. Le test du modèle utilise uniquement des données synthétiques.
- Ollama écoute uniquement en local (127.0.0.1:11434). Ne jamais définir `OLLAMA_HOST` sur une adresse publique.
- Télécharger un modèle est autorisé (c'est le modèle, pas des données du projet), mais DEMANDER avant chaque installation de logiciel et avant chaque téléchargement de modèle (plusieurs Go).
- Ne pas modifier AD-3 : le modèle ne génère ni n'exécute de Cypher et ne produit pas les références de preuve. Il formule du texte uniquement à partir d'un résultat structuré.
- Ne fixer aucun seuil de réussite avant la mesure de la baseline. Pendant la phase A, rapporter des mesures, pas des verdicts.
- Ne pas marquer une story ou un epic comme terminé, ne pas modifier `tickets.toml`, sans confirmation de l'utilisateur. Ne pas implémenter l'epic 4 avant approbation du découpage.
- Ne jamais afficher ni commiter de mot de passe, `.env`, `data/`, `.venv/`. Ne pas commiter sans demander ; l'utilisateur commite lui-même (pas de trailer Copilot sur ses commits).

## Machine de référence
16 Go de RAM, pas de carte NVIDIA (processeur seul), Windows, PowerShell. Neo4j, DuckDB et Streamlit partagent cette mémoire avec le modèle : viser des modèles de 4 à 8 milliards de paramètres.

## Décisions déjà prises par l'utilisateur (à ne pas remettre en cause)
1. Cible = projet complet.
2. Compréhension de la question déterministe, AD-3 inchangée.
3. Questions prises en charge = les dix questions de référence de l'epic 3.
4. Réponse correcte = résultat structuré identique à la référence, ou abstention attendue et effective.
5. Hallucination = tout fait, chiffre ou entité du texte absent du résultat structuré reçu.
6. Coûts = latence et mémoire locales, pas d'API.
7. Baselines : le même modèle local sans graphe (obligatoire) ; baseline SQL sur le Parquet via DuckDB (option, à faire approuver).

## PHASE A : test de capacité du modèle local

### A1. Vérifier l'état
    git status --short --branch
Ne rien faire d'autre si le dépôt n'est pas propre sans en parler à l'utilisateur.

### A2. Ollama
    ollama --version
Si la commande est absente : DEMANDER, puis `winget install Ollama.Ollama`, fermer et rouvrir le terminal, `ollama --version`. Ollama passe seul en mode processeur sans GPU.
Vérifier que le serveur répond : `ollama list`. S'il ne répond pas, `ollama serve` dans un terminal dédié.

### A3. Modèles à comparer
DEMANDER avant de télécharger. Candidats de départ (vérifier les noms exacts sur ollama.com/library ; si un nom est refusé, proposer le plus proche) :
    ollama pull llama3.1:8b
    ollama pull qwen3:8b
Ajouter un modèle de 4 milliards de paramètres de la bibliothèque (des articles de 2026 citent notamment Qwen3.5 4B, Gemma 4 E4B, Phi-4-mini, Qwen3 8B) : ces classements viennent de blogs, ne pas s'y fier, tester.

### A4. Créer le script
Créer `src/spike_llm_capacite.py` avec EXACTEMENT le contenu ci-dessous (exploration hors tickets, bibliothèque standard seulement).

```python
"""Exploration (hors tickets) : un modèle local sait-il reformuler un résultat structuré ?

Données de test synthétiques. Ollama en local uniquement (127.0.0.1).
Usage : python src/spike_llm_capacite.py NOM_DU_MODELE
"""
import json
import re
import sys
import time
import urllib.request

URL = "http://127.0.0.1:11434/api/generate"

INSTRUCTIONS = (
    "Tu rédiges en français. Réponds UNIQUEMENT à partir du résultat JSON fourni. "
    "N'ajoute aucun fait, aucun chiffre et aucun nom absents du JSON. "
    "Recopie les nombres exactement, sans les arrondir. Signale les limites indiquées. "
    "Si la liste des lignes est vide, dis qu'aucun résultat n'est disponible. "
    "Réponds en trois phrases au maximum."
)

CASES = [
    {
        "id": "classement",
        "question": "Quels acheteurs ont attribué le plus de marchés en 2025 ?",
        "result": {
            "rows": [
                {"nom": "Acheteur Alpha", "marches": 1234},
                {"nom": "Acheteur Beta", "marches": 987},
                {"nom": "Acheteur Gamma", "marches": 456},
            ],
            "limites": [],
        },
    },
    {
        "id": "limites",
        "question": "Quel montant total par famille CPV ?",
        "result": {
            "rows": [
                {"famille_cpv": "452", "marches": 5120,
                 "montant_total": "81234567.50", "marches_montant_multivalue": 37}
            ],
            "limites": [
                "37 marchés ont plusieurs montants et sont exclus de l'agrégat de montant."
            ],
        },
    },
    {
        "id": "vide",
        "question": "Quels marchés ont été modifiés en 2031 ?",
        "result": {"rows": [], "limites": []},
    },
]


def nombres(texte):
    """Ensemble des nombres d'un texte, normalisés (séparateurs de milliers retirés)."""
    texte = re.sub(r"(?<=\d)[\u202f\u00a0 ](?=\d{3}(?!\d))", "", texte)
    return {str(float(x.replace(",", "."))) for x in re.findall(r"\d+(?:[.,]\d+)?", texte)}


def generer(model, prompt):
    corps = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0, "seed": 42, "num_predict": 400},
    }).encode()
    requete = urllib.request.Request(
        URL, data=corps, headers={"Content-Type": "application/json"})
    debut = time.perf_counter()
    with urllib.request.urlopen(requete, timeout=900) as reponse:
        data = json.load(reponse)
    return data, time.perf_counter() - debut


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage : python src/spike_llm_capacite.py NOM_DU_MODELE")
    model = sys.argv[1]
    print(f"Modèle : {model}\n")
    for cas in CASES:
        resultat = json.dumps(cas["result"], ensure_ascii=False)
        prompt = (f"{INSTRUCTIONS}\n\nQuestion : {cas['question']}\n"
                  f"Résultat JSON : {resultat}\n\nRéponse :")
        data, duree = generer(model, prompt)
        texte = re.sub(r"<think>.*?</think>", "", data.get("response", ""),
                       flags=re.S).strip()
        jetons = data.get("eval_count", 0)
        secondes = max(data.get("eval_duration", 1) / 1e9, 1e-9)
        chargement = data.get("load_duration", 0) / 1e9
        requis = nombres(json.dumps(cas["result"]["rows"], ensure_ascii=False))
        permis = nombres(resultat + " " + cas["question"])
        trouves = nombres(texte)
        print(f"[{cas['id']}] {duree:.1f} s au total (chargement {chargement:.1f} s), "
              f"{jetons / secondes:.1f} jetons/s")
        print("  chiffres manquants :", sorted(requis - trouves) or "aucun")
        print("  chiffres inventés  :", sorted(trouves - permis) or "aucun")
        print("  réponse :", texte or "(vide)", "\n")
    print("À juger à la main : français correct, aucun fait ajouté, limites signalées.")


if __name__ == "__main__":
    main()
```

Ne pas commiter ce script avant l'approbation du découpage de l'epic 4.

### A5. Lancer le test, par modèle
    uv run --locked python src/spike_llm_capacite.py llama3.1:8b
    ollama ps
    Get-CimInstance Win32_OperatingSystem | Select-Object @{n='RAM_libre_Go';e={[math]::Round($_.FreePhysicalMemory/1MB,1)}}
Répéter pour chaque modèle. Idéalement avec Neo4j démarré (conditions de la démo) : relever la RAM libre avant et pendant. Si la réponse est vide avec un modèle de type Qwen3, c'est qu'il consomme ses jetons à raisonner : le rapporter sans contourner.

### A6. Compte rendu (sans verdict)
Écrire `docs/spike-modele-local-resultats.md` (données synthétiques seulement) avec un tableau par modèle : taille du modèle (`ollama ps`), RAM libre avant/pendant, durée totale et jetons/s par cas, chiffres manquants, chiffres inventés, qualité du français (relue par l'utilisateur), comportement sur le cas vide et le cas avec limites. Demander à l'utilisateur de lire les réponses et de noter ce qu'il juge acceptable. NE PAS conclure « modèle retenu » : cette décision appartient à l'utilisateur après lecture.

## PHASE B : raffinement de l'epic 4 (après la phase A)
1. Lire le fichier de l'epic, `docs/epic4-notes-raffinement.md`, AD-3 à AD-5 et `docs/spike-modele-local-resultats.md`.
2. Utiliser le workflow de raffinement BMAD. Produire un découpage en stories avec critères d'acceptation, en tenant compte des décisions ci-dessus. Première story = test de capacité du modèle (la phase A en est le point de départ, pas un livrable accepté).
3. Lister les décisions restantes pour l'utilisateur.
4. S'arrêter et attendre l'approbation. Ne pas toucher aux tickets avant.

## Compte rendu attendu à chaque session
Dire à l'utilisateur, en français : ce qui a réussi, ce qui a échoué, ce qui attend sa décision. Ajouter trois lignes à la section « Ce qui s'est passé » de `docs/handoff-copilot.md` s'il existe.
