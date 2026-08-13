from __future__ import annotations

import copy
import unittest
from pathlib import Path

from contractgraph_qa.payment_fulfillment import (
    PaymentFulfillmentError,
    evaluate_payment_fulfillment_scenario,
    load_payment_fulfillment_contract,
    load_payment_fulfillment_scenario,
    validate_payment_fulfillment_contract,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "payment-fulfillment"
CONTRACT = BASE / "x402-v2-http-public-contract.v0.1.json"
DELIVERED = BASE / "x402-committed-delivered-stop.json"
UNKNOWN_HOLD = BASE / "x402-committed-unknown-hold.json"
UNKNOWN_REPURCHASE = BASE / "x402-committed-unknown-repurchase.json"


class PaymentFulfillmentTest(unittest.TestCase):
    def test_x402_public_contract_separates_payment_from_fulfillment(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        summary = validate_payment_fulfillment_contract(contract)

        self.assertEqual(summary["providerId"], "x402-v2-http-public")
        self.assertFalse(summary["financialFinalityImpliesFulfillment"])
        self.assertEqual(summary["fulfillmentRecoveryStatus"], "unresolved")

    def test_committed_and_delivered_is_safe(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        scenario = load_payment_fulfillment_scenario(DELIVERED)
        result = evaluate_payment_fulfillment_scenario(contract, scenario)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["payment"]["outcome"], "committed")
        self.assertEqual(result["fulfillment"]["outcome"], "delivered")
        self.assertTrue(result["fulfillment"]["reconciled"])
        self.assertTrue(result["safeToSpendAgain"])

    def test_unknown_fulfillment_can_be_safely_contained(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        scenario = load_payment_fulfillment_scenario(UNKNOWN_HOLD)
        result = evaluate_payment_fulfillment_scenario(contract, scenario)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["fulfillment"]["outcome"], "unknown")
        self.assertFalse(result["fulfillment"]["reconciled"])
        self.assertFalse(result["safeToSpendAgain"])
        self.assertTrue(result["invariants"]["unknownFulfillmentContained"])

    def test_repurchase_after_committed_unknown_fulfillment_is_critical(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        scenario = load_payment_fulfillment_scenario(UNKNOWN_REPURCHASE)
        result = evaluate_payment_fulfillment_scenario(contract, scenario)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["criticalFailure"])
        self.assertLessEqual(result["score"], 49)
        self.assertIn(
            "PFC-001_COMMITTED_PAYMENT_UNKNOWN_FULFILLMENT_NEW_PAYMENT",
            {item["code"] for item in result["violations"]},
        )
        self.assertFalse(result["safeToSpendAgain"])

    def test_contract_rejects_missing_public_refs(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        contract = copy.deepcopy(contract)
        contract["publicContractRefs"] = []

        with self.assertRaisesRegex(PaymentFulfillmentError, "publicContractRefs"):
            validate_payment_fulfillment_contract(contract)

    def test_unknown_next_action_fails_closed(self) -> None:
        contract = load_payment_fulfillment_contract(CONTRACT)
        scenario = load_payment_fulfillment_scenario(UNKNOWN_HOLD)
        scenario = copy.deepcopy(scenario)
        scenario["nextAction"] = "magic_retry"

        with self.assertRaisesRegex(PaymentFulfillmentError, "nextAction"):
            evaluate_payment_fulfillment_scenario(contract, scenario)


if __name__ == "__main__":
    unittest.main()
