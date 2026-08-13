from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.client_proof import build_causal_security_proof
from contractgraph_qa.path_replay import replay_prior_model_path
from contractgraph_qa.postimpact import load_post_impact_model, run_post_impact_model
from contractgraph_qa.reachability import load_reachability_model, run_reachability_model


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
        cls.prior_model = load_reachability_model(
            cls.root / cls.proof["causalSecurityProof"]["priorModel"]
        )
        cls.post_model = load_post_impact_model(
            cls.root / cls.proof["causalSecurityProof"]["postImpactModel"]
        )
        cls.fixed_model = load_reachability_model(
            cls.root / cls.proof["causalSecurityProof"]["fixedModel"]
        )

    def test_proof_identity_matches_engagement_fixture(self) -> None:
        self.assertEqual(self.proof["schemaVersion"], 2)
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

    def test_causal_path_matches_recomputed_reachability(self) -> None:
        causal = self.proof["causalSecurityProof"]
        expected = causal["causalPath"]
        result = run_reachability_model(self.prior_model)
        self.assertEqual(result["status"], "reachable")
        path = result["path"]
        self.assertEqual(causal["forbiddenCapability"], path["targetCapability"])
        self.assertEqual(expected["initialCapability"], path["initialCapability"])
        self.assertEqual(
            expected["transitionIds"],
            [edge["id"] for edge in path["transitions"]],
        )
        self.assertEqual(expected["violatedAssumptions"], path["violatedAssumptions"])
        self.assertEqual(expected["invariantIds"], path["invariantIds"])
        self.assertEqual(expected["controlBoundaries"], path["crossedBoundaries"])
        self.assertEqual(expected["impact"], path["impact"])

    def test_control_path_matches_recomputed_post_impact_graph(self) -> None:
        causal = self.proof["causalSecurityProof"]
        reachability = run_reachability_model(self.prior_model)
        control = run_post_impact_model(self.post_model, self.prior_model, reachability)
        expected = causal["controlPath"]
        self.assertEqual(expected["status"], control["status"])
        relations = {
            edge["relation"] for edge in control["controlGraph"]["edges"]
        }
        self.assertEqual(set(expected["relations"]), relations)
        restored = next(
            edge["target"].split(":", 1)[1]
            for edge in control["controlGraph"]["edges"]
            if edge["relation"] == "restores_to"
        )
        self.assertEqual(expected["restoredCapability"], restored)

    def test_fix_replay_matches_recomputed_historical_path_replay(self) -> None:
        expected = self.proof["causalSecurityProof"]["fixReplay"]
        replay = replay_prior_model_path(self.prior_model, self.fixed_model)
        self.assertEqual(expected["status"], replay["status"])
        self.assertEqual(
            expected["blockedReason"],
            replay["exactReplay"]["blockedAt"]["reason"],
        )
        self.assertEqual(
            expected["alternateReachability"],
            replay["alternateReachability"]["reachable"],
        )

    def test_causal_builder_preserves_claim_boundary(self) -> None:
        generated = build_causal_security_proof(
            self.prior_model,
            self.post_model,
            self.fixed_model,
        )
        self.assertEqual(generated["fixReplay"]["status"], "fix_verified")
        self.assertEqual(generated["control"]["status"], "contained_and_verified")
        self.assertEqual(
            generated["claimBoundary"],
            self.proof["causalSecurityProof"]["claimBoundary"],
        )

    def test_pilot_offer_remains_small_and_fixed_scope(self) -> None:
        pilot = self.proof["pilot"]
        self.assertEqual(pilot["priceUsd"], 200)
        self.assertLessEqual(pilot["maxPrioritizedInvariants"], 5)
        self.assertEqual(pilot["retestPasses"], 1)


if __name__ == "__main__":
    unittest.main()
