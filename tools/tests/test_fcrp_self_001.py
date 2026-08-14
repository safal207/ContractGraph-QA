from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp import FCRPError, evaluate_fcrp_case
from contractgraph_qa.provider_decision_evidence import (
    ProviderDecisionEvidenceError,
    build_provider_decision_evidence,
    canonical_evidence_pack_sha256,
    verify_provider_decision_evidence,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision

ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = ROOT / "benchmarks" / "fcrp-v0.1" / "FCRP-SELF-001.json"
ADAPTERS = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"


class FCRPSelf001Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.case = json.loads(CASE_PATH.read_text(encoding="utf-8"))

    def test_self_case_identifies_fixture_as_first_divergence_and_refactor_point(self) -> None:
        result = evaluate_fcrp_case(copy.deepcopy(self.case))
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["firstMeaningfulDivergence"], "N2")
        self.assertEqual(result["causePoint"], "N2")
        self.assertEqual(result["refactorPoint"], "N2")
        self.assertEqual(result["navigationDirection"], "UP")

    def test_self_case_replays_the_external_digest_invariant(self) -> None:
        adapter = json.loads(
            (ADAPTERS / "crossmint-public-contract.v0.1.json").read_text(encoding="utf-8")
        )
        observations = json.loads(
            (ADAPTERS / "crossmint-observations-get-success.json").read_text(encoding="utf-8")
        )
        authority = {
            "status": "authorized",
            "evidenceRef": "fixture://authority/crossmint/fcrp-self-001",
        }
        decision = evaluate_provider_payment_decision(
            adapter,
            observations,
            authority,
            decision_id="fcrp-self-001",
        )
        pack = build_provider_decision_evidence(adapter, observations, authority, decision)
        actual_digest = canonical_evidence_pack_sha256(pack)
        wrong_digest = "0" * 64 if actual_digest != "0" * 64 else "f" * 64

        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "external digest mismatch"):
            verify_provider_decision_evidence(pack, expected_pack_sha256=wrong_digest)

    def test_upward_stop_cannot_be_claimed_without_all_stop_conditions(self) -> None:
        case = copy.deepcopy(self.case)
        case["verification"]["upward"] = "NOT_REQUIRED"
        case["verification"]["stopConditions"]["parentInvariantsPreserved"] = False
        with self.assertRaisesRegex(FCRPError, "all stop conditions hold"):
            evaluate_fcrp_case(case)

    def test_divergence_must_reference_the_declared_causal_path(self) -> None:
        case = copy.deepcopy(self.case)
        case["divergence"]["firstMeaningfulDivergence"] = "UNKNOWN"
        with self.assertRaisesRegex(FCRPError, "unknown causal point"):
            evaluate_fcrp_case(case)


if __name__ == "__main__":
    unittest.main()
