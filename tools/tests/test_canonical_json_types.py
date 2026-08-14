from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.provider_decision_evidence import (
    ProviderDecisionEvidenceError,
    build_provider_decision_evidence,
    canonical_json_bytes,
    canonical_evidence_pack_sha256,
    verify_provider_decision_evidence,
)
from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"


class CanonicalJsonTypeTest(unittest.TestCase):
    def test_monetary_action_boolean_false_is_distinct_from_numeric_zero(self) -> None:
        self.assertNotEqual(
            canonical_json_bytes({"monetaryActionAllowed": False}),
            canonical_json_bytes({"monetaryActionAllowed": 0}),
        )

    def test_expected_pack_digest_mismatch_is_rejected(self) -> None:
        adapter = json.loads(
            (ADAPTERS / "crossmint-public-contract.v0.1.json").read_text(encoding="utf-8")
        )
        observations = json.loads(
            (ADAPTERS / "crossmint-observations-get-success.json").read_text(encoding="utf-8")
        )
        authority = {
            "status": "authorized",
            "evidenceRef": "fixture://authority/crossmint/external-digest-test",
        }
        decision = evaluate_provider_payment_decision(
            adapter,
            observations,
            authority,
            decision_id="crossmint-external-digest-test",
        )
        pack = build_provider_decision_evidence(adapter, observations, authority, decision)
        actual_digest = canonical_evidence_pack_sha256(pack)
        wrong_digest = "0" * 64 if actual_digest != "0" * 64 else "f" * 64

        with self.assertRaisesRegex(ProviderDecisionEvidenceError, "external digest mismatch"):
            verify_provider_decision_evidence(
                pack,
                expected_pack_sha256=wrong_digest,
            )


if __name__ == "__main__":
    unittest.main()
