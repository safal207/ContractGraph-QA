from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.causal_temporal_utils import canonical_sha256  # noqa: E402
from contractgraph_qa.proof_integrity import (  # noqa: E402
    build_durable_manifest,
    evaluate_evidence_readiness,
    evaluate_metamorphic,
    evaluate_root_cause,
    evaluate_subject_freeze,
    evaluate_trace_integrity,
    evaluate_verification_plan,
    verify_durable_manifest,
)
from contractgraph_qa.proof_integrity_cli import main as phase3_cli_main  # noqa: E402


class Phase3ProofIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = {"repo": "example/repo", "commit": "abc"}
        self.subject_hash = canonical_sha256(self.subject)

    def test_exact_subject_freeze_passes_only_when_unchanged(self) -> None:
        base = {
            "schema": "cgqa/subject-freeze/v0.1",
            "subjectBefore": self.subject,
            "subjectAfter": dict(self.subject),
        }
        self.assertEqual(evaluate_subject_freeze(base)["classification"], "UNCHANGED")
        base["subjectAfter"] = {"repo": "example/repo", "commit": "def"}
        self.assertEqual(evaluate_subject_freeze(base)["classification"], "STALE_SUBJECT")

    def _plan_core(self) -> dict[str, object]:
        return {
            "subjectHash": self.subject_hash,
            "invariants": ["conservation"],
            "forbiddenStates": ["double-effect"],
            "capabilities": ["geometry", "ancestry"],
            "negativeControls": ["remove-terminal-guard"],
            "bounds": {"maxDepth": 6, "seed": 7},
        }

    def test_preregistered_plan_passes_exact_result(self) -> None:
        plan = self._plan_core()
        model = {
            "schema": "cgqa/verification-plan/v0.1",
            "plan": plan,
            "amendments": [],
            "result": {
                "planHash": canonical_sha256(plan),
                "subjectHash": self.subject_hash,
                "executedCapabilities": ["geometry"],
                "bounds": dict(plan["bounds"]),
            },
        }
        self.assertEqual(evaluate_verification_plan(model)["status"], "pass")

    def test_post_hoc_bound_drift_fails(self) -> None:
        plan = self._plan_core()
        model = {
            "schema": "cgqa/verification-plan/v0.1",
            "plan": plan,
            "amendments": [],
            "result": {
                "planHash": canonical_sha256(plan),
                "subjectHash": self.subject_hash,
                "executedCapabilities": ["geometry"],
                "bounds": {"maxDepth": 99, "seed": 7},
            },
        }
        self.assertIn("POST_HOC_BOUND_DRIFT", evaluate_verification_plan(model)["reasons"])

    def test_append_only_plan_amendment_is_explicit(self) -> None:
        base = self._plan_core()
        amended = {**base, "bounds": {"maxDepth": 8, "seed": 7}}
        model = {
            "schema": "cgqa/verification-plan/v0.1",
            "plan": base,
            "amendments": [
                {
                    "fromPlanHash": canonical_sha256(base),
                    "toPlan": amended,
                    "reason": "new bounded counterexample requires two more steps",
                }
            ],
            "result": {
                "planHash": canonical_sha256(amended),
                "subjectHash": self.subject_hash,
                "executedCapabilities": ["geometry"],
                "bounds": dict(amended["bounds"]),
            },
        }
        result = evaluate_verification_plan(model)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["amendments"]), 1)

    def _trace(self) -> dict[str, object]:
        return {
            "schema": "cgqa/trace-integrity/v0.1",
            "subject": self.subject,
            "completeExpected": True,
            "events": [
                {"eventId": "e0", "sequence": 0, "subjectHash": self.subject_hash},
                {
                    "eventId": "e1",
                    "sequence": 1,
                    "subjectHash": self.subject_hash,
                    "predecessorId": "e0",
                },
                {
                    "eventId": "e2",
                    "sequence": 2,
                    "subjectHash": self.subject_hash,
                    "predecessorId": "e1",
                },
            ],
        }

    def test_trace_integrity_passes_contiguous_chain(self) -> None:
        self.assertEqual(evaluate_trace_integrity(self._trace())["status"], "pass")

    def test_trace_gap_without_marker_fails(self) -> None:
        model = self._trace()
        model["events"][2]["sequence"] = 3
        codes = {row["code"] for row in evaluate_trace_integrity(model)["reasons"]}
        self.assertIn("UNMARKED_TRACE_GAP", codes)

    def test_trace_duplicate_event_fails(self) -> None:
        model = self._trace()
        model["events"][2]["eventId"] = "e1"
        codes = {row["code"] for row in evaluate_trace_integrity(model)["reasons"]}
        self.assertIn("DUPLICATE_EVENT_ID", codes)

    def test_foreign_subject_event_fails(self) -> None:
        model = self._trace()
        model["events"][1]["subjectHash"] = "f" * 64
        codes = {row["code"] for row in evaluate_trace_integrity(model)["reasons"]}
        self.assertIn("FOREIGN_SUBJECT_EVENT", codes)

    def _evidence(self) -> dict[str, object]:
        return {
            "schema": "cgqa/evidence-readiness/v0.1",
            "subject": self.subject,
            "evidence": [
                {
                    "id": "w1",
                    "class": "WITNESSED",
                    "subjectHash": self.subject_hash,
                    "sourceType": "DIRECT_OBSERVATION",
                    "replayable": True,
                    "fresh": True,
                    "independent": True,
                },
                {
                    "id": "counter-1",
                    "class": "COUNTEREVIDENCE",
                    "subjectHash": self.subject_hash,
                    "sourceType": "DIRECT_OBSERVATION",
                    "replayable": True,
                    "fresh": True,
                    "independent": True,
                },
            ],
            "requirements": {
                "requireFresh": True,
                "requireReplayable": True,
                "expectedCounterevidenceIds": ["counter-1"],
            },
        }

    def test_evidence_readiness_ready_is_not_truth_probability(self) -> None:
        result = evaluate_evidence_readiness(self._evidence())
        self.assertEqual(result["readiness"], "READY")
        self.assertIsNone(result["truthProbability"])

    def test_reflected_claim_cannot_masquerade_as_witnessed(self) -> None:
        model = self._evidence()
        model["evidence"][0]["sourceType"] = "HOST_REPORT"
        result = evaluate_evidence_readiness(model)
        self.assertEqual(result["readiness"], "UNSTABLE")
        self.assertIn("FALSE_WITNESS_CLASS", {row["code"] for row in result["hardFindings"]})

    def test_expected_counterevidence_cannot_be_silently_omitted(self) -> None:
        model = self._evidence()
        model["evidence"] = [model["evidence"][0]]
        result = evaluate_evidence_readiness(model)
        self.assertIn("COUNTEREVIDENCE_OMITTED", {row["code"] for row in result["hardFindings"]})

    def test_root_cause_collapses_downstream_symptoms(self) -> None:
        model = {
            "schema": "cgqa/root-cause-collapse/v0.1",
            "findings": [
                {"id": "root", "invariant": "auth"},
                {"id": "symptom-a", "invariant": "value"},
                {"id": "symptom-b", "invariant": "terminality"},
            ],
            "edges": [
                {"from": "root", "to": "symptom-a", "relation": "CAUSES"},
                {"from": "root", "to": "symptom-b", "relation": "CAUSES"},
            ],
        }
        result = evaluate_root_cause(model)
        self.assertEqual(result["independentRootCount"], 1)
        self.assertEqual(result["roots"][0]["downstreamFindingIds"], ["symptom-a", "symptom-b"])

    def test_independent_roots_are_not_collapsed(self) -> None:
        model = {
            "schema": "cgqa/root-cause-collapse/v0.1",
            "findings": [
                {"id": "a", "invariant": "auth"},
                {"id": "b", "invariant": "conservation"},
            ],
            "edges": [],
        }
        self.assertEqual(evaluate_root_cause(model)["independentRootCount"], 2)

    def _metamorphic(self) -> dict[str, object]:
        endpoint = {
            "subjectHash": self.subject_hash,
            "state": {"balance": 10},
            "effects": {"payout": 0},
            "history": {"generation": 2},
        }
        return {
            "schema": "cgqa/metamorphic-roundtrip/v0.1",
            "subject": self.subject,
            "cases": [
                {
                    "id": "persist-reopen",
                    "before": endpoint,
                    "after": json.loads(json.dumps(endpoint)),
                    "preserve": {"state": True, "effects": True, "history": True},
                }
            ],
        }

    def test_metamorphic_round_trip_passes(self) -> None:
        self.assertEqual(evaluate_metamorphic(self._metamorphic())["status"], "pass")

    def test_history_loss_during_round_trip_fails(self) -> None:
        model = self._metamorphic()
        model["cases"][0]["after"]["history"] = {}
        result = evaluate_metamorphic(model)
        self.assertEqual(result["status"], "fail")
        self.assertIn("history", result["cases"][0]["mismatches"])

    def test_durable_reopen_verifies_bytes_and_detects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "finding.json").write_text('{"status":"pass"}', encoding="utf-8")
            (root / "trace.json").write_text('{"events":[1,2]}', encoding="utf-8")
            manifest = build_durable_manifest(root, ["finding.json", "trace.json"])
            self.assertEqual(verify_durable_manifest(root, manifest)["status"], "pass")
            (root / "trace.json").write_text('{"events":[1,2,3]}', encoding="utf-8")
            result = verify_durable_manifest(root, manifest)
            self.assertEqual(result["status"], "fail")
            self.assertIn("SHA256_MISMATCH", {row["code"] for row in result["reasons"]})

    def test_phase3_cli_deterministic(self) -> None:
        model = {
            "schema": "cgqa/subject-freeze/v0.1",
            "subjectBefore": self.subject,
            "subjectAfter": self.subject,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "freeze.json"
            path.write_text(json.dumps(model), encoding="utf-8")
            outputs: list[str] = []
            for _ in range(2):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(phase3_cli_main(["freeze", "--input", str(path)]), 0)
                outputs.append(stdout.getvalue())
            self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
