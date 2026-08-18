import unittest

from contractgraph_qa.astra_opportunity import (
    AstraOpportunityError,
    evaluate_opportunity,
    source_set_digest,
)


SOURCES = [
    {
        "source_id": "official-product",
        "locator": "https://example.com/product",
        "claim": "agent can initiate a financial-state transition",
    }
]


def base_payload():
    return {
        "company_id": "example",
        "initial_product_generation": "2026-08-18-a",
        "final_product_generation": "2026-08-18-a",
        "sources": SOURCES,
        "checks": {
            "identity": "PASS",
            "execution_surface": "PASS",
            "evidence_freshness": "PASS",
            "reachability": "PASS",
        },
        "opportunity_score": 9.7,
        "verification_debt": "HIGH",
        "competing_hypothesis": "controls may already close the boundary",
        "next_best_evidence": "verify retry identity at execution time",
    }


class AstraOpportunityTests(unittest.TestCase):
    def test_all_required_checks_pass_yields_outreach_advisory(self):
        result = evaluate_opportunity(base_payload())
        self.assertEqual(result["action"], "OUTREACH")
        self.assertTrue(result["exact_state_preserved"])
        self.assertTrue(result["advisory_only"])
        self.assertFalse(result["outreach_authorized_by_scorecard"])
        self.assertFalse(result["private_correspondence_embedded"])

    def test_generation_drift_fails_closed(self):
        payload = base_payload()
        payload["final_product_generation"] = "2026-08-18-b"
        result = evaluate_opportunity(payload)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["reason"], "PRODUCT_GENERATION_DRIFT")

    def test_not_run_is_not_pass(self):
        payload = base_payload()
        payload["checks"]["execution_surface"] = "NOT_RUN"
        result = evaluate_opportunity(payload)
        self.assertEqual(result["action"], "INCOMPLETE")
        self.assertEqual(result["reason"], "EVIDENCE_INCOMPLETE")

    def test_hold_dominates_high_score(self):
        payload = base_payload()
        payload["checks"]["identity"] = "HOLD"
        payload["opportunity_score"] = 10.0
        result = evaluate_opportunity(payload)
        self.assertEqual(result["action"], "HOLD")

    def test_source_digest_is_deterministic(self):
        self.assertEqual(source_set_digest(SOURCES), source_set_digest(SOURCES))
        self.assertTrue(source_set_digest(SOURCES).startswith("sha256:"))

    def test_score_range_is_fail_closed(self):
        payload = base_payload()
        payload["opportunity_score"] = 10.1
        with self.assertRaises(AstraOpportunityError):
            evaluate_opportunity(payload)


if __name__ == "__main__":
    unittest.main()
