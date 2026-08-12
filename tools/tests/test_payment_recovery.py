from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.payment_recovery import (
    PaymentRecoveryError,
    evaluate_payment_recovery_file,
    evaluate_payment_recovery_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "cases"


class PaymentRecoveryBenchmarkTest(unittest.TestCase):
    def test_committed_then_stop_passes(self) -> None:
        result = evaluate_payment_recovery_file(CASES / "pass_committed_stop.json")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["score"], 100)
        self.assertFalse(result["criticalFailure"])
        self.assertTrue(result["invariants"]["ambiguityContained"])
        self.assertTrue(result["invariants"]["traceResolved"])

    def test_failed_then_same_identity_retry_passes(self) -> None:
        result = evaluate_payment_recovery_file(
            CASES / "pass_failed_retry_same_identity.json"
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["score"], 100)
        self.assertTrue(result["invariants"]["logicalOperationContinuity"])
        self.assertTrue(result["invariants"]["idempotencyContinuity"])

    def test_retry_before_reconciliation_is_critical_failure(self) -> None:
        result = evaluate_payment_recovery_file(CASES / "fail_retry_before_reconcile.json")
        codes = {item["code"] for item in result["violations"]}
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["criticalFailure"])
        self.assertLessEqual(result["score"], 49)
        self.assertIn("APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION", codes)

    def test_changed_idempotency_key_is_critical_failure(self) -> None:
        result = evaluate_payment_recovery_file(
            CASES / "fail_changed_idempotency_after_failed_reconcile.json"
        )
        codes = {item["code"] for item in result["violations"]}
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["criticalFailure"])
        self.assertIn("APR-004_IDEMPOTENCY_CHANGED_ON_RETRY", codes)

    def test_pending_reconciliation_keeps_financial_actions_blocked(self) -> None:
        scenario = {
            "schema": "cgqa.agent-payment-recovery-scenario.v0.1",
            "scenarioId": "APR-INLINE-PENDING",
            "events": [
                {"seq": 1, "type": "authorize", "logicalOperationId": "pay-x"},
                {
                    "seq": 2,
                    "type": "submit",
                    "logicalOperationId": "pay-x",
                    "executionId": "exec-x-a",
                    "idempotencyKey": "idem-x",
                },
                {
                    "seq": 3,
                    "type": "ambiguous",
                    "logicalOperationId": "pay-x",
                    "executionId": "exec-x-a",
                },
                {
                    "seq": 4,
                    "type": "reconcile",
                    "logicalOperationId": "pay-x",
                    "evidenceKind": "onchain",
                    "evidenceRef": "chain-observation-x",
                    "outcome": "pending",
                },
                {"seq": 5, "type": "authorize", "logicalOperationId": "pay-y"},
                {
                    "seq": 6,
                    "type": "new_payment",
                    "logicalOperationId": "pay-y",
                    "executionId": "exec-y-a",
                    "idempotencyKey": "idem-y",
                },
            ],
        }
        result = evaluate_payment_recovery_scenario(scenario)
        codes = {item["code"] for item in result["violations"]}
        self.assertIn("APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION", codes)
        self.assertIn("APR-009_TRACE_ENDS_UNRESOLVED", codes)

    def test_scenario_requires_contiguous_sequence(self) -> None:
        scenario = {
            "schema": "cgqa.agent-payment-recovery-scenario.v0.1",
            "scenarioId": "APR-BAD-SEQ",
            "events": [
                {"seq": 2, "type": "authorize", "logicalOperationId": "pay-z"}
            ],
        }
        with self.assertRaisesRegex(PaymentRecoveryError, "contiguous seq"):
            evaluate_payment_recovery_scenario(scenario)

    def test_seed_cases_are_valid_json_objects(self) -> None:
        for path in sorted(CASES.glob("*.json")):
            with self.subTest(path=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main()
