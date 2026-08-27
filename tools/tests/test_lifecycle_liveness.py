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
from contractgraph_qa.lifecycle_liveness import (  # noqa: E402
    lifecycle_liveness_model_from_dict,
    load_lifecycle_liveness_model,
    run_lifecycle_liveness_model,
)


class LifecycleLivenessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model_path = ROOT / "scenarios" / "escrow-disputed-dead-end.json"
        self.data = json.loads(self.model_path.read_text(encoding="utf-8"))

    def test_repository_fixture_finds_disputed_dead_end(self) -> None:
        model = load_lifecycle_liveness_model(self.model_path)
        first = run_lifecycle_liveness_model(model)
        second = run_lifecycle_liveness_model(model)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "fail")
        self.assertEqual(first["invariantId"], "CGQ-LIVE-001")
        self.assertEqual(len(first["modelSha256"]), 64)
        self.assertEqual(first["safeEconomicTerminals"], ["Refunded", "Released"])

        violations = first["violations"]
        self.assertEqual(len(violations), 1)
        violation = violations[0]
        self.assertEqual(violation["state"], "Disputed")
        self.assertEqual(violation["reason"], "reachable_value_holding_dead_end")
        self.assertEqual(
            violation["counterexampleStates"],
            ["Active", "Funded", "Disputed"],
        )
        self.assertEqual(
            violation["counterexampleTransitions"],
            ["fund", "raise-dispute-from-funded"],
        )

    def test_dispute_resolution_path_restores_liveness(self) -> None:
        data = copy.deepcopy(self.data)
        data["transitions"].append(
            {"id": "resolve-dispute-refund", "source": "Disputed", "target": "Refunded"}
        )

        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(data))

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])

    def test_reachable_value_holding_cycle_without_terminal_is_a_trap(self) -> None:
        data = copy.deepcopy(self.data)
        data["states"].append(
            {
                "id": "Review",
                "description": "Dispute review still holds escrowed value.",
                "holdsValue": True,
                "safeTerminal": False,
            }
        )
        data["transitions"].extend(
            [
                {"id": "dispute-review", "source": "Disputed", "target": "Review"},
                {"id": "review-dispute", "source": "Review", "target": "Disputed"},
            ]
        )

        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(data))

        trapped = {item["state"]: item["reason"] for item in result["violations"]}
        self.assertEqual(trapped["Disputed"], "reachable_value_holding_trap")
        self.assertEqual(trapped["Review"], "reachable_value_holding_trap")

    def test_unreachable_value_holding_dead_end_does_not_create_false_positive(self) -> None:
        data = copy.deepcopy(self.data)
        data["states"].append(
            {
                "id": "Orphaned",
                "description": "Unreachable modeled state that holds value.",
                "holdsValue": True,
                "safeTerminal": False,
            }
        )

        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(data))

        self.assertNotIn("Orphaned", result["reachableStates"])
        self.assertNotIn("Orphaned", [item["state"] for item in result["violations"]])

    def test_model_rejects_safe_terminal_that_still_holds_locked_value(self) -> None:
        data = copy.deepcopy(self.data)
        for state in data["states"]:
            if state["id"] == "Released":
                state["holdsValue"] = True

        with self.assertRaisesRegex(ValueError, "safe terminal state must not hold locked value"):
            lifecycle_liveness_model_from_dict(data)

    def test_cli_returns_validation_exit_on_liveness_failure(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(["lifecycle-liveness", "--model", str(self.model_path)])

        self.assertEqual(exit_code, EXIT_VALIDATION)
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["status"], "fail")
        self.assertEqual(document["violations"][0]["state"], "Disputed")

    def test_cli_returns_ok_after_resolution_path_exists(self) -> None:
        data = copy.deepcopy(self.data)
        data["transitions"].append(
            {"id": "resolve-dispute-release", "source": "Disputed", "target": "Released"}
        )
        model = lifecycle_liveness_model_from_dict(data)
        result = run_lifecycle_liveness_model(model)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])
        self.assertEqual(EXIT_OK, 0)


if __name__ == "__main__":
    unittest.main()
