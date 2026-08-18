import unittest

from contractgraph_qa.astra_opportunity_drift import evaluate_opportunity_drift


def card(company, generation, score, surfaces, action="OUTREACH", checks=None):
    return {
        "company_id": company,
        "final_product_generation": generation,
        "opportunity_score": score,
        "execution_surfaces": surfaces,
        "action": action,
        "checks": checks
        or {
            "identity": "PASS",
            "execution_surface": "PASS",
            "evidence_freshness": "PASS",
            "reachability": "PASS",
        },
        "next_best_evidence": "verify retry lineage",
    }


class AstraOpportunityDriftTests(unittest.TestCase):
    def test_new_execution_surface_is_material_positive_drift(self):
        result = evaluate_opportunity_drift(
            {
                "previous": card("acme", "g1", 8.8, ["wallet"]),
                "current": card("acme", "g2", 9.4, ["wallet", "autonomous_payout"]),
            }
        )
        self.assertEqual(result["classification"], "MATERIAL_POSITIVE_DRIFT")
        self.assertEqual(result["action"], "PRIORITIZE_REVIEW")
        self.assertEqual(result["added_execution_surfaces"], ["autonomous_payout"])
        self.assertFalse(result["outreach_authorized"])

    def test_score_increase_alone_does_not_promote(self):
        result = evaluate_opportunity_drift(
            {
                "previous": card("acme", "g1", 8.0, ["wallet"]),
                "current": card("acme", "g1", 9.2, ["wallet"]),
            }
        )
        self.assertEqual(result["classification"], "SCORE_DRIFT_ONLY")
        self.assertEqual(result["action"], "NO_AUTOMATIC_PROMOTION")

    def test_incomplete_current_evidence_forces_reverify(self):
        checks = {
            "identity": "PASS",
            "execution_surface": "PASS",
            "evidence_freshness": "INCOMPLETE",
            "reachability": "PASS",
        }
        result = evaluate_opportunity_drift(
            {
                "previous": card("acme", "g1", 8.0, ["wallet"]),
                "current": card("acme", "g2", 9.5, ["wallet", "payout"], action="INCOMPLETE", checks=checks),
            }
        )
        self.assertEqual(result["classification"], "REVERIFY")
        self.assertEqual(result["action"], "HOLD")

    def test_company_identity_change_holds(self):
        result = evaluate_opportunity_drift(
            {
                "previous": card("oldco", "g1", 8.0, ["wallet"]),
                "current": card("newco", "g2", 9.0, ["wallet", "payout"]),
            }
        )
        self.assertEqual(result["classification"], "IDENTITY_DRIFT")
        self.assertEqual(result["action"], "HOLD")

    def test_removed_surface_is_negative_drift(self):
        result = evaluate_opportunity_drift(
            {
                "previous": card("acme", "g1", 9.0, ["wallet", "payout"]),
                "current": card("acme", "g2", 8.4, ["wallet"]),
            }
        )
        self.assertEqual(result["classification"], "NEGATIVE_DRIFT")
        self.assertEqual(result["removed_execution_surfaces"], ["payout"])


if __name__ == "__main__":
    unittest.main()
