from __future__ import annotations

from dataclasses import replace
import unittest

from contractgraph_qa.path_replay import replay_impact_path
from contractgraph_qa.reachability import (
    Assumption,
    Capability,
    CapabilityTransition,
    find_shortest_impact_path,
    ReachabilityModel,
)


class PathReplayHistoricalTargetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assumptions = (
            Assumption("broken-guard", "The historical failing path relies on this break."),
        )
        self.capabilities = (
            Capability("start", "Start."),
            Capability("forbidden-target", "Historical forbidden target.", forbidden=True),
        )
        self.transitions = (
            CapabilityTransition(
                id="reach-target",
                source="start",
                target="forbidden-target",
                requires_violations=("broken-guard",),
                invariant_id="must-remain-safe",
            ),
        )
        path = find_shortest_impact_path(
            initial_capabilities=("start",),
            target_capabilities=("forbidden-target",),
            capabilities=self.capabilities,
            transitions=self.transitions,
            violated_assumptions=("broken-guard",),
            assumptions=self.assumptions,
        )
        self.assertIsNotNone(path)
        assert path is not None
        self.prior_path = path

    def _model(self, capabilities):
        return ReachabilityModel(
            assumptions=self.assumptions,
            capabilities=tuple(capabilities),
            transitions=self.transitions,
            initial_capabilities=("start",),
            target_capabilities=("forbidden-target",),
            violated_assumptions=(),
        )

    def test_removing_historical_target_is_not_accepted_as_fix(self) -> None:
        result = replay_impact_path(
            self.prior_path,
            self._model((Capability("start", "Start."),)),
        )
        self.assertEqual(result["status"], "target_definition_changed")
        self.assertEqual(result["historicalTarget"]["definitionStatus"], "missing")
        self.assertFalse(result["historicalTarget"]["definitionPreserved"])

    def test_relabeling_historical_target_as_allowed_is_not_accepted_as_fix(self) -> None:
        result = replay_impact_path(
            self.prior_path,
            self._model(
                (
                    Capability("start", "Start."),
                    Capability(
                        "forbidden-target",
                        "Historical forbidden target.",
                        forbidden=False,
                    ),
                )
            ),
        )
        self.assertEqual(result["status"], "target_definition_changed")
        self.assertEqual(
            result["historicalTarget"]["definitionStatus"],
            "no_longer_forbidden",
        )
        self.assertFalse(result["alternateReachability"]["stillForbidden"])


if __name__ == "__main__":
    unittest.main()
