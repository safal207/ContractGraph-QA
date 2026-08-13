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

    def _observations(self, name: str) -> dict:
        return json.loads((ADAPTERS / name).read_text(encoding="utf-8"))

    def _authority(self) -> dict[str, str]:
        return {
            "status": "authorized",
            "evidenceRef": "fixture://authority/crossmint/test",
        }

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

    def test_v02_final_failure_does_not_inherit_legacy_retry_allowance(self) -> None:
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
        # The v0.2 reconciler predates explicit retry-authority semantics and may
        # report retryAllowed=True. The bridge must not promote that to money authority.
        self.assertTrue(result["reconciliation"]["retryAllowed"])
        self.assertEqual(result["retryAuthority"]["status"], "unresolved")
        self.assertFalse(result["retryAuthority"]["allowed"])
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

    def test_rejects_retry_capable_v03_profile_before_decision(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["schema"] = "cgqa.payment-provider-adapter.v0.3"
        adapter["retrySemanticsStatus"] = "documented"
        adapter["retryAllowedAfterProviderStates"] = ["failed"]

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "requires the reviewed Crossmint"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_other_provider_using_v02_shape(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["providerId"] = "unreviewed-provider"

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "requires providerId"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )

    def test_rejects_unreviewed_crossmint_profile_version(self) -> None:
        adapter = copy.deepcopy(self.adapter)
        adapter["profileVersion"] = "0.2"

        with self.assertRaisesRegex(ProviderPaymentDecisionError, "requires profileVersion"):
            evaluate_provider_payment_decision(
                adapter,
                self._observations("crossmint-observations-get-success.json"),
                self._authority(),
            )


if __name__ == "__main__":
    unittest.main()
