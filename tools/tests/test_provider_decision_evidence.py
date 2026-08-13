from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.provider_decision_evidence import (
    ProviderDecisionEvidenceError,
    build_provider_decision_evidence,
    canonical_sha256,
    verify_provider_decision_evidence,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"


class ProviderDecisionEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = json.loads(
            (ADAPTERS / "crossmint-public-contract.v0.1.json").read_text(encoding="utf-8")
        )
        cls.observations = json.loads(
            (ADAPTERS / "crossmint-observations-get-success.json").read_text(encoding="utf-8")
        )
        cls.authority = {
            "status": "authorized",
            "evidenceRef": "fixture://authority/crossmint/evidence-pack",
        }

    def _decision(self) -> dict:
        return evaluate_provider_payment_decision(
            copy.deepcopy(self.adapter),
            copy.deepcopy(self.observations),
            copy.deepcopy(self.authority),
            decision_id="crossmint-evidence-pack-example",
        )

    def _pack(self) -> dict:
        return build_provider_decision_evidence(
            copy.deepcopy(self.adapter),
            copy.deepcopy(self.observations),
            copy.deepcopy(self.authority),
            self._decision(),
        )

    def test_pack_verifies_by_exact_local_replay(self) -> None:
        decision = self._decision()
        pack = build_provider_decision_evidence(
            self.adapter, self.observations, self.authority, decision
        )
        replayed = verify_provider_decision_evidence(pack)
        self.assertEqual(replayed, decision)
        self.assertEqual(replayed["decision"]["decision"], "STOP")
        self.assertFalse(replayed["decision"]["monetaryActionAllowed"])

    def test_canonical_digest_is_key_order_independent(self) -> None:
        left = {"b": 2, "a": {"y": 2, "x": 1}}
        right = {"a": {"x": 1, "y": 2}, "b": 2}
        self.assertEqual(canonical_sha256(left), canonical_sha256(right))

    def test_adapter_tamper_fails_digest_verification(self) -> None:
        pack = self._pack()
        pack["payloads"]["adapter"]["profileVersion"] = "tampered"
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "adapter digest mismatch"):
            verify_provider_decision_evidence(pack)

    def test_observation_tamper_fails_digest_verification(self) -> None:
        pack = self._pack()
        pack["payloads"]["observations"]["observations"][0]["providerState"] = "failed"
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "observations digest mismatch"):
            verify_provider_decision_evidence(pack)

    def test_authority_tamper_fails_digest_verification(self) -> None:
        pack = self._pack()
        pack["payloads"]["authority"]["status"] = "revoked"
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "authority digest mismatch"):
            verify_provider_decision_evidence(pack)

    def test_decision_tamper_fails_digest_verification(self) -> None:
        pack = self._pack()
        pack["payloads"]["providerDecision"]["decision"]["decision"] = "ALLOW"
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "providerDecision digest mismatch"):
            verify_provider_decision_evidence(pack)

    def test_rehashed_semantic_tamper_still_fails_replay(self) -> None:
        pack = self._pack()
        pack["payloads"]["providerDecision"]["decision"]["decision"] = "ALLOW"
        pack["digests"]["providerDecision"] = canonical_sha256(
            pack["payloads"]["providerDecision"]
        )
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "does not exactly match"):
            verify_provider_decision_evidence(pack)

    def test_build_rejects_pre_tampered_decision(self) -> None:
        decision = self._decision()
        decision["decision"]["monetaryActionAllowed"] = True
        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "does not exactly match"):
            build_provider_decision_evidence(
                self.adapter, self.observations, self.authority, decision
            )


if __name__ == "__main__":
    unittest.main()
