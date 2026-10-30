"""Reconnaissance déterministe des dix questions de référence.

Sans dépendance à Neo4j ni à l'interface. Toute question non reconnue, ambiguë
ou hors périmètre renvoie None : l'appelant doit alors s'abstenir.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Mapping

SUPPORTED_YEARS = (2024, 2025)
DEFAULT_YEAR = 2025

# Codes INSEE des régions d'acheteur présents dans le jeu préparé.
REGIONS: dict[str, tuple[str, ...]] = {
    "01": ("guadeloupe",),
    "02": ("martinique",),
    "03": ("guyane",),
    "04": ("la reunion", "reunion"),
    "06": ("mayotte",),
    "11": ("ile de france",),
    "24": ("centre val de loire",),
    "27": ("bourgogne franche comte",),
    "28": ("normandie",),
    "32": ("hauts de france",),
    "44": ("grand est",),
    "52": ("pays de la loire",),
    "53": ("bretagne",),
    "75": ("nouvelle aquitaine",),
    "76": ("occitanie",),
    "84": ("auvergne rhone alpes",),
    "93": ("provence alpes cote d'azur", "paca"),
    "94": ("corse",),
    "975": ("saint pierre et miquelon",),
    "977": ("saint barthelemy",),
    "978": ("saint martin",),
    "986": ("wallis et futuna",),
    "987": ("polynesie francaise",),
    "988": ("nouvelle caledonie",),
}

LABELS: dict[int | tuple[int, ...], str] = {
    1: "Classement des acheteurs",
    2: "Titulaires récurrents d'un acheteur",
    3: "Montant total par famille CPV",
    4: "Historique des modifications",
    5: "Natures et procédures",
    6: "Titulaires travaillant avec plusieurs acheteurs",
    7: "Marchés d'un thème dans une région",
    8: "Durée moyenne par famille CPV",
    9: "Variantes de noms de titulaires",
    10: "Données manquantes ou incohérentes",
    (3, 8): "Montant et durée par famille CPV",
}

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_BUYER_ID = re.compile(r"\b\d{14}\b")
_REGION_CODE = re.compile(r"\bregion\s+(?:n[o°]\s*)?(\d{2,3})\b")
_THEME_TRIGGER = re.compile(
    r"\b(?:theme|concernent|concernant|portent sur|portant sur|lies a|lie a|"
    r"relatifs a|relatif a|en lien avec|mentionnant)\b"
)
_THEME_TAIL = re.compile(
    r"(?:\s+(?:dans|en|pour|de|sur|attribues?|ont ete|ete))*"
    r"(?:\s+(?:la|le|l'))?(?:\s+region)?\s*$"
)
_THEME_HEAD = re.compile(r"\s*(?:(?:de la|du|des|de|le|la|les)\s+|[dl]')*")
_HOLDER_WORDS = ("titulaire", "fournisseur", "prestataire", "entreprise", "societe")
_BUYER_MENTION = re.compile(
    r"\bchez\s+(?:l'acheteur\s+|l'organisme\s+)?(?:(?:la|le|les)\s+|l')?"
    r"(?P<mention>.+?)\s*(?:\b(?:en|pour|sur)\s+(?:19|20)\d{2}\b)?[\s?.!]*$"
)
_GENERIC_MENTION = frozenset({"un", "une", "acheteur", "donne", "donnee", "certain",
                              "quelconque", "ce", "cet", "cette", "chaque"})


@dataclass(frozen=True)
class Interpretation:
    question_id: int | tuple[int, ...]
    label: str
    params: Mapping[str, str | int] = field(default_factory=dict)


def _normalize(text: str) -> tuple[str, list[int]]:
    """Minuscules sans accents ni tirets, avec l'index d'origine de chaque caractère."""
    chars: list[str] = []
    origin: list[int] = []
    for position, char in enumerate(text):
        if char in "’‘`":
            char = "'"
        for part in unicodedata.normalize("NFKD", char):
            if unicodedata.combining(part):
                continue
            for lowered in part.lower():
                chars.append(" " if lowered == "-" else lowered)
                origin.append(position)
    return "".join(chars), origin


def _contains(text: str, *words: str) -> bool:
    return any(word in text for word in words)


def _find_regions(text: str) -> list[tuple[str, int]]:
    """Codes de région cités, avec la position de début de chaque mention."""
    found: list[tuple[str, int]] = []
    for match in _REGION_CODE.finditer(text):
        found.append((match.group(1), match.start()))
    for code, names in REGIONS.items():
        for name in sorted(names, key=len, reverse=True):
            for match in re.finditer(rf"\b{re.escape(name)}\b", text):
                found.append((code, match.start()))
    return found


def _theme(text: str, origin: list[int], original: str, region_start: int) -> str:
    trigger = None
    for match in _THEME_TRIGGER.finditer(text, 0, region_start):
        trigger = match
    if trigger is None:
        return ""
    start, end = trigger.end(), region_start
    head = _THEME_HEAD.match(text, start, end)
    if head:
        start = head.end()
    tail = _THEME_TAIL.search(text[start:end])
    if tail:
        end = start + tail.start()
    if end <= start:
        return ""
    return original[origin[start]:origin[end - 1] + 1].strip(" ,;:'\"")


def _buyer_mention(text: str, origin: list[int], original: str) -> tuple[str, int] | None:
    """Nom d'acheteur cité après « chez », avec sa position ; None s'il est générique."""
    match = _BUYER_MENTION.search(text)
    if match is None:
        return None
    words = set(re.split(r"[^a-z0-9]+", match.group("mention"))) - {""}
    if not words or words <= _GENERIC_MENTION:
        return None
    start, end = match.span("mention")
    return original[origin[start]:origin[end - 1] + 1].strip(" ,;:'\""), start


def interpret(question: str) -> Interpretation | None:
    """Associe une question à une question de référence, ou renvoie None."""
    text, origin = _normalize(question)

    years = {int(year) for year in _YEAR.findall(text)}
    if len(years) > 1 or (years and not years <= set(SUPPORTED_YEARS)):
        return None
    year = years.pop() if years else DEFAULT_YEAR
    year_given = bool(_YEAR.search(text))

    regions = _find_regions(text)
    if _contains(text, *_HOLDER_WORDS) and "chez" in text and not _BUYER_ID.search(text):
        mention = _buyer_mention(text, origin, question)
        # Une région hors du nom de l'acheteur serait un filtre que Q2 n'applique pas.
        if mention is None or any(start < mention[1] for _, start in regions):
            return None
        return _make(2, buyer_name=mention[0], year=year)

    if regions:
        codes = {code for code, _ in regions}
        if len(codes) != 1 or not codes <= REGIONS.keys():
            return None
        region_start = min(start for _, start in regions)
        theme = _theme(text, origin, question, region_start)
        if not theme:
            return None
        return _make(7, theme=theme, region_code=codes.pop(), year=year)

    if _contains(text, "manquant", "incoherent", "anomalie", "qualite des donnees"):
        return None if year_given else _make(10)
    if _contains(text, "ecritures", "variante", "graphie", "orthographe",
                 "plusieurs noms"):
        return None if year_given else _make(9)
    if _contains(text, "modifi", "avenant"):
        return _make(4, year=year)
    if _contains(text, "plusieurs acheteurs", "acheteurs differents",
                 "differents acheteurs"):
        return _make(6, year=year)
    if _contains(text, *_HOLDER_WORDS):
        buyer = _BUYER_ID.search(text)
        if buyer is None:
            return None
        return _make(2, buyer_id=buyer.group(0), year=year)
    if _contains(text, "cpv", "famille"):
        amount = _contains(text, "montant", "somme")
        duration = _contains(text, "duree")
        if amount and duration:
            return _make((3, 8), year=year)
        if amount:
            return _make(3, year=year)
        if duration:
            return _make(8, year=year)
        return None
    if _contains(text, "procedure") or (
        _contains(text, "nature") and _contains(text, "marche")
    ):
        return _make(5, year=year)
    if (
        _contains(text, "acheteur")
        and _contains(text, "le plus", "classement", "principaux", "premiers")
        and _contains(text, "marche", "attribu")
    ):
        return _make(1, year=year)
    return None


def _make(question_id: int | tuple[int, ...], **params: str | int) -> Interpretation:
    return Interpretation(question_id, LABELS[question_id], params)
