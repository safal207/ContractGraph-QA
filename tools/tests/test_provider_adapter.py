from __future__ import annotations

import copy
import unittest
from pathlib import Path

from contractgraph_qa.provider_adapter import (
    ProviderAdapterError,
    load_provider_adapter,
    load_provider_observations,
    reconcile_provider_observations,
    validate_provider_adapter,
)


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters" / "example-public-contract.json"
NONFINAL = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters" / "example-observations-nonfinal.json"
FINAL = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters" / "example-observations-final.json"


class ProviderAdapterTest(unittest.TestCase):
    def test_example_adapter_is_valid(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        summary = validate_provider_adapter(adapter)

        self.assertEqual(summary["status"], "valid")
        self.assertEqual(summary["providerId"], "example-provider")
        self.assertEqual(
            summary["evidencePrecedence"],
            ["onchain-state", "status-api", "webhook"],
        )

    def test_higher_precedence_pending_keeps_reconciliation_nonfinal(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        observations = load_provider_observations(NONFINAL)
        result = reconcile_provider_observations(adapter, observations)

        self.assertEqual(result["status"], "nonfinal")
        self.assertEqual(result["outcome"], "pending")
        self.assertEqual(result["selectedEvidence"]["source"], "status-api")
        self.assertFalse(result["retryAllowed"])
        self.assertNotIn("reconcileEvent", result)
        self.assertEqual(result["overriddenEvidence"][0]["source"], "webhook")

    def test_higher_precedence_final_evidence_emits_reconcile_event(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        observations = load_provider_observations(FINAL)
        result = reconcile_provider_observations(adapter, observations)

        self.assertEqual(result["status"], "final")
        self.assertEqual(result["outcome"], "committed")
        self.assertEqual(result["selectedEvidence"]["source"], "onchain-state")
        self.assertFalse(result["retryAllowed"])
        self.assertEqual(result["reconcileEvent"]["outcome"], "committed")
        self.assertEqual(result["reconcileEvent"]["evidenceKind"], "onchain-state")

    def test_undeclared_evidence_source_is_rejected(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        observations = load_provider_observations(FINAL)
        observations = copy.deepcopy(observations)
        observations["observations"][0]["source"] = "mystery-source"

        with self.assertRaisesRegex(ProviderAdapterError, "undeclared evidence source"):
            reconcile_provider_observations(adapter, observations)

    def test_precedence_must_cover_every_declared_source(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        adapter = copy.deepcopy(adapter)
        adapter["evidencePrecedence"] = ["onchain-state", "status-api"]

        with self.assertRaisesRegex(ProviderAdapterError, "every evidence source"):
            validate_provider_adapter(adapter)

    def test_non_authoritative_final_state_does_not_unlock_reconciliation(self) -> None:
        adapter = load_provider_adapter(ADAPTER)
        adapter = copy.deepcopy(adapter)
        adapter["evidenceSources"][0]["authoritativeForFinality"] = False
        observations = load_provider_observations(FINAL)
        result = reconcile_provider_observations(adapter, observations)

        self.assertEqual(result["status"], "nonfinal")
        self.assertEqual(result["outcome"], "unknown")
        self.assertFalse(result["retryAllowed"])
        self.assertNotIn("reconcileEvent", result)


if __name__ == "__main__":
    unittest.main()
