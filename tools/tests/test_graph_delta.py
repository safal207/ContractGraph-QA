from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from contractgraph_qa.graph_delta import compare_reachability_models
from contractgraph_qa.reachability import (
    Capability,
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
        self.assertEqual(result["gateReasons"], ["new_forbidden_reachability"])
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
        self.assertEqual(result["gateReasons"], [])
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
        self.assertEqual(
            result["forbiddenDefinitionChanges"]["forbiddenToAllowedCapabilities"],
            [],
        )

    def test_relabeling_forbidden_capability_as_allowed_fails_gate(self) -> None:
        reclassified = replace(
            self.head,
            capabilities=tuple(
                Capability(
                    item.id,
                    item.description,
                    forbidden=False if item.id == "terminal-state-reachable" else item.forbidden,
                )
                for item in self.head.capabilities
            ),
        )
        result = compare_reachability_models(self.head, reclassified)
        self.assertEqual(result["status"], "risk_increase_detected")
        self.assertEqual(result["gateReasons"], ["forbidden_definition_changed"])
        self.assertEqual(
            result["forbiddenDefinitionChanges"]["forbiddenToAllowedCapabilities"],
            ["terminal-state-reachable"],
        )

    def test_removing_forbidden_capability_fails_gate(self) -> None:
        without_target = replace(
            self.head,
            capabilities=tuple(
                item
                for item in self.head.capabilities
                if item.id != "terminal-state-reachable"
            ),
            transitions=tuple(
                edge
                for edge in self.head.transitions
                if edge.source != "terminal-state-reachable"
                and edge.target != "terminal-state-reachable"
            ),
            target_capabilities=("advance-state-machine",),
        )
        result = compare_reachability_models(self.head, without_target)
        self.assertEqual(result["status"], "risk_increase_detected")
        self.assertEqual(result["gateReasons"], ["forbidden_definition_changed"])
        self.assertEqual(
            result["forbiddenDefinitionChanges"]["removedFormerlyForbiddenCapabilities"],
            ["terminal-state-reachable"],
        )


if __name__ == "__main__":
    unittest.main()
