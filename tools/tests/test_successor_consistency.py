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
from contractgraph_qa.successor_consistency import (  # noqa: E402
    load_successor_consistency_model,
    run_successor_consistency_model,
    successor_consistency_model_from_dict,
)


class SuccessorConsistencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "scenarios" / "conflicting-successors-same-parent-version.json"

    def test_b004_two_committed_children_from_same_parent_fail(self) -> None:
        result = run_successor_consistency_model(load_successor_consistency_model(self.path))

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["invariantId"], "CGQ-CONS-001")
        self.assertEqual(len(result["violations"]), 1)
        violation = result["violations"][0]
        self.assertEqual(violation["parentState"], "Funded")
        self.assertEqual(violation["parentVersion"], 7)
        self.assertEqual(violation["distinctCommittedChildCount"], 2)
        self.assertEqual(
            {item["successorState"] for item in violation["successors"]},
            {"Delivered", "Disputed"},
        )

    def test_competing_attempt_not_committed_passes(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fixed = copy.deepcopy(data)
        fixed["commits"][1]["committed"] = False
        result = run_successor_consistency_model(successor_consistency_model_from_dict(fixed))

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["distinctCommittedChildCount"], 1)

    def test_duplicate_observation_of_same_commit_is_deduplicated(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        one = copy.deepcopy(data)
        one["commits"] = [one["commits"][0]]
        duplicate = copy.deepcopy(one["commits"][0])
        duplicate["eventId"] = "evt-deliver-commit-poll"
        one["commits"].append(duplicate)

        result = run_successor_consistency_model(successor_consistency_model_from_dict(one))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["committedObservationCount"], 2)
        self.assertEqual(result["distinctCommittedChildCount"], 1)

    def test_different_parent_versions_are_independent_domains(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        separated = copy.deepcopy(data)
        separated["commits"][1]["parentState"] = "Delivered"
        separated["commits"][1]["parentVersion"] = 8
        separated["commits"][1]["successorState"] = "Disputed"
        separated["commits"][1]["successorVersion"] = 9

        result = run_successor_consistency_model(successor_consistency_model_from_dict(separated))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checkedParentVersionDomains"], 2)

    def test_same_commit_id_with_inconsistent_semantics_is_rejected(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        inconsistent = copy.deepcopy(data)
        inconsistent["commits"][1]["commitId"] = inconsistent["commits"][0]["commitId"]
        with self.assertRaisesRegex(ValueError, "inconsistent static semantics"):
            successor_consistency_model_from_dict(inconsistent)

    def test_result_is_deterministic(self) -> None:
        model = load_successor_consistency_model(self.path)
        first = run_successor_consistency_model(model)
        second = run_successor_consistency_model(model)
        self.assertEqual(first, second)
        self.assertEqual(len(first["modelSha256"]), 64)

    def test_cli_fail_and_pass_exit_codes(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["successor-consistency", "--model", str(self.path)])
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "fail")

        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["commits"][1]["committed"] = False
        passing_path = ROOT / "results" / "generated" / "successor-consistency-test-pass.json"
        passing_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            passing_path.write_text(json.dumps(data), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli_main(["successor-consistency", "--model", str(passing_path)])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "pass")
        finally:
            passing_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
