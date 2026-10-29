"""Formulation en français d'un résultat structuré, avec contrôle et abstention.

Le modèle ne reçoit que les valeurs du résultat et ses limites, jamais les
références de preuve, qui restent celles de la requête (AD-3).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from typing import Callable

from marchegraph.graph.contracts import QueryResponse

Generate = Callable[[str], str]

MAX_MODEL_ROWS = 10

INSTRUCTIONS = (
    "Tu rédiges en français, en phrases, sans JSON ni code. "
    "Réponds UNIQUEMENT à partir du résultat JSON fourni. "
    "N'ajoute aucun fait, aucun chiffre et aucun nom absents du JSON. "
    "Recopie les nombres exactement, en chiffres, sans les arrondir. "
    "Signale les limites indiquées. Si toutes les lignes ne sont pas fournies, "
    "dis que tu présentes les premières. Ne dis jamais qu'aucun résultat n'est "
    "disponible si la liste des lignes contient des éléments. "
    "Réponds en trois phrases au maximum."
)

NUMBER_WORDS = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13,
    "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20, "trente": 30,
    "quarante": 40, "cinquante": 50, "soixante": 60, "cent": 100, "mille": 1000,
}

_FALSE_ABSENCE = re.compile(
    r"\baucune?\s+(?:resultat|donnee|information|element|ligne|marche|"
    r"fournisseur|titulaire|acheteur|procedure)s?\b"
    r"|\bpas de (?:resultat|donnee)s?\b"
    r"|\bliste\b[^.]*\bvide\b"
)


@dataclass(frozen=True)
class Formulation:
    text: str | None
    source: str  # "modele", "gabarit" ou "abstention"
    problems: tuple[str, ...] = ()


def _plain(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        obj = asdict(obj)
    if isinstance(obj, Decimal):
        # Le modèle recopie mal les longues décimales : 2 chiffres suffisent à la phrase.
        if obj.as_tuple().exponent < -2:
            obj = obj.quantize(Decimal("0.01"))
        return str(obj)
    if isinstance(obj, dict):
        return {key: _plain(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(value) for value in obj]
    return obj


def payload(response: QueryResponse) -> dict:
    """Valeurs et limites du résultat, sans les références de preuve."""
    rows = response.rows[:MAX_MODEL_ROWS]
    return {
        "rows": [_plain(row.result) for row in rows],
        "lignes_fournies": len(rows),
        "lignes_total": len(response.rows),
        "limites": list(response.limitations),
    }


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _numbers(text: str) -> set[Decimal]:
    text = re.sub(r"(?<=\d)[\u202f\u00a0 ](?=\d{3}(?!\d))", "", text)
    return {Decimal(value.replace(",", "."))
            for value in re.findall(r"\d+(?:[.,]\d+)?", text)}


def _list_lengths(value) -> set[Decimal]:
    lengths: set[Decimal] = set()
    if isinstance(value, dict):
        for item in value.values():
            lengths |= _list_lengths(item)
    elif isinstance(value, list):
        lengths.add(Decimal(len(value)))
        for item in value:
            lengths |= _list_lengths(item)
    return lengths


def check(text: str, data: dict, question: str) -> tuple[str, ...]:
    """Problèmes détectés dans un texte du modèle ; vide si le texte est accepté."""
    if not text.strip():
        return ("réponse vide",)
    if "```" in text or text.lstrip()[:1] in "{[":
        return ("réponse non rédigée (JSON ou code)",)
    allowed = (
        _numbers(json.dumps(data, ensure_ascii=False))
        | _numbers(question)
        | _list_lengths(data)
    )
    problems = [
        f"chiffre absent du résultat : {value}"
        for value in sorted(_numbers(text) - allowed)
    ]
    normalized = _normalize(text)
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", normalized) and Decimal(value) not in allowed:
            problems.append(f"nombre en lettres absent du résultat : {word}")
    if data["rows"] and _FALSE_ABSENCE.search(normalized):
        problems.append("absence de résultat affirmée alors que des lignes existent")
    return tuple(problems)


def template(label: str, response: QueryResponse) -> str:
    count = len(response.rows)
    if count == 0:
        return f"{label} : aucun résultat n'est disponible pour cette question."
    return f"{label} : {count} ligne(s) de résultat, détaillées ci-dessous."


def formulate(
    question: str, label: str, response: QueryResponse, generate: Generate | None
) -> Formulation:
    """Gabarit sans modèle ou sans ligne ; sinon texte du modèle contrôlé, ou abstention."""
    if generate is None or not response.rows:
        return Formulation(template(label, response), "gabarit")
    data = payload(response)
    prompt = (
        f"{INSTRUCTIONS}\n\nQuestion : {question}\n"
        f"Résultat JSON : {json.dumps(data, ensure_ascii=False)}\n\nRéponse :"
    )
    try:
        text = generate(prompt)
    except Exception as error:  # modèle indisponible : on ne formule pas
        return Formulation(None, "abstention", (f"modèle indisponible : {error}",))
    problems = check(text, data, question)
    if problems:
        return Formulation(None, "abstention", problems)
    return Formulation(text, "modele")
