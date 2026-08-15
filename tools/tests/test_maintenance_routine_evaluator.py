from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "maintenance_routine_evaluator.py"
SPEC = importlib.util.spec_from_file_location("maintenance_routine_evaluator", MODULE_PATH)
assert SPEC and SPEC.loader
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)

MATRIX = Path(__file__).resolve().parents[2] / "benchmarks/global-p2-4/maintenance-routines.v0.1.json"


class MaintenanceRoutineEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.runs = deepcopy(self.matrix["routine_runs"])
        self.subject_heads = {
            subject["repository"]: subject["revision"]
            for subject in self.matrix["subjects"]
        }
        self.verifier_revision = "f" * 40

    def test_two_closed_runs_evaluate(self) -> None:
        receipt = evaluator.evaluate_runs(
            self.runs,
            self.subject_heads,
            verifier_revision=self.verifier_revision,
        )
        self.assertEqual(receipt["decision"], "PASS")
        self.assertEqual(receipt["routine_count"], 2)
        self.assertEqual(receipt["metrics"]["outcome_attribution_pass"], 2)
        self.assertTrue(receipt["all_authority_flags_false"])

    def test_replay_receipt_is_deterministic(self) -> None:
        first = evaluator.evaluate_runs(self.runs, self.subject_heads, verifier_revision=self.verifier_revision)
        second = evaluator.evaluate_runs(self.runs, self.subject_heads, verifier_revision=self.verifier_revision)
        self.assertEqual(first, second)

    def test_stale_target_head_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[0]["target"]["checked_subject"] = "0" * 40
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "stale"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_missing_evidence_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[0]["verification"]["evidence_refs"] = []
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "evidence_refs"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_duplicate_finding_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[1]["observation"]["finding_id"] = tampered[0]["observation"]["finding_id"]
        tampered[1]["routine_run_digest"] = evaluator.expected_run_digest(tampered[1])
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "duplicate finding"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_false_green_replay_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[0]["verification"]["replay"] = "DIFFERENT_RESULT"
        tampered[0]["routine_run_digest"] = evaluator.expected_run_digest(tampered[0])
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "SAME_RESULT"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_wrong_outcome_attribution_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[0]["outcome"]["routine_id"] = "routine-attacker"
        tampered[0]["routine_run_digest"] = evaluator.expected_run_digest(tampered[0])
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "outcome attribution"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_self_authorization_fails_closed(self) -> None:
        tampered = deepcopy(self.runs)
        tampered[0]["authority"]["may_authorize"] = True
        tampered[0]["routine_run_digest"] = evaluator.expected_run_digest(tampered[0])
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "may_authorize"):
            evaluator.evaluate_runs(tampered, self.subject_heads, verifier_revision=self.verifier_revision)

    def test_receipt_tamper_fails_closed(self) -> None:
        receipt = evaluator.evaluate_runs(self.runs, self.subject_heads, verifier_revision=self.verifier_revision)
        receipt["policy"] = "ATTACKER_POLICY"
        with self.assertRaisesRegex(evaluator.MaintenanceRoutineError, "digest mismatch"):
            evaluator.verify_evaluation_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
