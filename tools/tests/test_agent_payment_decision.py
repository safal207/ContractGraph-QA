from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision,
    evaluate_agent_payment_decision_file,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "unified-decision" / "examples"


class AgentPaymentDecisionTest(unittest.TestCase):
    def test_initial_authorized_payment_is_allowed(self) -> None:
        result = evaluate_agent_payment_decision_file(EXAMPLES / "allow-initial.json")
        self.assertEqual(result["decision"], "ALLOW")
        self.assertTrue(result["monetaryActionAllowed"])

    def test_ambiguous_payment_requires_reconciliation(self) -> None:
        result = evaluate_agent_payment_decision_file(EXAMPLES / "reconcile-ambiguous.json")
        self.assertEqual(result["decision"], "RECONCILE")
        self.assertFalse(result["monetaryActionAllowed"])
        self.assertIn("payment_finality", result["blockers"])

    def test_final_failure_with_unresolved_retry_authority_holds(self) -> None:
        result = evaluate_agent_payment_decision_file(EXAMPLES / "hold-retry-unresolved.json")
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason"], "retry_authority_unresolved")

    def test_committed_and_delivered_stops_same_logical_operation(self) -> None:
        result = evaluate_agent_payment_decision_file(EXAMPLES / "stop-delivered.json")
        self.assertEqual(result["decision"], "STOP")
        self.assertEqual(result["reason"], "logical_operation_already_satisfied")

    def test_committed_but_not_delivered_requires_compensation(self) -> None:
        result = evaluate_agent_payment_decision_file(EXAMPLES / "compensate-not-delivered.json")
        self.assertEqual(result["decision"], "COMPENSATE")
        self.assertFalse(result["monetaryActionAllowed"])

    def test_documented_retry_can_be_allowed(self) -> None:
        payload = json.loads((EXAMPLES / "hold-retry-unresolved.json").read_text(encoding="utf-8"))
        payload = copy.deepcopy(payload)
        payload["payment"]["retryAuthorityStatus"] = "documented"
        payload["payment"]["retryAllowed"] = True
        result = evaluate_agent_payment_decision(payload)
        self.assertEqual(result["decision"], "ALLOW")
        self.assertEqual(result["reason"], "documented_retry_authority")

    def test_unresolved_retry_authority_cannot_claim_retry_allowed(self) -> None:
        payload = json.loads((EXAMPLES / "hold-retry-unresolved.json").read_text(encoding="utf-8"))
        payload["payment"]["retryAllowed"] = True
        with self.assertRaisesRegex(AgentPaymentDecisionError, "unresolved retry authority"):
            evaluate_agent_payment_decision(payload)

    def test_unknown_authority_holds_even_before_payment(self) -> None:
        payload = json.loads((EXAMPLES / "allow-initial.json").read_text(encoding="utf-8"))
        payload["authority"]["status"] = "unknown"
        result = evaluate_agent_payment_decision(payload)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason"], "authority_unresolved")


if __name__ == "__main__":
    unittest.main()
