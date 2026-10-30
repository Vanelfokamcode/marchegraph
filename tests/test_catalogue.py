from __future__ import annotations

import itertools
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph.catalogue_queries import aggregate, build_cypher
from marchegraph.queries.catalogue import (
    GROUPINGS,
    MEASURES,
    CatalogueQuery,
    CatalogueRefusal,
    validate,
)


def market(uid, **values):
    record = {
        "uid": uid, "annee": 2025, "buyer_id": "B1", "regions": ["53"],
        "cpv_values": ["45233140"], "procedures": ["Procédure adaptée"],
        "natures": ["Travaux"], "amounts": [], "durations": [],
        "buyer_names": ["Ville A"], "holders": [], "modification_count": 0,
    }
    record.update(values)
    return record


class CatalogueValidationTests(unittest.TestCase):
    def test_refused_combinations_explain_why(self) -> None:
        refused = [
            CatalogueQuery("nombre_modifications", "titulaire", year_given=True),
            CatalogueQuery("nombre_modifications", "procedure"),
            CatalogueQuery("duree_moyenne", amount_min=Decimal(1000)),
            CatalogueQuery("nombre_marches", "titulaire"),
            CatalogueQuery("nombre_marches", year=2019),
            CatalogueQuery("nombre_marches", "annee", year_given=True),
            CatalogueQuery("nombre_marches", region_code="99"),
            CatalogueQuery("nombre_marches", cpv_family="45"),
            CatalogueQuery("nombre_marches", limit=101),
            CatalogueQuery("montant_total", amount_min=Decimal(10), amount_max=Decimal(5)),
            CatalogueQuery("inconnue"),
        ]
        for query in refused:
            with self.subTest(query=query):
                with self.assertRaises(CatalogueRefusal) as error:
                    validate(query)
                self.assertTrue(str(error.exception))

    def test_every_other_combination_is_accepted(self) -> None:
        for measure, grouping in itertools.product(MEASURES, GROUPINGS):
            query = CatalogueQuery(measure, grouping, year_given=grouping != "annee")
            refused = (measure == "nombre_modifications"
                       and grouping in ("titulaire", "procedure"))
            with self.subTest(measure=measure, grouping=grouping):
                if refused:
                    with self.assertRaises(CatalogueRefusal):
                        validate(query)
                else:
                    validate(query)

    def test_user_values_never_enter_the_query_text(self) -> None:
        hostile = "voirie' }) DETACH DELETE (n) //"
        query = CatalogueQuery(
            "montant_total", "acheteur", year_given=True, theme=hostile,
            buyer_id=hostile, procedure=hostile, nature=hostile,
            holder_type="SIRET", holder_value=hostile, region_code="53",
        )
        cypher, parameters = build_cypher(query, "source")
        self.assertNotIn("DETACH", cypher)
        self.assertNotIn("voirie", cypher)
        self.assertEqual(parameters["theme"], hostile.strip())
        self.assertNotIn("CREATE", cypher)
        self.assertNotIn("SET ", cypher)


