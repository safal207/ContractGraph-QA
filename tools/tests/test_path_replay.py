from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from contractgraph_qa.path_replay import replay_prior_model_path
from contractgraph_qa.reachability import CapabilityTransition, load_reachability_model


class PriorPathReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.before = load_reachability_model(
            cls.root / "scenarios/adversarial-adapter-fixture-before.json"
        )
        cls.failing = load_reachability_model(
            cls.root / "scenarios/adversarial-adapter-fixture.json"
        )

    def test_exact_prior_path_persists_without_fix(self) -> None:
        result = replay_prior_model_path(self.failing, self.failing)
        self.assertEqual(result["status"], "failing_path_persists")
        self.assertTrue(result["exactReplay"]["reachedForbiddenCapability"])
        self.assertTrue(result["alternateReachability"]["reachable"])

    def test_fix_verified_when_prior_path_and_target_are_no_longer_reachable(self) -> None:
        result = replay_prior_model_path(self.failing, self.before)
        self.assertEqual(result["status"], "fix_verified")
        self.assertFalse(result["exactReplay"]["reachedForbiddenCapability"])
        self.assertFalse(result["alternateReachability"]["reachable"])
        self.assertEqual(
            result["exactReplay"]["blockedAt"]["reason"],
            "assumption_guard_restored",
        )

    def test_blocked_exact_path_does_not_claim_fix_when_alternate_path_remains(self) -> None:
        original = self.failing.transitions[0]
        alternate = CapabilityTransition(
            id="alternate-terminal-path",
            source=original.source,
            target=original.target,
            requires_violations=(),
            invariant_id=original.invariant_id,
            boundary="alternate-terminal-boundary",
            impact=original.impact,
        )
        fixed = replace(
            self.failing,
            transitions=(replace(original, requires_violations=("terminal-transition-blocked",)), alternate),
            violated_assumptions=(),
        )
        result = replay_prior_model_path(self.failing, fixed)
        self.assertEqual(result["status"], "path_eliminated_but_risk_remains")
        self.assertEqual(
            result["exactReplay"]["blockedAt"]["reason"],
            "assumption_guard_restored",
        )
        self.assertTrue(result["alternateReachability"]["reachable"])
        self.assertEqual(
            result["alternateReachability"]["path"]["transitions"][0]["id"],
            "alternate-terminal-path",
        )

    def test_missing_prior_transition_is_evidence_of_exact_path_elimination(self) -> None:
        fixed = replace(self.failing, transitions=())
        result = replay_prior_model_path(self.failing, fixed)
        self.assertEqual(result["status"], "fix_verified")
        self.assertEqual(
            result["exactReplay"]["blockedAt"]["reason"],
            "transition_missing",
        )


if __name__ == "__main__":
    unittest.main()
