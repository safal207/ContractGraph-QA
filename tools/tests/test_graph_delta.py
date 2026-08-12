from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from contractgraph_qa.graph_delta import compare_reachability_models
from contractgraph_qa.reachability import (
    CapabilityTransition,
    load_reachability_model,
)


class ReachabilityGraphDeltaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.base = load_reachability_model(
            cls.root / "scenarios/adversarial-adapter-fixture-before.json"
        )
        cls.head = load_reachability_model(
            cls.root / "scenarios/adversarial-adapter-fixture.json"
        )

    def test_newly_reachable_forbidden_capability_is_reported(self) -> None:
        result = compare_reachability_models(self.base, self.head)
        self.assertEqual(result["status"], "risk_increase_detected")
        self.assertEqual(
            result["newlyReachableForbiddenCapabilities"],
            ["terminal-state-reachable"],
        )
        path = result["introducedForbiddenPaths"]["terminal-state-reachable"]
        self.assertEqual(path["invariantIds"], ["adapter-terminal-state"])
        self.assertEqual(path["crossedBoundaries"], ["terminal-state-boundary"])

    def test_identical_model_has_no_material_delta(self) -> None:
        result = compare_reachability_models(self.head, self.head)
        self.assertEqual(result["status"], "no_material_delta")
        self.assertEqual(result["newlyReachableForbiddenCapabilities"], [])
        self.assertEqual(result["removedDeclaredControlBoundaries"], [])

    def test_removed_declared_boundary_is_reported(self) -> None:
        head_without_boundary = replace(
            self.head,
            transitions=tuple(
                CapabilityTransition(
                    id=edge.id,
                    source=edge.source,
                    target=edge.target,
                    requires_violations=edge.requires_violations,
                    invariant_id=edge.invariant_id,
                    boundary=None,
                    impact=edge.impact,
                )
                for edge in self.head.transitions
            ),
        )
        result = compare_reachability_models(self.head, head_without_boundary)
        self.assertEqual(result["status"], "control_boundary_change")
        self.assertEqual(
            result["removedDeclaredControlBoundaries"],
            ["terminal-state-boundary"],
        )

    def test_fix_that_removes_forbidden_reachability_is_reported(self) -> None:
        result = compare_reachability_models(self.head, self.base)
        self.assertEqual(result["status"], "risk_reduced")
        self.assertEqual(
            result["noLongerReachableForbiddenCapabilities"],
            ["terminal-state-reachable"],
        )


if __name__ == "__main__":
    unittest.main()
