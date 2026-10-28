from __future__ import annotations

from neo4j import Driver, Session

from marchegraph.graph.contracts import DemoBuyerRanking as BuyerRanking
from marchegraph.graph.demo_data import (
    DEMO_DATA,
    DEMO_ID,
    Buyer,
    DemoData,
    Holder,
    Market,
    Modification,
)


def load_demo_data(session: Session, data: DemoData = DEMO_DATA) -> None:
    with session.begin_transaction() as transaction:
        transaction.run(
            """
            MATCH (node {demo_id: $demo_id})
            DETACH DELETE node
            """,
            demo_id=DEMO_ID,
        ).consume()

        for buyer in data.buyers:
            transaction.run(
                """
                CREATE (:Acheteur {
                    id: $identifier,
                    nom: $name,
                    demo_id: $demo_id
                })
                """,
                identifier=buyer.identifier,
                name=buyer.name,
                demo_id=DEMO_ID,
            ).consume()

        for holder in data.holders:
            transaction.run(
                """
                CREATE (:Titulaire {
                    id: $identifier,
                    nom: $name,
                    identifier_type: $identifier_type,
                    identifier_value: $identifier_value,
                    demo_id: $demo_id
                })
                """,
                identifier=holder.identifier,
                name=holder.name,
                identifier_type=holder.identifier_type,
                identifier_value=holder.identifier_value,
                demo_id=DEMO_ID,
            ).consume()

        for market in data.markets:
            transaction.run(
                """
                MATCH (buyer:Acheteur {id: $buyer_id, demo_id: $demo_id})
                CREATE (market:Marche {
                    uid: $uid,
                    year: $year,
                    objet: $subject,
                    montantHT: $amount_ht,
                    cpv_code: $cpv_code,
                    demo_id: $demo_id
                })
                CREATE (market)-[:A_ACHETEUR]->(buyer)
                """,
                buyer_id=market.buyer_id,
                uid=market.uid,
                year=market.year,
                subject=market.subject,
                amount_ht=market.amount_ht,
                cpv_code=market.cpv_code,
                demo_id=DEMO_ID,
            ).consume()

            for holder_id in market.holder_ids:
                transaction.run(
                    """
                    MATCH (market:Marche {uid: $uid, demo_id: $demo_id})
                    MATCH (holder:Titulaire {id: $holder_id, demo_id: $demo_id})
                    CREATE (market)-[:A_TITULAIRE]->(holder)
                    """,
                    uid=market.uid,
                    holder_id=holder_id,
                    demo_id=DEMO_ID,
                ).consume()

        for modification in data.modifications:
            transaction.run(
                """
                MATCH (market:Marche {uid: $market_uid, demo_id: $demo_id})
                CREATE (version:Modification {
                    id: $identifier,
                    objet: $subject,
                    demo_id: $demo_id
                })
                CREATE (version)-[:MODIFICATION_DE]->(market)
                """,
                market_uid=modification.market_uid,
                identifier=modification.identifier,
                subject=modification.subject,
                demo_id=DEMO_ID,
            ).consume()

        transaction.commit()


def top_buyer_with_evidence(session: Session) -> BuyerRanking | None:
    record = session.run(
        """
        MATCH (market:Marche {demo_id: $demo_id})-[:A_ACHETEUR]->(buyer:Acheteur)
        RETURN buyer.id AS buyer_id,
               buyer.nom AS buyer_name,
               count(DISTINCT market.uid) AS market_count,
               collect(DISTINCT market.uid) AS market_uids
        ORDER BY market_count DESC, buyer.id ASC
        LIMIT 1
        """,
        demo_id=DEMO_ID,
    ).single()
    if record is None:
        return None
    return BuyerRanking(
        buyer_id=record["buyer_id"],
        buyer_name=record["buyer_name"],
        market_count=record["market_count"],
        market_uids=tuple(record["market_uids"]),
    )


def read_demo_data(session: Session) -> DemoData:
    records = session.run(
        """
        MATCH (market:Marche {demo_id: $demo_id})
        OPTIONAL MATCH (market)-[:A_ACHETEUR]->(buyer:Acheteur)
        OPTIONAL MATCH (market)-[:A_TITULAIRE]->(holder:Titulaire)
        WITH market, buyer, collect(DISTINCT holder) AS holders
        OPTIONAL MATCH (version:Modification {demo_id: $demo_id})
          -[:MODIFICATION_DE]->(market)
        RETURN properties(market) AS market,
               properties(buyer) AS buyer,
               [holder IN holders WHERE holder IS NOT NULL |
                 properties(holder)] AS holders,
               collect(DISTINCT properties(version)) AS modifications
        ORDER BY market.uid
        """,
        demo_id=DEMO_ID,
    )

    buyers = {}
    holders = {}
    markets = []
    modifications: dict[str, object] = {}
    for record in records:
        market = record["market"]
        buyer = record["buyer"]
        if buyer is not None:
            buyers[buyer["id"]] = buyer
        market_holders = [holder for holder in record["holders"] if holder]
        for holder in market_holders:
            holders[holder["id"]] = holder
        markets.append(
            {
                "uid": market["uid"],
                "buyer_id": buyer["id"] if buyer else "",
                "holder_ids": tuple(holder["id"] for holder in market_holders),
                "year": market["year"],
                "subject": market["objet"],
                "amount_ht": market["montantHT"],
                "cpv_code": market["cpv_code"],
            }
        )
        for version in record["modifications"]:
            if version is not None:
                modifications[version["id"]] = {
                    "identifier": version["id"],
                    "market_uid": market["uid"],
                    "subject": version["objet"],
                }

    return DemoData(
        buyers=tuple(
            Buyer(identifier=item["id"], name=item["nom"])
            for item in buyers.values()
        ),
        holders=tuple(
            Holder(
                identifier=item["id"],
                name=item["nom"],
                identifier_type=item["identifier_type"],
                identifier_value=item["identifier_value"],
            )
            for item in holders.values()
        ),
        markets=tuple(Market(**item) for item in markets),
        modifications=tuple(
            Modification(**item) for item in modifications.values()
        ),
    )


def assert_connection(driver: Driver) -> None:
    driver.verify_connectivity()
