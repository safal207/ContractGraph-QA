from __future__ import annotations

import copy
import unittest

from tools.negative_path_matrix import (
    ACCEPT,
    BLOCK,
    MatrixError,
    build_case_specs,
    evaluate_case,
    run_matrix,
    verify_matrix,
)


SUBJECT = "a" * 40
PROOFPATH = "b" * 40


class NegativePathMatrixTests(unittest.TestCase):
    def test_matrix_has_accept_control_and_fail_closed_negative_cases(self) -> None:
        inputs, result = run_matrix(
            checked_subject=SUBJECT,
            proofpath_head=PROOFPATH,
            now="2026-08-14T08:02:00Z",
        )
        verify_matrix(
            inputs,
            result,
            expected_subject=SUBJECT,
            expected_proofpath_head=PROOFPATH,
        )
        self.assertGreaterEqual(result["coverage"]["accept_control_cases"], 1)
        self.assertGreaterEqual(result["coverage"]["blocked_cases"], 10)
        self.assertEqual(result["coverage"]["executed_cases"], 0)
        self.assertEqual(result["coverage"]["replay_stable_cases"], result["coverage"]["total_cases"])

    def test_each_declared_case_matches_its_expected_decision(self) -> None:
        cases = build_case_specs()
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        for case in cases:
            observation = evaluate_case(case, now="2026-08-14T08:02:00Z")
            self.assertEqual(observation["observed_decision"], case["expected_decision"])
            self.assertEqual(observation["observed_reason"], case["expected_reason"])
            self.assertFalse(observation["side_effect_executed"])
            self.assertTrue(observation["replayable"])

    def test_tampered_result_is_rejected(self) -> None:
        inputs, result = run_matrix(
            checked_subject=SUBJECT,
            proofpath_head=PROOFPATH,
            now="2026-08-14T08:02:00Z",
        )
        tampered = copy.deepcopy(result)
        tampered["cases"][1]["observed_decision"] = ACCEPT
        with self.assertRaisesRegex(MatrixError, "not reproducible"):
            verify_matrix(
                inputs,
                tampered,
                expected_subject=SUBJECT,
                expected_proofpath_head=PROOFPATH,
            )

    def test_stale_subject_is_rejected(self) -> None:
        inputs, result = run_matrix(
            checked_subject=SUBJECT,
            proofpath_head=PROOFPATH,
            now="2026-08-14T08:02:00Z",
        )
        with self.assertRaisesRegex(MatrixError, "subject is stale"):
            verify_matrix(
                inputs,
                result,
                expected_subject="c" * 40,
                expected_proofpath_head=PROOFPATH,
            )

    def test_negative_cases_are_blocked(self) -> None:
        observations = [
            evaluate_case(case, now="2026-08-14T08:02:00Z")
            for case in build_case_specs()
            if case["expected_decision"] == BLOCK
        ]
        self.assertTrue(observations)
        self.assertTrue(all(item["observed_decision"] == BLOCK for item in observations))


if __name__ == "__main__":
    unittest.main()
