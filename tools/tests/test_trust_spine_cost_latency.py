from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "benchmarks/global-p2-1/trust-spine-cost-latency.observed.v0.1.json"
PRODUCER_PATH = ROOT / "tools/trust_spine_cost_latency.py"
VERIFIER_PATH = ROOT / "tools/trust_spine_measurement_verifier.py"
VERIFIER_SUBJECT = "1111111111111111111111111111111111111111"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


producer = load_module("trust_spine_cost_latency", PRODUCER_PATH)
verifier = load_module("trust_spine_measurement_verifier", VERIFIER_PATH)


def load_source():
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def reseal_source(source):
    payload = copy.deepcopy(source)
    payload.pop("snapshot_digest", None)
    source["snapshot_digest"] = "sha256:" + producer.sha256_object(payload)
    return source


def reseal_receipt(receipt):
    payload = copy.deepcopy(receipt)
    payload.pop("receipt_digest", None)
    receipt["receipt_digest"] = "sha256:" + producer.sha256_object(payload)
    return receipt


class TrustSpineCostLatencyTests(unittest.TestCase):
    def test_real_run_measurement_is_deterministic_and_bounded(self):
        source = load_source()
        result = producer.measure(source)
        self.assertEqual("PASS", result["decision"])
        self.assertEqual("READ_ONLY_MEASUREMENT_NO_AUTHORITY", result["policy"])
        self.assertEqual(45, result["latency"]["job_elapsed_seconds"])
        self.assertEqual(35, result["latency"]["substantive_window_seconds"])
        self.assertEqual(35, result["latency"]["summed_substantive_step_seconds"])
        self.assertEqual(10, result["latency"]["runner_overhead_seconds"])
        self.assertEqual(13, result["structural_cost"]["substantive_step_count"])
        self.assertEqual(1, result["structural_cost"]["artifact_count"])
        self.assertEqual(28222, result["structural_cost"]["artifact_bytes"])
        groups = {row["group"]: row["observed_seconds"] for row in result["latency"]["measurement_groups"]}
        self.assertEqual(23, groups["liminaldb"])
        self.assertEqual(8, groups["proofpath"])
        self.assertEqual(1, groups["rinse"])
        self.assertEqual({"status": "NOT_MEASURED", "amount_usd": None}, result["monetary_cost"])
        self.assertFalse(result["authority"]["may_authorize"])
        self.assertFalse(result["authority"]["may_execute"])

    def test_independent_verifier_recomputes_without_importing_producer(self):
        source = load_source()
        receipt = producer.measure(source)
        verified = verifier.verify(source, receipt, verifier_subject=VERIFIER_SUBJECT)
        self.assertEqual("PASS", verified["decision"])
        self.assertTrue(verified["measurement_recomputed"])
        self.assertFalse(verified["producer_imported"])
        self.assertEqual("liminaldb", verified["dominant_measurement_group"]["group"])
        self.assertEqual(23, verified["dominant_measurement_group"]["observed_seconds"])
        self.assertEqual(28222, verified["recomputed"]["artifact_bytes"])
        self.assertEqual("NOT_MEASURED", verified["monetary_cost_status"])
        self.assertFalse(verified["authority"]["may_authorize"])
        verifier_source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import trust_spine_cost_latency", verifier_source)
        self.assertNotIn("from tools.trust_spine_cost_latency", verifier_source)

    def test_rejects_reordered_steps(self):
        source = load_source()
        source["substantive_steps"][1], source["substantive_steps"][2] = source["substantive_steps"][2], source["substantive_steps"][1]
        reseal_source(source)
        with self.assertRaises(producer.TrustSpineMeasurementError):
            producer.measure(source)

    def test_rejects_negative_duration(self):
        source = load_source()
        source["substantive_steps"][4]["completed_at"] = "2026-08-15T10:31:48Z"
        reseal_source(source)
        with self.assertRaises(producer.TrustSpineMeasurementError):
            producer.measure(source)

    def test_rejects_stale_measured_subject(self):
        source = load_source()
        source["source"]["head_sha"] = "0" * 40
        reseal_source(source)
        with self.assertRaises(producer.TrustSpineMeasurementError):
            producer.measure(source)

    def test_rejects_fabricated_monetary_cost(self):
        source = load_source()
        source["cost_scope"]["monetary_cost_status"] = "MEASURED"
        source["cost_scope"]["monetary_cost_usd"] = 0.01
        reseal_source(source)
        with self.assertRaises(producer.TrustSpineMeasurementError):
            producer.measure(source)

    def test_rejects_inconsistent_aggregate_even_with_resealed_receipt(self):
        source = load_source()
        receipt = producer.measure(source)
        receipt["latency"]["substantive_window_seconds"] = 99
        reseal_receipt(receipt)
        with self.assertRaises(verifier.TrustSpineVerificationError):
            verifier.verify(source, receipt, verifier_subject=VERIFIER_SUBJECT)

    def test_rejects_receipt_digest_tamper(self):
        source = load_source()
        receipt = producer.measure(source)
        receipt["receipt_digest"] = "sha256:" + "0" * 64
        with self.assertRaises(verifier.TrustSpineVerificationError):
            verifier.verify(source, receipt, verifier_subject=VERIFIER_SUBJECT)

    def test_rejects_authority_escalation_even_with_resealed_receipt(self):
        source = load_source()
        receipt = producer.measure(source)
        receipt["authority"]["may_authorize"] = True
        reseal_receipt(receipt)
        with self.assertRaises(verifier.TrustSpineVerificationError):
            verifier.verify(source, receipt, verifier_subject=VERIFIER_SUBJECT)

    def test_rejects_source_artifact_identity_tamper(self):
        source = load_source()
        source["artifacts"][0]["id"] = 1
        reseal_source(source)
        with self.assertRaises(producer.TrustSpineMeasurementError):
            producer.measure(source)


if __name__ == "__main__":
    unittest.main()
