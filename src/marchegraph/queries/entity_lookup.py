"""Décision de résolution d'une entité citée par son nom (module pur).

La recherche plein texte ne fournit que des candidats ; ce module décide
s'il faut en retenir un, demander à l'utilisateur de choisir, ou s'abstenir.
Un score de pertinence n'est jamais présenté comme un fait.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

STOPWORDS = frozenset({"a", "au", "aux", "d", "de", "des", "du", "en", "et", "l",
                       "la", "le", "les", "pour", "sur"})
# Le premier candidat est retenu s'il dépasse le second d'au moins ce facteur.
DOMINANCE = 1.5
MAX_OPTIONS = 5
FUZZY_MIN_LENGTH = 5
_LUCENE_SPECIAL = re.compile(r'([+\-!(){}\[\]^"~*?:\\/&|])')


@dataclass(frozen=True)
class Candidate:
    kind: str
    identifier: str
    names: tuple[str, ...]
    score: float
    market_count: int
    # Plus d'un : regroupement des établissements (SIRET) d'un même organisme (SIREN).
    establishments: int = 1


@dataclass(frozen=True)
class Resolution:
    status: str  # "resolved", "choose" ou "not_found"
    chosen: Candidate | None = None
    options: tuple[Candidate, ...] = ()


def tokens(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return [t for t in re.split(r"[^a-z0-9]+", plain) if t and t not in STOPWORDS]


def lucene_query(mention: str) -> str | None:
    """Requête Lucene sûre : chaque mot échappé, tous obligatoires, tolérance aux fautes."""
    terms = []
    for token in tokens(mention):
        escaped = _LUCENE_SPECIAL.sub(r"\\\1", token)
        terms.append(f"{escaped}~1" if len(token) >= FUZZY_MIN_LENGTH else escaped)
    return " AND ".join(terms) if terms else None


def decide(mention: str, candidates: list[Candidate]) -> Resolution:
    if not candidates:
        return Resolution("not_found")
    ranked = sorted(candidates, key=lambda c: (-c.score, c.identifier))
    wanted = tokens(mention)
    exact = [c for c in ranked if any(tokens(name) == wanted for name in c.names)]
    if len(exact) == 1:
        return Resolution("resolved", chosen=exact[0])
    if len(ranked) == 1 or ranked[0].score >= DOMINANCE * ranked[1].score:
        return Resolution("resolved", chosen=ranked[0])
    return Resolution("choose", options=by_market_count(ranked[:MAX_OPTIONS]))


def by_market_count(options) -> tuple[Candidate, ...]:
    """Ordre d'affichage : les entités les plus actives d'abord, le score départage."""
    return tuple(sorted(options, key=lambda c: (-c.market_count, -c.score, c.identifier)))


def siren_of(identifier: str) -> str | None:
    return identifier[:9] if len(identifier) == 14 and identifier.isdigit() else None


def shared_sirens(options) -> list[str]:
    """SIREN portés par au moins deux options : ils méritent une option regroupée."""
    counts = Counter(siren_of(o.identifier) for o in options if o.kind == "acheteur")
    return sorted(s for s, n in counts.items() if s and n >= 2)


def organisation(siren: str, members, market_count: int, establishments: int) -> Candidate:
    main = max(members, key=lambda c: (c.market_count, c.identifier))
    return Candidate(main.kind, siren, main.names, max(c.score for c in members),
                     market_count, establishments)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


def option_label(option: Candidate) -> str:
    name = ", ".join(option.names[:2]) or option.identifier
    markets = _plural(option.market_count, "marché")
    if option.establishments > 1:
        return (f"{name} : tout l'organisme, {_plural(option.establishments, 'établissement')}"
                f" (SIREN {option.identifier}, {markets})")
    return f"{name} ({option.identifier}, {markets})"
