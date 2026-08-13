from __future__ import annotations

import unittest

from contractgraph_qa.reachability import (
    Assumption,
    Capability,
    CapabilityTransition,
    ReachabilityModel,
    find_shortest_impact_path,
    run_reachability_model,
)


class ReachabilityPathViolationScopeTest(unittest.TestCase):
    def test_path_reports_only_violations_required_by_selected_transitions(self) -> None:
        assumptions = (
            Assumption("required-break", "The selected path requires this break."),
            Assumption("unrelated-break", "This break is declared but not used by the path."),
        )
        capabilities = (
            Capability("start", "Start capability."),
            Capability("forbidden", "Forbidden target.", forbidden=True),
        )
        transitions = (
            CapabilityTransition(
                id="cross-boundary",
                source="start",
                target="forbidden",
                requires_violations=("required-break",),
                invariant_id="must-hold",
            ),
        )

        path = find_shortest_impact_path(
            initial_capabilities=("start",),
            target_capabilities=("forbidden",),
            capabilities=capabilities,
            transitions=transitions,
            violated_assumptions=("required-break", "unrelated-break"),
            assumptions=assumptions,
        )

        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.violated_assumptions, ("required-break",))

        result = run_reachability_model(
            ReachabilityModel(
                assumptions=assumptions,
                capabilities=capabilities,
                transitions=transitions,
                initial_capabilities=("start",),
                target_capabilities=("forbidden",),
                violated_assumptions=("required-break", "unrelated-break"),
            )
        )
        self.assertEqual(
            result["violatedAssumptions"],
            ["required-break", "unrelated-break"],
        )
        self.assertEqual(result["path"]["violatedAssumptions"], ["required-break"])

    def test_zero_length_target_path_uses_no_assumption_violations(self) -> None:
        path = find_shortest_impact_path(
            initial_capabilities=("already-target",),
            target_capabilities=("already-target",),
            capabilities=(Capability("already-target", "Existing target.", forbidden=True),),
            transitions=(),
            violated_assumptions=("irrelevant",),
            assumptions=(Assumption("irrelevant", "Declared but unused."),),
            max_depth=0,
        )
        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(path.violated_assumptions, ())


if __name__ == "__main__":
    unittest.main()
