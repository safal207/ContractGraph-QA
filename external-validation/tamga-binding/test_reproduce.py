"""Offline regression tests for the historical Tamga result oracle.

Importing the local reproducer does not execute its main function or fetch/run
any upstream code. These tests exercise result comparison and offline packet
validation; main-boundary tests mock fetching and subprocess execution.
"""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


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


class OfflineSourcePacketTests(unittest.TestCase):
    @staticmethod
    def valid_contents():
        return {key: "Исторический источник — café\n" for key in reproduce.FILES}

    def load_document(self, document):
        with tempfile.TemporaryDirectory(prefix="tamga-packet-test-") as temporary:
            packet_path = Path(temporary) / "packet.json"
            packet_path.write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            return reproduce.load_source_packet(packet_path)

    def test_absent_packet_intentionally_selects_online_mode(self):
        self.assertIsNone(reproduce.load_source_packet(None))

    def test_valid_packet_returns_unicode_contents(self):
        contents = self.valid_contents()
        self.assertEqual(self.load_document({"contents": contents}), contents)

    def test_invalid_top_level_documents_are_rejected(self):
        for document in (None, {}, [], False, True, 1, "packet"):
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    self.load_document(document)

    def test_invalid_contents_shapes_are_rejected(self):
        for contents in (None, [], False, True, 1, "contents"):
            with self.subTest(contents=contents):
                with self.assertRaises(ValueError):
                    self.load_document({"contents": contents})

    def test_empty_contents_are_rejected(self):
        with self.assertRaises(ValueError):
            self.load_document({"contents": {}})

    def test_every_required_source_must_be_present(self):
        for missing_key in reproduce.FILES:
            with self.subTest(missing_key=missing_key):
                contents = self.valid_contents()
                del contents[missing_key]
                with self.assertRaises(ValueError):
                    self.load_document({"contents": contents})

    def test_every_required_source_must_be_a_string(self):
        for key in reproduce.FILES:
            for invalid_value in (None, False, True, 1, [], {}):
                with self.subTest(key=key, value=invalid_value):
                    contents = self.valid_contents()
                    contents[key] = invalid_value
                    with self.assertRaises(ValueError):
                        self.load_document({"contents": contents})

    def test_invalid_offline_packet_never_fetches_or_executes_at_main_boundary(self):
        incomplete_contents = self.valid_contents()
        del incomplete_contents[next(iter(reproduce.FILES))]
        nonstring_contents = self.valid_contents()
        nonstring_contents[next(iter(reproduce.FILES))] = False
        invalid_documents = (
            None,
            {},
            [],
            False,
            {"contents": None},
            {"contents": []},
            {"contents": False},
            {"contents": {}},
            {"contents": incomplete_contents},
            {"contents": nonstring_contents},
        )
        with tempfile.TemporaryDirectory(prefix="tamga-main-packet-test-") as temporary:
            packet_path = Path(temporary) / "packet.json"
            for document in invalid_documents:
                with self.subTest(document=document):
                    packet_path.write_text(json.dumps(document), encoding="utf-8")
                    with (
                        mock.patch.object(reproduce, "urlopen") as fetch,
                        mock.patch.object(reproduce.subprocess, "run") as execute,
                        mock.patch.object(
                            reproduce.sys,
                            "argv",
                            ["reproduce.py", "--source-packet", str(packet_path)],
                        ),
                    ):
                        with self.assertRaises(ValueError):
                            reproduce.main()
                        fetch.assert_not_called()
                        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
