from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main as cli_main  # noqa: E402
from contractgraph_qa.economic_cardinality import (  # noqa: E402
    economic_cardinality_model_from_dict,
    load_economic_cardinality_model,
    run_economic_cardinality_model,
)


class EconomicCardinalityTest(unittest.TestCase):
    def test_b002_distinct_occurrences_fail(self) -> None:
        model = load_economic_cardinality_model(
            ROOT / "scenarios" / "replay-duplicate-economic-effect.json"
        )
        result = run_economic_cardinality_model(model)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["invariantId"], "CGQ-SAFE-001")
        self.assertEqual(len(result["violations"]), 1)
        violation = result["violations"][0]
        self.assertEqual(violation["actionId"], "release:A")
        self.assertEqual(violation["distinctAppliedOccurrenceCount"], 2)
        self.assertEqual(
            violation["minimalCounterexampleEventIds"],
            ["evt-release-accepted", "evt-release-replay-accepted"],
        )

    def test_duplicate_observation_of_same_occurrence_passes(self) -> None:
        data = {
            "schemaVersion": "economic-cardinality.v0.1",
            "modelId": "same-settlement-observed-twice",
            "invariantId": "CGQ-SAFE-001",
            "events": [
                {
                    "eventId": "webhook-1",
                    "actionId": "release:A",
                    "effectKey": "escrow-release-settlement",
                    "occurrenceId": "tx-123",
                    "applied": True,
                },
                {
                    "eventId": "poll-1",
                    "actionId": "release:A",
                    "effectKey": "escrow-release-settlement",
                    "occurrenceId": "tx-123",
                    "applied": True,
                },
            ],
        }
        result = run_economic_cardinality_model(economic_cardinality_model_from_dict(data))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])

    def test_distinct_effect_keys_are_independent_slots(self) -> None:
        data = {
            "schemaVersion": "economic-cardinality.v0.1",
            "modelId": "multi-leg-action",
            "invariantId": "CGQ-SAFE-001",
            "events": [
                {
                    "eventId": "payout",
                    "actionId": "release:A",
                    "effectKey": "seller-payout",
                    "occurrenceId": "ledger-1",
                    "applied": True,
                },
                {
                    "eventId": "fee",
                    "actionId": "release:A",
                    "effectKey": "platform-fee",
                    "occurrenceId": "ledger-2",
                    "applied": True,
                },
            ],
        }
        result = run_economic_cardinality_model(economic_cardinality_model_from_dict(data))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checkedActionEffectPairs"], 2)

    def test_unapplied_attempt_does_not_count_as_economic_effect(self) -> None:
        data = {
            "schemaVersion": "economic-cardinality.v0.1",
            "modelId": "rejected-replay",
            "invariantId": "CGQ-SAFE-001",
            "events": [
                {
                    "eventId": "first",
                    "actionId": "release:A",
                    "effectKey": "escrow-release-settlement",
                    "occurrenceId": "settlement-1",
                    "applied": True,
                },
                {
                    "eventId": "replay-rejected",
                    "actionId": "release:A",
                    "effectKey": "escrow-release-settlement",
                    "occurrenceId": "attempt-2",
                    "applied": False,
                },
            ],
        }
        result = run_economic_cardinality_model(economic_cardinality_model_from_dict(data))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checkedAppliedEventCount"], 1)

    def test_result_is_deterministic(self) -> None:
        model = load_economic_cardinality_model(
            ROOT / "scenarios" / "replay-duplicate-economic-effect.json"
        )
        self.assertEqual(
            run_economic_cardinality_model(model),
            run_economic_cardinality_model(model),
        )
        self.assertEqual(len(run_economic_cardinality_model(model)["modelSha256"]), 64)

    def test_loader_rejects_duplicate_event_id_and_schema_drift(self) -> None:
        path = ROOT / "scenarios" / "replay-duplicate-economic-effect.json"
        data = json.loads(path.read_text(encoding="utf-8"))

        duplicate = copy.deepcopy(data)
        duplicate["events"][1]["eventId"] = duplicate["events"][0]["eventId"]
        with self.assertRaisesRegex(ValueError, "duplicate eventId"):
            economic_cardinality_model_from_dict(duplicate)

        drift = copy.deepcopy(data)
        drift["events"][0]["surprise"] = "nope"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            economic_cardinality_model_from_dict(drift)

    def test_cli_fail_and_pass_exit_codes(self) -> None:
        failing = ROOT / "scenarios" / "replay-duplicate-economic-effect.json"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["economic-cardinality", "--model", str(failing)])
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "fail")

        passing_data = {
            "schemaVersion": "economic-cardinality.v0.1",
            "modelId": "pass",
            "invariantId": "CGQ-SAFE-001",
            "events": [],
        }
        passing_path = ROOT / "results" / "generated" / "economic-cardinality-test-pass.json"
        passing_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            passing_path.write_text(json.dumps(passing_data), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli_main(["economic-cardinality", "--model", str(passing_path)])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "pass")
        finally:
            passing_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
