from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.payment_evidence_pack import (
    PaymentEvidencePackError,
    build_payment_evidence_pack,
    verify_payment_evidence_pack,
)

ROOT = Path(__file__).resolve().parents[2]
DEMO = (
    ROOT
    / "benchmarks"
    / "agent-payment-recovery-v0.1"
    / "customer-evidence-pack"
    / "demo-timeout-settled-fulfillment-unknown.json"
)


class PaymentEvidencePackTest(unittest.TestCase):
    def test_demo_blocks_new_money_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "pack.zip"
            built = build_payment_evidence_pack(DEMO, pack)
            self.assertEqual(built["decision"], "RECONCILE")
            self.assertFalse(built["monetaryActionAllowed"])

            verified = verify_payment_evidence_pack(pack)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["decision"], "RECONCILE")
            self.assertFalse(verified["monetaryActionAllowed"])

    def test_same_input_produces_byte_identical_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.zip"
            second = Path(tmp) / "second.zip"
            build_payment_evidence_pack(DEMO, first)
            build_payment_evidence_pack(DEMO, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_decision_tamper_is_rejected_even_if_zip_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "original.zip"
            tampered = Path(tmp) / "tampered.zip"
            build_payment_evidence_pack(DEMO, original)

            with zipfile.ZipFile(original, "r") as source:
                blobs = {name: source.read(name) for name in source.namelist()}
            decision = json.loads(blobs["decision.json"])
            decision["decision"] = "ALLOW"
            decision["monetaryActionAllowed"] = True
            blobs["decision.json"] = (
                json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")

            with zipfile.ZipFile(tampered, "w") as target:
                for name in ["input.json", "decision.json", "customer-summary.md", "manifest.json"]:
                    target.writestr(name, blobs[name])

            with self.assertRaises(PaymentEvidencePackError):
                verify_payment_evidence_pack(tampered)


if __name__ == "__main__":
    unittest.main()
