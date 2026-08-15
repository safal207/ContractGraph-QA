from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.provider_payment_decision import (
    ProviderPaymentDecisionError,
    evaluate_provider_payment_decision,
)

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"


class ProviderPaymentDecisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = json.loads(
            (ADAPTERS / "crossmint-public-contract.v0.1.json").read_text(encoding="utf-8")
        )
        cls.stripe_adapter = json.loads(
            (ADAPTERS / "stripe-payment-intents-public-contract.v0.1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.x402_adapter = json.loads(
            (ADAPTERS / "coinbase-x402-v2-public-contract.v0.1.json").read_text(
                encoding="utf-8"
            )
        )

    def _observations(self, name: str) -> dict:
        return json.loads((ADAPTERS / name).read_text(encoding="utf-8"))

    def _authority(self) -> dict[str, str]:
        return {
            "status": "authorized",
            "evidenceRef": "fixture://authority/crossmint/test",
        }

    def _stripe_authority(self) -> dict[str, str]:
        return {
            "status": "authorized",
            "evidenceRef": "fixture://authority/stripe/test",
        }

    def _x402_authority(self) -> dict[str, str]:
        return {
            "status": "authorized",
            "evidenceRef": "fixture://authority/coinbase-x402/test",
        }

    def test_reviewed_profile_records_same_key_replay_without_inventing_retry_authority(self) -> None:
        self.assertEqual(self.adapter["schema"], "cgqa.payment-provider-adapter.v0.3")
        self.assertEqual(self.adapter["profileVersion"], "0.2")
        self.assertTrue(self.adapter["create"]["supportsIdempotencyKey"])
        self.assertTrue(self.adapter["create"]["sameKeyReplayDocumented"])
        self.assertEqual(self.adapter["evidencePrecedenceStatus"], "unresolved")
        self.assertEqual(self.adapter["retrySemanticsStatus"], "unresolved")
        self.assertEqual(self.adapter["retryAllowedAfterProviderStates"], [])

    def test_crossmint_webhook_only_stays_nonfinal_and_blocks_money(self) -> None:
        result = evaluate_provider_payment_decision(
            self.adapter,
            self._observations("crossmint-observations-webhook-only.json"),
            {
                "status": "authorized",
                "evidenceRef": "fixture://authority/crossmint/example-002",
            },
        )

        self.assertEqual(result["providerId"], "crossmint-wallet-transactions-public")
        self.assertEqual(result["reconciliation"]["status"], "nonfinal")
        self.assertEqual(result["decision"]["decision"], "RECONCILE")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])
        self.assertEqual(
            result["decision"]["state"]["payment"]["evidenceRef"],
            "fixture://crossmint/wallet-transfer-webhook/succeeded",
        )

    def test_crossmint_get_success_stops_second_money_action(self) -> None:
        result = evaluate_provider_payment_decision(
            self.adapter,
            self._observations("crossmint-observations-get-success.json"),
            {
                "status": "authorized",
                "evidenceRef": "fixture://authority/crossmint/example-001",
            },
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "committed")
        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertEqual(result["decision"]["reason"], "logical_operation_already_satisfied")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_v03_final_failure_keeps_new_money_retry_authority_unresolved(self) -> None:
        failed = {
            "schema": "cgqa.payment-provider-observations.v0.1",
            "logicalOperationId": "crossmint-public-example-failed",
            "executionId": "exec-crossmint-public-failed",
            "observations": [
                {
                    "source": "get-transaction",
                    "providerState": "failed",
                    "evidenceRef": "fixture://crossmint/get-transaction/failed",
                }
            ],
        }
        result = evaluate_provider_payment_decision(
            self.adapter,
            failed,
            {
                "status": "authorized",
                "evidenceRef": "fixture://authority/crossmint/example-failed",
            },
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "failed")
        self.assertFalse(result["reconciliation"]["retryAllowed"])
        self.assertEqual(
            result["reconciliation"].get("retryBlockReason"),
            "retry_semantics_unresolved",
        )
        self.assertEqual(result["retryAuthority"]["status"], "unresolved")
        self.assertFalse(result["retryAuthority"]["allowed"])
        self.assertEqual(result["retryAuthority"]["reason"], "retry_semantics_unresolved")
        self.assertEqual(result["decision"]["decision"], "HOLD")
        self.assertEqual(result["decision"]["reason"], "retry_authority_unresolved")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_authority_is_never_inferred_from_provider_success(self) -> None:
        result = evaluate_provider_payment_decision(
            self.adapter,
            self._observations("crossmint-observations-get-success.json"),
            {
                "status": "revoked",
                "evidenceRef": "fixture://authority/crossmint/revoked",
            },
        )

        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertEqual(result["decision"]["reason"], "authority_revoked")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_stripe_public_profile_is_second_reviewed_afsp_provider(self) -> None:
        self.assertEqual(self.stripe_adapter["schema"], "cgqa.payment-provider-adapter.v0.3")
        self.assertEqual(self.stripe_adapter["profileVersion"], "0.1")
        self.assertTrue(self.stripe_adapter["create"]["supportsIdempotencyKey"])
        self.assertTrue(self.stripe_adapter["create"]["sameKeyReplayDocumented"])
        self.assertEqual(self.stripe_adapter["evidencePrecedenceStatus"], "unresolved")
        self.assertEqual(self.stripe_adapter["retrySemanticsStatus"], "unresolved")

    def test_stripe_webhook_only_stays_nonfinal_and_blocks_money(self) -> None:
        result = evaluate_provider_payment_decision(
            self.stripe_adapter,
            self._observations("stripe-observations-webhook-only.json"),
            self._stripe_authority(),
        )

        self.assertEqual(result["providerId"], "stripe-payment-intents-public")
        self.assertEqual(result["reconciliation"]["status"], "nonfinal")
        self.assertEqual(result["decision"]["decision"], "RECONCILE")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_stripe_get_succeeded_stops_second_money_action(self) -> None:
        result = evaluate_provider_payment_decision(
            self.stripe_adapter,
            self._observations("stripe-observations-get-succeeded.json"),
            self._stripe_authority(),
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "committed")
        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertEqual(result["decision"]["reason"], "logical_operation_already_satisfied")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_stripe_canceled_is_final_but_new_payment_authority_remains_unresolved(self) -> None:
        result = evaluate_provider_payment_decision(
            self.stripe_adapter,
            self._observations("stripe-observations-get-canceled.json"),
            self._stripe_authority(),
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "failed")
        self.assertFalse(result["reconciliation"]["retryAllowed"])
        self.assertEqual(result["retryAuthority"]["status"], "unresolved")
        self.assertEqual(result["decision"]["decision"], "HOLD")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_x402_core_profile_preserves_nonce_vs_idempotency_distinction(self) -> None:
        self.assertEqual(self.x402_adapter["schema"], "cgqa.payment-provider-adapter.v0.3")
        self.assertEqual(self.x402_adapter["profileVersion"], "0.1")
        self.assertFalse(self.x402_adapter["create"]["supportsIdempotencyKey"])
        self.assertFalse(self.x402_adapter["create"]["sameKeyReplayDocumented"])
        self.assertEqual(self.x402_adapter["evidencePrecedenceStatus"], "unresolved")
        self.assertEqual(self.x402_adapter["retrySemanticsStatus"], "unresolved")

    def test_x402_verify_valid_is_not_settlement_and_reconciles(self) -> None:
        result = evaluate_provider_payment_decision(
            self.x402_adapter,
            self._observations("coinbase-x402-observations-verify-valid.json"),
            self._x402_authority(),
        )

        self.assertEqual(result["providerId"], "coinbase-x402-v2-public")
        self.assertEqual(result["reconciliation"]["status"], "nonfinal")
        self.assertEqual(result["reconciliation"]["outcome"], "pending")
        self.assertEqual(result["decision"]["decision"], "RECONCILE")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_x402_settle_success_stops_second_economic_action(self) -> None:
        result = evaluate_provider_payment_decision(
            self.x402_adapter,
            self._observations("coinbase-x402-observations-settle-success.json"),
            self._x402_authority(),
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "committed")
        self.assertEqual(result["decision"]["decision"], "STOP")
        self.assertEqual(result["decision"]["reason"], "logical_operation_already_satisfied")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_x402_settle_failure_does_not_authorize_fresh_payment(self) -> None:
        result = evaluate_provider_payment_decision(
            self.x402_adapter,
            self._observations("coinbase-x402-observations-settle-failed.json"),
            self._x402_authority(),
        )

        self.assertEqual(result["reconciliation"]["status"], "final")
        self.assertEqual(result["reconciliation"]["outcome"], "failed")
        self.assertFalse(result["reconciliation"]["retryAllowed"])
        self.assertEqual(result["retryAuthority"]["status"], "unresolved")
        self.assertEqual(result["decision"]["decision"], "HOLD")
        self.assertFalse(result["decision"]["monetaryActionAllowed"])

    def test_x402_profile_rejects_invented_core_idempotency(self) -> None:
        adapter = copy.deepcopy(self.x402_adapter)
        adapter["create"]["supportsIdempotencyKey"] = True
        adapter["create"]["sameKeyReplayDocumented"] = True

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "must not invent an idempotency key"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("coinbase-x402-observations-settle-success.json"),
                self._x402_authority(),
            )

    def test_x402_profile_rejects_verify_promoted_to_finality(self) -> None:
        adapter = copy.deepcopy(self.x402_adapter)
        adapter["evidenceSources"][1]["authoritativeForFinality"] = True

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "facilitator settle as finality"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("coinbase-x402-observations-settle-success.json"),
                self._x402_authority(),
            )

    def test_rejects_profile_that_downgrades_documented_same_key_replay(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["create"]["sameKeyReplayDocumented"] = False

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "same-key replay"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_profile_that_invents_retry_authority(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["retrySemanticsStatus"] = "documented"
        adapter["retryAllowedAfterProviderStates"] = ["failed"]

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "retry authority unresolved"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_profile_that_promotes_webhook_to_finality_authority(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["evidenceSources"][1]["authoritativeForFinality"] = True

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "GET transaction as finality authority"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_unreviewed_provider_using_reviewed_shape(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["providerId"] = "unreviewed-provider"

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "not a reviewed AFSP profile"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_unreviewed_crossmint_profile_version(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["profileVersion"] = "0.3"

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "requires profileVersion"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_stripe_profile_that_promotes_webhook_to_finality_authority(self) -> None:
        adapter = copy.deepcopy(self.stripe_adapter)
        adapter["evidenceSources"][1]["authoritativeForFinality"] = True

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "GET PaymentIntent as finality authority"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("stripe-observations-get-succeeded.json"),
                self._stripe_authority(),
            )


if __name__ == "__main__":
    unittest.main()