class CatalogueAggregationTests(unittest.TestCase):
    def test_amounts_follow_epic_3_rules(self) -> None:
        records = [
            market("m1", amounts=["100.10"]),
            market("m2", amounts=["200.20"], buyer_id="B2"),
            market("m3", amounts=["5", "7"]),            # valeurs multiples : exclu
            market("m4", amounts=[]),                    # absent : exclu
        ]
        response = aggregate(CatalogueQuery("montant_total", "acheteur",
                                            year_given=True), records)
        values = {row.result.group: row.result for row in response.rows}
        self.assertEqual(values["B1"].value, Decimal("100.10"))
        self.assertEqual(values["B1"].market_count, 3)
        self.assertEqual(values["B1"].measured_market_count, 1)
        self.assertEqual(values["B2"].value, Decimal("200.20"))
        self.assertEqual([row.result.group for row in response.rows], ["B2", "B1"])
        self.assertTrue(any("1 marché(s) à valeurs multiples et 1 sans valeur"
                            in note for note in response.limitations))
        self.assertTrue(all(row.evidence for row in response.rows))

    def test_multi_group_and_unclassified_markets_are_reported(self) -> None:
        records = [
            market("m1", procedures=["A", "B"]),
            market("m2", procedures=[]),
            market("m3", regions=["53", "11"]),
        ]
        by_procedure = aggregate(CatalogueQuery("nombre_marches", "procedure"), records)
        counts = {row.result.group: row.result.value for row in by_procedure.rows}
        self.assertEqual(counts["A"], 1)
        self.assertEqual(counts["B"], 1)
        self.assertTrue(any("plusieurs groupes" in n for n in by_procedure.limitations))
        by_region = aggregate(CatalogueQuery("nombre_marches", "region"), records)
        self.assertEqual({r.result.group: r.result.value for r in by_region.rows},
                         {"53": 2})
        self.assertTrue(any("ne peuvent être rattachés" in n
                            for n in by_region.limitations))

    def test_amount_range_and_cpv_family_filters(self) -> None:
        records = [
            market("m1", amounts=["50"]),
            market("m2", amounts=["500"]),
            market("m3", amounts=["5000"], cpv_values=["30000000"]),
            market("m4", amounts=["1", "2"]),
        ]
        response = aggregate(
            CatalogueQuery("nombre_marches", cpv_family="452",
                           amount_min=Decimal(100), amount_max=Decimal(1000)),
            records,
        )
        self.assertEqual(response.rows[0].result.value, 1)
        self.assertTrue(any("hors tranche" in n for n in response.limitations))

    def test_means_and_limit(self) -> None:
        records = [market(f"m{i}", buyer_id=f"B{i}", durations=[str(i)])
                   for i in range(1, 16)]
        response = aggregate(CatalogueQuery("duree_moyenne", "acheteur",
                                            year_given=True, limit=3), records)
        self.assertEqual([row.result.value for row in response.rows],
                         [Decimal(15), Decimal(14), Decimal(13)])
        self.assertTrue(any("3 premiers groupes sur 15" in n
                            for n in response.limitations))


@unittest.skipUnless(os.environ.get("NEO4J_PASSWORD"),
                     "Set NEO4J_PASSWORD to run the catalogue on local Neo4j fixtures.")
class CatalogueFixtureGraphTests(unittest.TestCase):
    def test_catalogue_on_fixture_graph_matches_reference_questions(self) -> None:
        from neo4j import GraphDatabase

        from marchegraph.evaluation.run import scoped_fixture_graph
        from marchegraph.graph import queries
        from marchegraph.graph.catalogue_queries import run_catalogue
        from marchegraph.graph.neo4j_config import validate_local_neo4j_uri

        uri = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        validate_local_neo4j_uri(uri)
        auth = (os.environ.get("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(uri, auth=auth) as driver, driver.session(
            database=os.environ.get("NEO4J_DATABASE", "neo4j")
        ) as session, scoped_fixture_graph(session):
            buyers = run_catalogue(session, CatalogueQuery(
                "nombre_marches", "acheteur", year_given=True))
            reference_buyers = queries.rank_buyers(session, year=2025)
            self.assertEqual(
                {(r.result.group, int(r.result.value)) for r in buyers.rows},
                {(r.result.buyer_id, r.result.market_count)
                 for r in reference_buyers.rows},
            )
            cpv = queries.aggregate_amounts_and_durations_by_cpv(session, year=2025)
            amounts = run_catalogue(session, CatalogueQuery("montant_total", "famille_cpv"))
            durations = run_catalogue(session, CatalogueQuery("duree_moyenne", "famille_cpv"))
            self.assertEqual(
                {(r.result.group, r.result.value) for r in amounts.rows},
                {(r.result.family_code, r.result.amount_total) for r in cpv.rows},
            )
            self.assertEqual(
                {(r.result.group, r.result.value) for r in durations.rows},
                {(r.result.family_code, r.result.mean_duration_months)
                 for r in cpv.rows},
            )
            for measure, grouping in itertools.product(MEASURES, GROUPINGS):
                query = CatalogueQuery(measure, grouping,
                                       year_given=grouping != "annee")
                with self.subTest(measure=measure, grouping=grouping):
                    try:
                        validate(query)
                    except CatalogueRefusal:
                        continue
                    response = run_catalogue(session, query)
                    self.assertTrue(response.limitations)
                    for row in response.rows:
                        if row.result.measured_market_count:
                            self.assertTrue(row.evidence)


if __name__ == "__main__":
    unittest.main()
