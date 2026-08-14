from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp_v02 import evaluate_fcrp_v02_case
from contractgraph_qa.system_receipt import SystemReceiptError, build_system_receipt


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "governance" / "neo-rezonans-system-snapshot.v0.1.json"
TRACE = ROOT / "benchmarks" / "system-e2e" / "NEO-REZONANS-E2E-001.json"
CASE = ROOT / "benchmarks" / "fcrp-v0.2" / "FCRP-SYSTEM-002-e2e-heartbeat.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SystemReceiptTest(unittest.TestCase):
    def test_canonical_trace_produces_non_authorizing_receipt(self) -> None:
        result = build_system_receipt(load(TRACE), load(SNAPSHOT))
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["stageCount"], 8)
        self.assertEqual(result["transferCount"], 8)
        self.assertTrue(result["identityPreserved"])
        self.assertTrue(result["causalLineagePreserved"])
        self.assertTrue(result["evidenceLineagePreserved"])
        self.assertEqual(result["authorityTransferCount"], 1)
        self.assertEqual(result["authorityLeakCount"], 0)
        self.assertEqual(result["feedbackCount"], 1)
        self.assertFalse(result["sourceMutationObserved"])
        self.assertFalse(result["externalEffectObserved"])
        self.assertEqual(result["finalStatus"], "REFLECTED_WITH_EVIDENCE")
        self.assertTrue(result["receiptDigest"].startswith("sha256:"))

    def test_receipt_is_deterministic(self) -> None:
        a = build_system_receipt(load(TRACE), load(SNAPSHOT))
        b = build_system_receipt(load(TRACE), load(SNAPSHOT))
        self.assertEqual(a, b)

    def test_stage_logical_operation_drift_fails(self) -> None:
        trace = load(TRACE)
        trace["stages"][3]["logicalOperationId"] = "lop:other"
        with self.assertRaisesRegex(SystemReceiptError, "changed logicalOperationId"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_transfer_logical_operation_drift_fails(self) -> None:
        trace = load(TRACE)
        trace["transfers"][4]["logicalOperationId"] = "lop:other"
        with self.assertRaisesRegex(SystemReceiptError, "changed logicalOperationId"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_broken_parent_lineage_fails(self) -> None:
        trace = load(TRACE)
        trace["stages"][5]["parentStageId"] = "S1-RESONANCE-INTENT"
        with self.assertRaisesRegex(SystemReceiptError, "must name previous stage"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_broken_evidence_lineage_fails(self) -> None:
        trace = load(TRACE)
        trace["stages"][6]["inputEvidenceRefs"] = ["evidence:wrong"]
        with self.assertRaisesRegex(SystemReceiptError, "must inherit prior evidence"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_authority_leak_on_non_authority_edge_fails(self) -> None:
        trace = load(TRACE)
        trace["transfers"][4]["authorityTransferred"] = True
        trace["transfers"][4]["authorizationRef"] = "auth:leak"
        with self.assertRaisesRegex(SystemReceiptError, "authority leaked"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_explicit_authority_edge_requires_reference(self) -> None:
        trace = load(TRACE)
        trace["transfers"][3]["authorizationRef"] = None
        with self.assertRaises(SystemReceiptError):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_unknown_transfer_fact_fails(self) -> None:
        trace = load(TRACE)
        trace["transfers"][0]["facts"].append("execution_authority")
        with self.assertRaisesRegex(SystemReceiptError, "facts not allowed"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_feedback_flag_must_match_snapshot(self) -> None:
        trace = load(TRACE)
        trace["transfers"][-1]["feedback"] = False
        with self.assertRaisesRegex(SystemReceiptError, "feedback flag"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_source_mutation_fails(self) -> None:
        trace = load(TRACE)
        trace["stages"][-1]["sourceMutation"] = True
        with self.assertRaisesRegex(SystemReceiptError, "may not mutate source history"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_external_effect_fails(self) -> None:
        trace = load(TRACE)
        trace["stages"][4]["externalEffect"] = True
        with self.assertRaisesRegex(SystemReceiptError, "may not perform an external effect"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_final_reflection_cannot_authorize_execution(self) -> None:
        trace = load(TRACE)
        trace["final"]["executionAuthorized"] = True
        with self.assertRaisesRegex(SystemReceiptError, "may not end with executionAuthorized"):
            build_system_receipt(trace, load(SNAPSHOT))

    def test_fcrp_system_002_passes_without_mutation_authority(self) -> None:
        case = load(CASE)
        result = evaluate_fcrp_v02_case(case)
        self.assertEqual(result["caseId"], "FCRP-SYSTEM-002")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["primaryTimeDomain"], "CAUSAL_SEQUENCE")
        self.assertTrue(result["causalAdvanceRequired"])
        self.assertEqual(result["simulationStatus"], "PASS")
        self.assertFalse(result["mutationAuthorized"])
        self.assertTrue(result["causalPropagationStopped"])
        self.assertEqual(result["decision"], case["expectedProtocolDecision"])


if __name__ == "__main__":
    unittest.main()
