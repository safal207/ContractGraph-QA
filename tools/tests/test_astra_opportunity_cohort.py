import json
import unittest
from pathlib import Path

from contractgraph_qa.astra_opportunity import evaluate_opportunity


FIXTURE = Path("benchmarks/astra-v0.1/opportunity-exact-head-2026-08-18.json")


class AstraOpportunityCohortTests(unittest.TestCase):
    def test_frozen_cohort_matches_expected_actions(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        observed = {}
        for case in payload["cases"]:
            result = evaluate_opportunity(case)
            observed[case["company_id"]] = result["action"]
            self.assertEqual(result["action"], case["expected_action"])
            self.assertTrue(result["exact_state_preserved"])
            self.assertFalse(result["private_correspondence_embedded"])
        self.assertEqual(
            observed,
            {
                "passes": "OUTREACH",
                "kastle": "OUTREACH",
                "fullseam": "OUTREACH",
                "grade": "INCOMPLETE",
            },
        )

    def test_score_never_grants_outreach_authority(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for case in payload["cases"]:
            result = evaluate_opportunity(case)
            self.assertFalse(result["outreach_authorized_by_scorecard"])
            self.assertTrue(result["advisory_only"])


if __name__ == "__main__":
    unittest.main()
