from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.provider_adapter import (
    load_provider_adapter,
    load_provider_observations,
    reconcile_provider_observations,
    validate_provider_adapter,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"
STRIPE = BASE / "stripe-payment-intents-public-contract.v0.1.json"
STRIPE_SUCCEEDED = BASE / "stripe-observations-get-succeeded.json"
STRIPE_WEBHOOK = BASE / "stripe-observations-webhook-only.json"
STRIPE_CANCELED = BASE / "stripe-observations-get-canceled.json"


class StripeAfspProfileTest(unittest.TestCase):
    def _authority(self) -> dict[str, str]:
        return {
            "status": "authorized",
            "evidenceRef": "fixture://authority/stripe/afsp",
        }

    def test_profile_is_valid_and_preserves_idempotent_discovery(self) -> None:
        adapter = load_provider_adapter(STRIPE)
        summary = validate_provider_adapter(adapter)

        self.assertEqual(summary["providerId"], "stripe-payment-intents-public")
        self.assertEqual(summary["schema"], "cgqa.payment-provider-adapter.v0.3")
        self.assertTrue(adapter["create"]["supportsIdempotencyKey"])
        self.assertTrue(adapter["create"]["sameKeyReplayDocumented"])
        self.assertEqual(summary["evidencePrecedenceStatus"], "unresolved")
        self.assertEqual(summary["retrySemanticsStatus"], "unresolved")

    def test_get_payment_intent_succeeded_is_final_and_stops_duplicate_money(self) -> None:
        adapter = load_provider_adapter(STRIPE)
        observations = load_provider_observations(STRIPE_SUCCEEDED)
        result = evaluate_provider_payment_decision(adapter, observations, self._authority())

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "committed")
        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_webhook_only_is_trigger_evidence_not_canonical_finality(self) -> None:
        adapter = load_provider_adapter(STRIPE)
        observations = load_provider_observations(STRIPE_WEBHOOK)
        result = evaluate_provider_payment_decision(adapter, observations, self._authority())

        self.assertEqual(result["reconciliation"]["status"], "nonfinal")
        self.assertEqual(
            result["reconciliation"]["reconciliationBlockReason"],
            "no_authoritative_finality_surface_observed",
        )
        self.assertEqual(result["decision"]["decision"], "RECONCILE")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_canceled_is_final_but_does_not_authorize_new_payment(self) -> None:
        adapter = load_provider_adapter(STRIPE)
        observations = load_provider_observations(STRIPE_CANCELED)
        result = evaluate_provider_payment_decision(adapter, observations, self._authority())

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "failed")
        self.assertEqual(result["retryAuthority"]["status"], "unresolved")
        self.assertEqual(result["decision"]["decision"], "HOLD")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_processing_remains_nonfinal_even_from_canonical_lookup(self) -> None:
        adapter = load_provider_adapter(STRIPE)
        observations = {
            "schema": "cgqa.payment-provider-observations.v0.1",
            "logicalOperationId": "stripe-payment-intent-processing",
            "executionId": "exec-stripe-payment-intent-processing",
            "observations": [
                {
                    "source": "get-payment-intent",
                    "providerState": "processing",
                    "evidenceRef": "fixture://stripe/payment-intent/processing",
                }
            ],
        }
        reconciliation = reconcile_provider_observations(adapter, observations)
        decision = evaluate_provider_payment_decision(adapter, observations, self._authority())

        self.assertEqual(reconciliation["status"], "nonfinal")
        self.assertEqual(reconciliation["outcome"], "pending")
        self.assertEqual(decision["decision"]["decision"], "RECONCILE")
        self.assertFalse(decision["decision"]["monetaryActionAllowed"])


if __name__ == "__main__":
    unittest.main()
