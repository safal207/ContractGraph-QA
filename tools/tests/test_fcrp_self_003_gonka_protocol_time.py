from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp import evaluate_fcrp_case

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "benchmarks" / "fcrp-v0.1" / "FCRP-SELF-003-gonka-protocol-time-oracle.json"
G004P_CASE = ROOT / "external-validation" / "gonka" / "cases" / "G-004P-post-success-pending-reserve-liveness.yaml"
G004P_HARNESS = ROOT / "external-validation" / "gonka" / "harness" / "cgqa_post_success_liveness_test.go"


class FCRPSelf003GonkaProtocolTimeTest(unittest.TestCase):
    def test_wait_only_oracle_is_blocked_until_protocol_time_is_modeled(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        result = evaluate_fcrp_case(case)

        self.assertEqual(result["caseId"], "FCRP-SELF-003")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["firstMeaningfulDivergence"], "N3")
        self.assertEqual(result["causePoint"], "N3")
        self.assertEqual(result["refactorPoint"], "N3")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["localVerification"], "FAIL")
        self.assertEqual(result["upwardVerification"], "PASS")
        self.assertFalse(result["stopConditionsSatisfied"])
        self.assertEqual(case["expectedProtocolDecision"], result["decision"])

    def test_case_is_bound_to_current_wait_only_g004p_contract(self) -> None:
        contract = G004P_CASE.read_text(encoding="utf-8")
        harness = G004P_HARNESS.read_text(encoding="utf-8")

        self.assertIn("window_seconds: 120", contract)
        self.assertIn("successful retry winner must become terminal inside the bounded observation window", contract)
        self.assertIn("const observationWindow = 120 * time.Second", harness)
        self.assertIn("time.Sleep(sampleInterval)", harness)
        self.assertIn("nonterminal_after_observation_window", harness)

    def test_refactor_explicitly_switches_from_wall_clock_to_protocol_clock(self) -> None:
        case = json.loads(CASE.read_text(encoding="utf-8"))
        change = case["refactor"]["change"]
        self.assertIn("protocol-clock oracle", change)
        self.assertIn("next eligible diff applied", change)
        self.assertIn("separate product requirement", change)


if __name__ == "__main__":
    unittest.main()
