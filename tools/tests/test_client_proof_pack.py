from __future__ import annotations

import json
import unittest
from pathlib import Path


class ClientProofPackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.proof = json.loads(
            (cls.root / "docs/client-proof/proof.json").read_text(encoding="utf-8")
        )
        cls.result = json.loads(
            (cls.root / "results/examples/CGQA-E-001.engagement-result.json").read_text(
                encoding="utf-8"
            )
        )

    def test_proof_identity_matches_engagement_fixture(self) -> None:
        self.assertEqual(self.proof["sourceType"], "repository-owned-local-demo")
        self.assertEqual(self.proof["engagementId"], self.result["engagementId"])
        self.assertEqual(self.proof["adapterId"], self.result["adapterId"])
        self.assertEqual(self.proof["scopeId"], self.result["scopeId"])

    def test_proof_coverage_matches_recorded_outcomes(self) -> None:
        counts = {
            "violated": 0,
            "not_found_within_bound": 0,
            "inconclusive": 0,
        }
        for check in self.result["checks"]:
            counts[check["status"]] += 1
        self.assertEqual(self.proof["expectedCoverage"], counts)

    def test_proof_minimal_path_matches_violated_check(self) -> None:
        violated = next(
            check
            for check in self.result["checks"]
            if check["invariantId"] == self.proof["violatedInvariantId"]
        )
        self.assertEqual(violated["status"], "violated")
        self.assertEqual(
            self.proof["minimalPathActionIds"],
            [step["actionId"] for step in violated["path"]],
        )

    def test_pilot_offer_remains_small_and_fixed_scope(self) -> None:
        pilot = self.proof["pilot"]
        self.assertEqual(pilot["priceUsd"], 200)
        self.assertLessEqual(pilot["maxPrioritizedInvariants"], 5)
        self.assertEqual(pilot["retestPasses"], 1)


if __name__ == "__main__":
    unittest.main()
