from __future__ import annotations

import unittest

from tools.ancestry_gate import HOLD, INCOMPLETE, NOT_RUN, PASS, evaluate_gate


SUBJECT = "a" * 40
BASE = "b" * 40
WORKFLOW_FILE = ".github/workflows/fcrp-p0-4-ancestry-gate.yml"


def evaluate(**overrides):
    values = {
        "initial_subject": SUBJECT,
        "final_subject": SUBJECT,
        "expected_subject": SUBJECT,
        "expected_base": BASE,
        "ancestry": True,
        "workflow_name": "FCRP P0-4 Ancestry Gate",
        "workflow_ref": f"safal207/ContractGraph-QA/{WORKFLOW_FILE}@refs/pull/61/merge",
        "run_id": "123",
        "run_attempt": "1",
        "expected_workflow_file": WORKFLOW_FILE,
        "artifact_subject": SUBJECT,
    }
    values.update(overrides)
    return evaluate_gate(**values)


class AncestryGateTests(unittest.TestCase):
    def test_all_machine_checks_pass(self) -> None:
        report = evaluate()
        self.assertEqual(report["decision"], PASS)
        self.assertTrue(all(item["status"] == PASS for item in report["checks"].values()))

    def test_initial_subject_change_is_hold(self) -> None:
        report = evaluate(initial_subject="c" * 40)
        self.assertEqual(report["decision"], HOLD)
        self.assertEqual(report["checks"]["initial_subject"]["status"], HOLD)

    def test_final_subject_change_is_hold(self) -> None:
        report = evaluate(final_subject="c" * 40)
        self.assertEqual(report["decision"], HOLD)
        self.assertEqual(report["checks"]["final_subject"]["status"], HOLD)

    def test_non_ancestor_is_hold(self) -> None:
        report = evaluate(ancestry=False)
        self.assertEqual(report["decision"], HOLD)
        self.assertEqual(report["checks"]["ancestry"]["status"], HOLD)

    def test_unavailable_ancestry_is_not_run(self) -> None:
        report = evaluate(ancestry=None)
        self.assertEqual(report["decision"], NOT_RUN)
        self.assertEqual(report["checks"]["ancestry"]["status"], NOT_RUN)

    def test_missing_workflow_identity_is_incomplete(self) -> None:
        report = evaluate(workflow_ref="")
        self.assertEqual(report["decision"], INCOMPLETE)
        self.assertEqual(report["checks"]["workflow_identity"]["status"], INCOMPLETE)

    def test_artifact_subject_mismatch_is_hold(self) -> None:
        report = evaluate(artifact_subject="d" * 40)
        self.assertEqual(report["decision"], HOLD)
        self.assertEqual(report["checks"]["artifact_subject"]["status"], HOLD)


if __name__ == "__main__":
    unittest.main()
