"""Offline regression tests for the historical Tamga result oracle.

Importing the local reproducer does not execute its main function or fetch/run
any upstream code. These tests exercise only result comparison.
"""
import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).with_name("reproduce.py")
SPEC = importlib.util.spec_from_file_location("tamga_reproduce", MODULE_PATH)
reproduce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reproduce)


SUCCESS = {
    "ok": True,
    "receiptHash": "36a8c38609c5e8d0dc89167581ef48122111bdcc8f831aecb3631834285214d6",
    "stdout_sha256": "c7023eda7dab3faf782149158fa55583a4f57cd3a230092da1933688d05f94be",
    "checks": [
        "labeling",
        "membership",
        "delivery_sha256",
        "delivery_keccak256",
        "input_sha256",
    ],
}
MEMBERSHIP_ERROR = {
    "ok": False,
    "where": "membership",
    "error": "recomputed h != receiptHash or charge.h",
}
INPUT_ERROR = {
    "ok": False,
    "where": "input_commitment",
    "error": "sha256(input.json) != fixture commitment or charge.input_sha256",
}


class MatchesExpectedResultTests(unittest.TestCase):
    def test_exact_success_is_accepted(self):
        self.assertTrue(
            reproduce.matches_expected_result(copy.deepcopy(SUCCESS), SUCCESS, 0, "")
        )

    def test_exact_errors_are_accepted(self):
        for expected in (MEMBERSHIP_ERROR, INPUT_ERROR):
            with self.subTest(where=expected["where"]):
                self.assertTrue(
                    reproduce.matches_expected_result(
                        copy.deepcopy(expected), expected, 1, ""
                    )
                )

    def test_missing_success_fields_are_rejected(self):
        # Checking only ok/where accepted these incomplete successful payloads.
        for field in SUCCESS:
            with self.subTest(field=field):
                outcome = copy.deepcopy(SUCCESS)
                del outcome[field]
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, SUCCESS, 0, "")
                )

    def test_changed_success_hashes_are_rejected(self):
        for field in ("receiptHash", "stdout_sha256"):
            with self.subTest(field=field):
                outcome = copy.deepcopy(SUCCESS)
                outcome[field] = "0" * 64
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, SUCCESS, 0, "")
                )

    def test_changed_success_checks_are_rejected(self):
        variants = (
            [],
            SUCCESS["checks"][:-1],
            list(reversed(SUCCESS["checks"])),
            SUCCESS["checks"] + ["invented_check"],
        )
        for checks in variants:
            with self.subTest(checks=checks):
                outcome = copy.deepcopy(SUCCESS)
                outcome["checks"] = checks
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, SUCCESS, 0, "")
                )

    def test_missing_failure_fields_are_rejected(self):
        for field in MEMBERSHIP_ERROR:
            with self.subTest(field=field):
                outcome = copy.deepcopy(MEMBERSHIP_ERROR)
                del outcome[field]
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, MEMBERSHIP_ERROR, 1, "")
                )

    def test_changed_failure_error_is_rejected(self):
        # The previous oracle accepted any error text at the expected where.
        outcome = copy.deepcopy(MEMBERSHIP_ERROR)
        outcome["error"] = "an unrelated failure"
        self.assertFalse(
            reproduce.matches_expected_result(outcome, MEMBERSHIP_ERROR, 1, "")
        )

    def test_changed_failure_location_is_rejected(self):
        outcome = copy.deepcopy(MEMBERSHIP_ERROR)
        outcome["where"] = "input_commitment"
        self.assertFalse(
            reproduce.matches_expected_result(outcome, MEMBERSHIP_ERROR, 1, "")
        )

    def test_extra_success_and_failure_fields_are_rejected(self):
        for expected, exit_code, field, value in (
            (SUCCESS, 0, "where", None),
            (SUCCESS, 0, "unexpected", "extra data"),
            (MEMBERSHIP_ERROR, 1, "unexpected", "extra data"),
        ):
            with self.subTest(ok=expected["ok"], field=field):
                outcome = copy.deepcopy(expected)
                outcome[field] = value
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, expected, exit_code, "")
                )

    def test_integer_ok_does_not_alias_boolean_ok(self):
        # Python dictionary equality alone considers 1 == True and 0 == False.
        for expected, numeric_ok, exit_code in (
            (SUCCESS, 1, 0),
            (MEMBERSHIP_ERROR, 0, 1),
        ):
            with self.subTest(numeric_ok=numeric_ok):
                outcome = copy.deepcopy(expected)
                outcome["ok"] = numeric_ok
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, expected, exit_code, "")
                )

    def test_opposite_boolean_ok_is_rejected(self):
        for expected, exit_code in ((SUCCESS, 0), (MEMBERSHIP_ERROR, 1)):
            with self.subTest(expected_ok=expected["ok"]):
                outcome = copy.deepcopy(expected)
                outcome["ok"] = not expected["ok"]
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, expected, exit_code, "")
                )

    def test_wrong_exit_codes_are_rejected(self):
        for expected, wrong_codes in (
            (SUCCESS, (1, 2, -9)),
            (MEMBERSHIP_ERROR, (0, 2, -9)),
        ):
            for exit_code in wrong_codes:
                with self.subTest(ok=expected["ok"], exit_code=exit_code):
                    self.assertFalse(
                        reproduce.matches_expected_result(
                            copy.deepcopy(expected), expected, exit_code, ""
                        )
                    )

    def test_any_stderr_is_rejected(self):
        for expected, exit_code in ((SUCCESS, 0), (MEMBERSHIP_ERROR, 1)):
            for stderr in ("warning", "\n", " "):
                with self.subTest(ok=expected["ok"], stderr=stderr):
                    self.assertFalse(
                        reproduce.matches_expected_result(
                            copy.deepcopy(expected), expected, exit_code, stderr
                        )
                    )

    def test_non_dictionary_outcomes_are_rejected(self):
        for outcome in (None, True, 1, "success", [], [SUCCESS]):
            with self.subTest(outcome=outcome):
                self.assertFalse(
                    reproduce.matches_expected_result(outcome, SUCCESS, 0, "")
                )


if __name__ == "__main__":
    unittest.main()
