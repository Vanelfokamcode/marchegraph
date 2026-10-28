from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Buyer:
    identifier: str
    name: str


@dataclass(frozen=True)
class Holder:
    identifier: str
    name: str
    identifier_type: str
    identifier_value: str


@dataclass(frozen=True)
class Market:
    uid: str
    buyer_id: str
    holder_ids: tuple[str, ...]
    year: int
    subject: str
    amount_ht: str
    cpv_code: str


@dataclass(frozen=True)
class Modification:
    identifier: str
    market_uid: str
    subject: str


@dataclass(frozen=True)
class DemoData:
    buyers: tuple[Buyer, ...]
    holders: tuple[Holder, ...]
    markets: tuple[Market, ...]
    modifications: tuple[Modification, ...]


DEMO_ID = "story-3-1-synthetic-demo"

DEMO_DATA = DemoData(
    buyers=(Buyer(identifier="buyer-ville-demo", name="Ville Démonstration"),),
    holders=(
        Holder(
            identifier="holder-demo-1",
            name="Entreprise Démonstration A",
            identifier_type="SIRET",
            identifier_value="00000000000001",
        ),
        Holder(
            identifier="holder-demo-2",
            name="Entreprise Démonstration B",
            identifier_type="SIRET",
            identifier_value="00000000000002",
        ),
    ),
    markets=(
        Market(
            uid="demo-marche-2025-001",
            buyer_id="buyer-ville-demo",
            holder_ids=("holder-demo-1", "holder-demo-2"),
            year=2025,
            subject="Travaux de voirie (données synthétiques)",
            amount_ht="250000.00",
            cpv_code="45233140",
        ),
    ),
    modifications=(
        Modification(
            identifier="demo-marche-2025-001-modification-1",
            market_uid="demo-marche-2025-001",
            subject="Modification synthétique après attribution",
        ),
    ),
)
