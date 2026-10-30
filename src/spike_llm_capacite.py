"""Exploration (hors tickets) : un modèle local sait-il reformuler un résultat structuré ?

Données de test synthétiques. Ollama en local uniquement (127.0.0.1).
Usage : python src/spike_llm_capacite.py NOM_DU_MODELE [--dix-questions]
"""
import json
import re
import sys
import time
import urllib.request
from dataclasses import asdict, is_dataclass
from decimal import Decimal

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


def _simple(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        obj = asdict(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _simple(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_simple(v) for v in obj]
    return obj


def _cas(ident, question, rows, limites=()):
    return {"id": ident, "question": question,
            "result": {"rows": _simple(list(rows)), "limites": list(limites)}}


def cas_dix_questions():
    """Un cas synthétique par question de référence, aux formes des contrats réels."""
    from marchegraph.graph import contracts as c

    cpv = c.CpvFamilyAggregate(
        family_code="452", market_count=5120, amount_total=Decimal("81234567.50"),
        amount_market_count=5000, amount_missing_value_market_count=83,
        amount_missing_source_market_count=12, amount_multivalued_market_count=37,
        mean_duration_months=Decimal("14.5"), duration_market_count=4990,
        duration_missing_value_market_count=100,
        duration_missing_source_market_count=5,
        duration_multivalued_market_count=30, multiple_cpv_market_count=4)
    limites_cpv = [
        "Les montants sont des montants déclarés, pas des paiements.",
        "Les montants et durées multivalués sont exclus des agrégats.",
    ]
    return [
        _cas("q1", "Quels acheteurs ont attribué le plus de marchés en 2025 ?", [
            c.BuyerRanking("00000000000011", ("Acheteur Alpha",), 1234),
            c.BuyerRanking("00000000000012", ("Acheteur Beta",), 987),
        ], ["Le classement couvre tout le territoire national."]),
        _cas("q2", "Quels titulaires reviennent le plus chez l'acheteur "
             "00000000000011 en 2025 ?", [
            c.HolderRanking("SIRET", "00000000000021", ("Titulaire Un",), 42),
            c.HolderRanking("SIRET", "00000000000022",
                            ("Titulaire Deux", "TITULAIRE DEUX SAS"), 17),
        ]),
        _cas("q3", "Quel montant total par famille CPV en 2025 ?", [cpv], limites_cpv),
        _cas("q4", "Quels marchés ont été modifiés en 2025 ?", [
            c.ModificationHistorySummary(
                year=2025, modified_market_count=2, total_version_count=6,
                linked_version_count=4, unlinked_version_count=2,
                modified_markets=(c.ModifiedMarketCount("uid-synth-1", (1, 2, 3)),
                                  c.ModifiedMarketCount("uid-synth-2", (1,))),
                unlinked_samples=(c.UnlinkedModification("uid-synth-9", 1),
                                  c.UnlinkedModification("uid-synth-9", 2))),
        ], ["2 versions n'ont pas de marché initial dans le snapshot."]),
        _cas("q5", "Quelles procédures et natures de marché sont utilisées en 2025 ?", [
            c.CategoryMarketCount("nature", "Marché", 900),
            c.CategoryMarketCount("procedure", "Appel d'offres ouvert", 400),
            c.CategoryMarketCount("procedure", "Procédure adaptée", 500),
        ], ["Nature et procédure sont résumées séparément, sans paires."]),
        _cas("q6", "Quels titulaires travaillent avec plusieurs acheteurs en 2025 ?", [
            c.MultiBuyerHolder("SIRET", "00000000000031", ("Titulaire Trois",),
                               ("00000000000011", "00000000000012"), 6),
        ]),
        _cas("q7", "Quels marchés concernent la voirie dans la région 84 ?", [
            c.ThemedMarket("uid-synth-5", "84", ("Travaux de voirie communale",)),
        ], ["3 marchés sans région d'acheteur unique sont exclus."]),
        _cas("q8", "Quelle durée moyenne par famille CPV en 2025 ?", [cpv], limites_cpv),
        _cas("q9", "Quels fournisseurs ont plusieurs écritures de leur nom ?", [
            c.HolderNameVariants("SIRET", "00000000000041",
                                 ("Société Exemple", "SOCIETE EXEMPLE SAS"), 12),
        ], ["Les variantes sont regroupées par identifiant, jamais par nom seul."]),
        _cas("q10", "Quelles données sont manquantes ou incohérentes ?", [
            c.DataQualityIssue("Marche", "montant_multivalue", 37),
            c.DataQualityIssue("Marche", "region_acheteur_manquante", 25),
        ], ["Une valeur multiple n'est pas qualifiée d'erreur."]),
        CASES[2],
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
    args = sys.argv[1:]
    dix_questions = "--dix-questions" in args
    args = [a for a in args if a != "--dix-questions"]
    if len(args) != 1:
        sys.exit("Usage : python src/spike_llm_capacite.py NOM_DU_MODELE "
                 "[--dix-questions]")
    model = args[0]
    cases = cas_dix_questions() if dix_questions else CASES
    print(f"Modèle : {model}\n")
    for cas in cases:
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
