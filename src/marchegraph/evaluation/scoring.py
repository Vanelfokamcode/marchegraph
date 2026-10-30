"""Notation automatique des réponses ; l'utilisateur valide ensuite chaque libellé."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from marchegraph.graph.contracts import QueryResponse
from marchegraph.queries.formulation import _normalize, _numbers

# Faits essentiels de chaque ligne de résultat, par question de référence.
CORE_FACTS: dict[int, Callable] = {
    0: lambda r: (r.group, r.value, r.market_count),
    1: lambda r: (r.buyer_id, r.market_count),
    2: lambda r: (r.identifier_value, r.market_count),
    3: lambda r: (r.family_code, r.market_count, r.amount_total),
    4: lambda r: (r.modified_market_count, r.total_version_count),
    5: lambda r: (r.field, r.value, r.market_count),
    6: lambda r: (r.identifier_value, r.market_count),
    7: lambda r: (r.uid,),
    8: lambda r: (r.family_code, r.mean_duration_months),
    9: lambda r: (r.identifier_value, len(r.names)),
    10: lambda r: (r.affected_record_count,),
}

_ABSTENTION = re.compile(
    r"je ne (?:sais|peux)|je n'ai pas|impossible de|ne dispose pas|"
    r"pas (?:d'|de |acces)(?:acces|information|donnee)|"
    r"aucune (?:information|donnee)|pas en mesure"
)


@dataclass(frozen=True)
class Score:
    label: str
    invented: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def _value(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, (float, Decimal)):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    return value


def normalize_facts(facts) -> list[tuple]:
    return sorted((tuple(_value(item) for item in fact) for fact in facts), key=repr)


def core_facts(question_id: int, response: QueryResponse) -> list[tuple]:
    extract = CORE_FACTS[question_id]
    return normalize_facts(extract(row.result) for row in response.rows)


def key_numbers(facts: list[tuple]) -> set[Decimal]:
    return {item for fact in facts for item in fact if isinstance(item, Decimal)}


def score_structured(facts: list[tuple] | None, reference: list[tuple]) -> Score:
    """Baseline SQL : faits essentiels identiques à la référence, ou non."""
    if facts is None:
        return Score("abstention à tort")
    if facts == reference:
        return Score("correct")
    expected, found = set(reference), set(facts)
    return Score(
        "différent",
        invented=tuple(sorted(map(repr, found - expected))),
        missing=tuple(sorted(map(repr, expected - found))),
    )


def is_abstention(text: str) -> bool:
    return bool(_ABSTENTION.search(_normalize(text))) or not text.strip()


def score_text(
    text: str,
    question: str,
    reference: list[tuple] | None,
    allowed_text: str = "",
) -> Score:
    """Réponse en texte libre. `reference` vaut None si l'abstention est attendue.

    `allowed_text` contient toutes les valeurs du résultat de référence : un
    nombre qui n'y figure pas, ni dans la question, est compté comme inventé.
    """
    found = _numbers(text)
    if reference is None:
        if is_abstention(text):
            return Score("abstention correcte")
        invented = found - _numbers(question)
        return Score("réponse au lieu d'abstention",
                     invented=tuple(sorted(map(str, invented))))
    if is_abstention(text):
        return Score("abstention à tort")
    allowed = _numbers(allowed_text) | _numbers(question) | key_numbers(reference)
    invented = tuple(sorted(map(str, found - allowed)))
    missing = tuple(sorted(map(str, key_numbers(reference) - found)))
    if invented:
        return Score("hallucination", invented, missing)
    if missing:
        return Score("incomplet", invented, missing)
    return Score("correct")
