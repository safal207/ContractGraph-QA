from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp import evaluate_fcrp_case

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "benchmarks" / "fcrp-v0.1" / "FCRP-SELF-002-gonka-local-pass-global-fail.json"
COLLISION_GUARD = ROOT / "external-validation" / "gonka" / "harness" / "cgqa_correlation_collision_test.go"
CORRELATION_CONTRACT = ROOT / "external-validation" / "gonka" / "remediation" / "production-correlation-contract.md"


class FCRPSelf002GonkaTest(unittest.TestCase):
    def test_local_pass_is_blocked_when_parent_accounting_invariant_fails(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        result = evaluate_fcrp_case(case)

        self.assertEqual(result["caseId"], "FCRP-SELF-002")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["firstMeaningfulDivergence"], "N2")
        self.assertEqual(result["causePoint"], "N2")
        self.assertEqual(result["refactorPoint"], "N2")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["localVerification"], "PASS")
        self.assertEqual(result["upwardVerification"], "FAIL")
        self.assertFalse(result["stopConditionsSatisfied"])
        self.assertEqual(case["expectedProtocolDecision"], result["decision"])

    def test_case_is_bound_to_existing_collision_and_replacement_evidence(self) -> None:
        collision_guard = COLLISION_GUARD.read_text(encoding="utf-8")
        contract = CORRELATION_CONTRACT.read_text(encoding="utf-8")

        self.assertIn("REJECTED_AS_PRODUCTION_FIX", collision_guard)
        self.assertIn("LogicalOperationsSimulated:       2", collision_guard)
        self.assertIn("CanonicalRequestRows:             requestRows", collision_guard)
        self.assertIn("Attempts from both operations", collision_guard.replace("attempts", "Attempts", 1))
        self.assertIn("MUST NOT be used directly as the canonical", contract)
        self.assertIn("request_correlations", contract)
        self.assertIn("one-to-many", contract)
        self.assertIn("retry is not idempotency", contract.lower())


if __name__ == "__main__":
    unittest.main()
