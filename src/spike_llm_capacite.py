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
