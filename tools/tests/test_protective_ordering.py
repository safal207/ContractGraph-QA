from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.protective_ordering import (  # noqa: E402
    load_protective_ordering_model,
    protective_ordering_model_from_dict,
    protective_ordering_model_sha256,
    run_protective_ordering_model,
)


class ProtectiveOrderingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "scenarios" / "milepact-protective-ordering-race.json"

    def test_mp05_fails_when_auto_release_defeats_valid_dispute(self) -> None:
        model = load_protective_ordering_model(self.path)
        result = run_protective_ordering_model(model)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["invariantId"], "CGQ-RACE-001")
        self.assertTrue(result["orderingSensitiveOutcome"])
        self.assertEqual(
            result["counterexample"]["sequence"],
            ["autoRelease", "raiseDispute"],
        )
        self.assertEqual(result["counterexample"]["finalState"], "Released")
        self.assertEqual(result["counterexample"]["protectiveActionResult"], "reverted")
        self.assertFalse(result["counterexample"]["protectiveRightPreserved"])

    def test_protective_priority_restores_pass(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fixed = copy.deepcopy(data)
        for ordering in fixed["orderings"]:
            ordering["finalState"] = "Disputed"
            ordering["protectiveActionResult"] = "committed"
            ordering["competingActionResult"] = "reverted"
            ordering["economicOutcome"] = "protective_dispute_preserved"
            ordering["protectiveRightPreserved"] = True

        result = run_protective_ordering_model(protective_ordering_model_from_dict(fixed))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])
        self.assertFalse(result["orderingSensitiveOutcome"])

    def test_missing_business_guarantee_is_inconclusive_not_false_pass(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["protectiveActionMustRemainEffectiveAcrossOrdering"] = False
        result = run_protective_ordering_model(protective_ordering_model_from_dict(data))
        self.assertEqual(result["status"], "inconclusive")

    def test_actions_not_jointly_enabled_is_inconclusive(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["bothEnabledAtParent"] = False
        result = run_protective_ordering_model(protective_ordering_model_from_dict(data))
        self.assertEqual(result["status"], "inconclusive")

    def test_model_hash_is_deterministic(self) -> None:
        model = load_protective_ordering_model(self.path)
        self.assertEqual(protective_ordering_model_sha256(model), protective_ordering_model_sha256(model))

    def test_duplicate_ordering_is_rejected(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["orderings"][1]["sequence"] = list(data["orderings"][0]["sequence"])
        with self.assertRaisesRegex(ValueError, "duplicate ordering sequence"):
            protective_ordering_model_from_dict(data)


if __name__ == "__main__":
    unittest.main()
