from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp import evaluate_fcrp_case

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "benchmarks" / "fcrp-v0.1" / "FCRP-SELF-004-protocol-clock-refactor.json"
G004Q_CASE = ROOT / "external-validation" / "gonka" / "cases" / "G-004Q-protocol-clock-reconciliation.yaml"
G004Q_HARNESS = ROOT / "external-validation" / "gonka" / "harness" / "cgqa_protocol_clock_reconciliation_test.go"
CGQA_SUPPORT = ROOT / "external-validation" / "gonka" / "remediation" / "cgqa_safe_correlation_support.go"


class FCRPSelf004ProtocolClockRefactorTest(unittest.TestCase):
    def test_refactored_oracle_passes_fcrp_structure(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        result = evaluate_fcrp_case(case)

        self.assertEqual(result["caseId"], "FCRP-SELF-004")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["firstMeaningfulDivergence"], "N1")
        self.assertEqual(result["causePoint"], "N1")
        self.assertEqual(result["refactorPoint"], "N2")
        self.assertEqual(result["navigationDirection"], "STOP")
        self.assertEqual(result["localVerification"], "PASS")
        self.assertEqual(result["upwardVerification"], "PASS")
        self.assertTrue(result["stopConditionsSatisfied"])
        self.assertEqual(case["expectedProtocolDecision"], result["decision"])

    def test_g004q_binds_readiness_before_protocol_event(self) -> None:
        contract = G004Q_CASE.read_text(encoding="utf-8")
        harness = G004Q_HARNESS.read_text(encoding="utf-8")
        support = CGQA_SUPPORT.read_text(encoding="utf-8")

        self.assertIn("next_eligible_state_advancing_request", contract)
        self.assertIn("retry_winner_nonce in finish_inference_ids", contract)
        self.assertIn("waitG004QPendingFinish", harness)
        self.assertIn("FinishReadyBeforeAdvance", harness)
        self.assertIn("retry winner remained non-terminal after a witnessed Finish and an actual state-advance opportunity", harness)
        self.assertIn("handleCGQAPendingProtocolTxs", support)
        self.assertIn("p.session.PendingTxs()", support)

    def test_financial_oracle_uses_whole_state_delta(self) -> None:
        contract = G004Q_CASE.read_text(encoding="utf-8")
        harness = G004Q_HARNESS.read_text(encoding="utf-8")

        self.assertIn("InferenceLiability_after - InferenceLiability_before", contract)
        self.assertIn("Fees_after - Fees_before", contract)
        self.assertIn("g004qLiability(pendingDump)", harness)
        self.assertIn("g004qLiability(afterDump)", harness)
        self.assertIn("HostStats cost delta did not match inference ActualCost delta", harness)


if __name__ == "__main__":
    unittest.main()
