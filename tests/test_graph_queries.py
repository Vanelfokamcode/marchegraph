from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from marchegraph.graph import queries


class FakeResult(list):
    def single(self):
        return self[0] if self else None


class FakeSession:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.calls = []

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeResult(self.results_by_query[query])


class GraphQueryTests(unittest.TestCase):
    def test_buyer_ranking_returns_parameterized_results_and_evidence(self):
        session = FakeSession(
            {
                queries.BUYER_RANKING_QUERY: [
                    {
                        "buyer_id": "buyer-1",
                        "names": ["Acheteur A", "Acheteur A"],
                        "market_count": 2,
                        "market_uids": ["uid-2", "uid-1"],
                    }
                ]
            }
        )

        response = queries.rank_buyers(session, year=2025, limit=5)

        self.assertEqual(response.question_id, 1)
        self.assertEqual(response.rows[0].result.market_count, 2)
        self.assertEqual(response.rows[0].result.names, ("Acheteur A",))
        self.assertEqual(
            response.rows[0].evidence,
            (
                queries.EvidenceReference("uid-1", "A_ACHETEUR", "buyer-1"),
                queries.EvidenceReference("uid-2", "A_ACHETEUR", "buyer-1"),
            ),
        )
        self.assertEqual(
            session.calls[0][1],
            {"source_id": "decp-initial-2024-2025", "year": 2025, "limit": 5},
        )
        self.assertIn("région", response.limitations[0])

    def test_recurring_holders_are_scoped_to_the_requested_buyer(self):
        session = FakeSession(
            {
                queries.HOLDER_RANKING_QUERY: [
                    {
                        "identifier_type": "SIRET",
                        "identifier_value": "00000000000001",
                        "names": ["Entreprise A"],
                        "market_count": 2,
                        "market_uids": ["uid-1", "uid-2"],
                    }
                ]
            }
        )

        response = queries.rank_holders_for_buyer(session, "buyer-7")

        self.assertEqual(response.question_id, 2)
        self.assertEqual(response.rows[0].result.market_count, 2)
        self.assertEqual(session.calls[0][1]["buyer_id"], "buyer-7")
        self.assertEqual(
            {
                (proof.predicate, proof.object_id)
                for proof in response.rows[0].evidence
            },
            {
                ("A_ACHETEUR", "buyer-7"),
                ("A_TITULAIRE", "SIRET:00000000000001"),
            },
        )
        self.assertEqual(len(response.rows[0].evidence), 4)

    def test_nature_and_procedure_summaries_keep_evidence_and_limits_separate(self):
        session = FakeSession(
            {
                queries.NATURE_COUNTS_QUERY: [
                    {
                        "value": "Travaux",
                        "market_count": 2,
                        "market_uids": ["uid-1", "uid-2"],
                    }
                ],
                queries.PROCEDURE_COUNTS_QUERY: [
                    {
                        "value": "Procédure adaptée",
                        "market_count": 1,
                        "market_uids": ["uid-1"],
                    }
                ],
                queries.NATURE_COVERAGE_QUERY: [
                    {
                        "market_count": 10,
                        "missing_count": 1,
                        "multivalued_count": 2,
                    }
                ],
                queries.PROCEDURE_COVERAGE_QUERY: [
                    {
                        "market_count": 10,
                        "missing_count": 3,
                        "multivalued_count": 4,
                    }
                ],
            }
        )

        response = queries.summarize_nature_and_procedures(session)

        self.assertEqual(response.question_id, 5)
        self.assertEqual(
            [row.result.field for row in response.rows],
            ["nature", "procedure"],
        )
        self.assertEqual(response.rows[0].evidence[0].predicate, "nature_values")
        self.assertEqual(response.rows[1].evidence[0].predicate, "procedure_values")
        self.assertIn("2 avec plusieurs valeurs", response.limitations[0])
        self.assertIn("4 avec plusieurs valeurs", response.limitations[1])
        self.assertIn("séparément", response.limitations[2])

    def test_multi_buyer_holders_include_both_relation_proofs(self):
        session = FakeSession(
            {
                queries.MULTI_BUYER_HOLDERS_QUERY: [
                    {
                        "identifier_type": "SIRET",
                        "identifier_value": "00000000000001",
                        "names": ["Entreprise A"],
                        "buyer_ids": ["buyer-2", "buyer-1"],
                        "market_count": 2,
                        "market_buyers": [
                            {"market_uid": "uid-1", "buyer_id": "buyer-1"},
                            {"market_uid": "uid-2", "buyer_id": "buyer-2"},
                        ],
                    }
                ]
            }
        )

        response = queries.find_holders_with_multiple_buyers(session)

        self.assertEqual(response.question_id, 6)
        self.assertEqual(
            response.rows[0].result.buyer_ids,
            ("buyer-1", "buyer-2"),
        )
        self.assertEqual(
            {item.predicate for item in response.rows[0].evidence},
            {"A_TITULAIRE", "A_ACHETEUR"},
        )
        self.assertEqual(len(response.rows[0].evidence), 4)
        self.assertEqual(session.calls[0][1]["limit"], 10)

    def test_query_limits_must_be_positive(self):
        with self.assertRaises(ValueError):
            queries.rank_buyers(FakeSession({}), limit=0)

    def test_cpv_aggregates_count_markets_once_and_report_ambiguous_values(self):
        markets = [
            {
                "uid": "uid-single-with-missing-line",
                "cpv_values": ["45233140"],
                "amount_values": ["100.10"],
                "duration_values": [12],
                "amount_missing": True,
                "duration_missing": True,
            },
            {
                "uid": "uid-multi-holder",
                "holder_ids": ["holder-a", "holder-b"],
                "cpv_values": ["45233140"],
                "amount_values": ["200.00"],
                "duration_values": [24],
                "amount_missing": False,
                "duration_missing": False,
            },
            {
                "uid": "uid-multivalued-amount",
                "cpv_values": ["45233140"],
                "amount_values": ["10.00", "20.00"],
                "duration_values": [6],
                "amount_missing": False,
                "duration_missing": False,
            },
            {
                "uid": "uid-no-amount-or-duration",
                "cpv_values": ["45233140"],
                "amount_values": [],
                "duration_values": [],
                "amount_missing": True,
                "duration_missing": True,
            },
            {
                "uid": "uid-multivalued-duration",
                "cpv_values": ["45233140"],
                "amount_values": ["50.00"],
                "duration_values": [12, 18],
                "amount_missing": False,
                "duration_missing": False,
            },
            {
                "uid": "uid-two-cpv-families",
                "cpv_values": ["45233140", "30000000"],
                "amount_values": ["75.00"],
                "duration_values": [30],
                "amount_missing": False,
                "duration_missing": False,
            },
        ]
        session = FakeSession({queries.AMOUNTS_AND_DURATIONS_QUERY: markets})

        response = queries.aggregate_amounts_and_durations_by_cpv(session)

        self.assertEqual(response.question_id, (3, 8))
        by_family = {row.result.family_code: row for row in response.rows}
        construction = by_family["452"].result
        self.assertEqual(construction.market_count, 6)
        self.assertEqual(construction.amount_total, Decimal("425.10"))
        self.assertEqual(construction.amount_market_count, 4)
        self.assertEqual(construction.amount_missing_value_market_count, 1)
        self.assertEqual(construction.amount_missing_source_market_count, 2)
        self.assertEqual(construction.amount_multivalued_market_count, 1)
        self.assertEqual(construction.mean_duration_months, Decimal("18"))
        self.assertEqual(construction.duration_market_count, 4)
        self.assertEqual(construction.duration_missing_value_market_count, 1)
        self.assertEqual(construction.duration_missing_source_market_count, 2)
        self.assertEqual(construction.duration_multivalued_market_count, 1)
        self.assertEqual(construction.multiple_cpv_market_count, 1)
        self.assertEqual(by_family["300"].result.amount_total, Decimal("75.00"))
        self.assertTrue(by_family["300"].evidence_complete)
        self.assertEqual(len(markets[1]["holder_ids"]), 2)
        self.assertNotIn("A_TITULAIRE", queries.AMOUNTS_AND_DURATIONS_QUERY)
        self.assertIn("accord-cadre", " ".join(response.limitations))
        self.assertIn("plusieurs familles CPV", " ".join(response.limitations))

    def test_cpv_aggregates_bound_evidence_without_truncating_the_totals(self):
        markets = [
            {
                "uid": f"uid-{index:02}",
                "cpv_values": ["45233140"],
                "amount_values": ["1.00"],
                "duration_values": [1],
                "amount_missing": False,
                "duration_missing": False,
            }
            for index in range(
                queries.MAX_AGGREGATE_EVIDENCE_MARKETS + 1
            )
        ]
        session = FakeSession({queries.AMOUNTS_AND_DURATIONS_QUERY: markets})

        response = queries.aggregate_amounts_and_durations_by_cpv(session)

        row = response.rows[0]
        self.assertEqual(row.result.market_count, 26)
        self.assertEqual(row.result.amount_total, Decimal("26.00"))
        self.assertFalse(row.evidence_complete)
        self.assertEqual(len(row.evidence), 100)
        self.assertIn("preuves détaillées", " ".join(response.limitations))

    def test_cpv_aggregates_reject_non_numeric_source_values(self):
        session = FakeSession(
            {
                queries.AMOUNTS_AND_DURATIONS_QUERY: [
                    {
                        "uid": "uid-invalid-amount",
                        "cpv_values": ["45233140"],
                        "amount_values": ["not-a-number"],
                        "duration_values": [1],
                        "amount_missing": False,
                        "duration_missing": False,
                    }
                ]
            }
        )

        with self.assertRaisesRegex(
            queries.GraphQueryDataError,
            "montant du marché uid-invalid-amount n'est pas numérique",
        ):
            queries.aggregate_amounts_and_durations_by_cpv(session)


if __name__ == "__main__":
    unittest.main()
