from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "independent_cross_repo_replay.py"
SPEC = importlib.util.spec_from_file_location("independent_cross_repo_replay", MODULE_PATH)
assert SPEC and SPEC.loader
replay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay)

FIXTURE = Path(__file__).resolve().parents[2] / "benchmarks/global-p1-7/authorization-occurrence-consumption.v0.1.json"


class IndependentCrossRepoReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def selected(self):
        request = self.raw["request"]
        return replay.resolve_occurrence(
            self.raw["authorization_occurrences"],
            decision_ref=request["decision_ref"],
            cites_event_id=request["cites_event_id"],
        )

    def test_exact_occurrence_reconstructs_observed_receipt(self) -> None:
        selected = self.selected()
        route_fp = replay.compute_route_fingerprint(selected, self.raw["route"])
        expected = replay.expected_receipt(selected, self.raw["request"], route_fp)
        replay.verify_observed_receipt(self.raw["observed_receipt"], expected)
        self.assertEqual(expected["route_fingerprint"], "fee0b69553abc156b77ad446c3cda8c7f50bbf0efc2cd3aafa75a279016f7930")
        self.assertEqual(expected["receipt_digest"], "690e4852db587c8aa97673ea3b93c5512ffb052ef15de7153604d3a2ff72d72a")

    def test_missing_event_id_with_same_decision_is_ambiguous(self) -> None:
        with self.assertRaisesRegex(replay.IndependentReplayError, "OCCURRENCE_AMBIGUOUS"):
            replay.resolve_occurrence(
                self.raw["authorization_occurrences"],
                decision_ref="decision-A",
                cites_event_id=None,
            )

    def test_unknown_event_id_fails_closed(self) -> None:
        with self.assertRaisesRegex(replay.IndependentReplayError, "OCCURRENCE_NOT_FOUND"):
            replay.resolve_occurrence(
                self.raw["authorization_occurrences"],
                decision_ref="decision-A",
                cites_event_id="evt-missing",
            )

    def test_cross_bound_event_does_not_fallback_to_event_identity(self) -> None:
        records = deepcopy(self.raw["authorization_occurrences"])
        records.append({**records[0], "decision_ref": "decision-B", "cites_event_id": "evt-B"})
        with self.assertRaisesRegex(replay.IndependentReplayError, "OCCURRENCE_NOT_FOUND"):
            replay.resolve_occurrence(records, decision_ref="decision-B", cites_event_id="evt-42")

    def test_route_reordering_fails_closed(self) -> None:
        selected = self.selected()
        bad_route = ["ProofPath", "CML", "RINSE", "LiminalDB", "ContractGraph-QA"]
        with self.assertRaisesRegex(replay.IndependentReplayError, "route order changed"):
            replay.compute_route_fingerprint(selected, bad_route)

    def test_receipt_decision_ref_tamper_is_rejected(self) -> None:
        selected = self.selected()
        route_fp = replay.compute_route_fingerprint(selected, self.raw["route"])
        expected = replay.expected_receipt(selected, self.raw["request"], route_fp)
        observed = deepcopy(expected)
        observed["decision_ref"] = "decision-attacker"
        with self.assertRaisesRegex(replay.IndependentReplayError, "does not match"):
            replay.verify_observed_receipt(observed, expected)

    def test_receipt_route_fingerprint_tamper_is_rejected(self) -> None:
        selected = self.selected()
        route_fp = replay.compute_route_fingerprint(selected, self.raw["route"])
        expected = replay.expected_receipt(selected, self.raw["request"], route_fp)
        observed = deepcopy(expected)
        observed["route_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(replay.IndependentReplayError, "does not match"):
            replay.verify_observed_receipt(observed, expected)

    def test_receipt_digest_tamper_is_rejected(self) -> None:
        selected = self.selected()
        route_fp = replay.compute_route_fingerprint(selected, self.raw["route"])
        expected = replay.expected_receipt(selected, self.raw["request"], route_fp)
        observed = deepcopy(expected)
        observed["receipt_digest"] = "f" * 64
        with self.assertRaisesRegex(replay.IndependentReplayError, "does not match"):
            replay.verify_observed_receipt(observed, expected)

    def test_revision_tamper_changes_cross_repo_subject_fingerprint(self) -> None:
        records = [
            {"component": "proofpath", "repository": "safal207/ProofPath", "revision": "a", "path": "p", "git_blob": "b", "sha256": "c"},
            {"component": "cml", "repository": "safal207/Causal-Memory-Layer", "revision": "d", "path": "q", "git_blob": "e", "sha256": "f"},
        ]
        first = replay.build_subject_fingerprint(records)
        tampered = deepcopy(records)
        tampered[0]["revision"] = "attacker"
        self.assertNotEqual(first, replay.build_subject_fingerprint(tampered))

    def test_raw_subject_tamper_changes_cross_repo_subject_fingerprint(self) -> None:
        records = [
            {"component": "rinse", "repository": "safal207/rinse", "revision": "a", "path": "p", "git_blob": "b", "sha256": "c"},
            {"component": "liminaldb", "repository": "safal207/LiminalDB", "revision": "d", "path": "q", "git_blob": "e", "sha256": "f"},
        ]
        first = replay.build_subject_fingerprint(records)
        tampered = deepcopy(records)
        tampered[0]["sha256"] = "attacker"
        self.assertNotEqual(first, replay.build_subject_fingerprint(tampered))

    def test_duplicate_component_fails_closed(self) -> None:
        records = [
            {"component": "cml", "repository": "one", "revision": "a", "path": "p", "git_blob": "b", "sha256": "c"},
            {"component": "cml", "repository": "two", "revision": "d", "path": "q", "git_blob": "e", "sha256": "f"},
        ]
        with self.assertRaisesRegex(replay.IndependentReplayError, "duplicate component"):
            replay.build_subject_fingerprint(records)


if __name__ == "__main__":
    unittest.main()
