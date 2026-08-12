from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.reachability import (  # noqa: E402
    Assumption,
    Capability,
    CapabilityTransition,
    find_shortest_impact_path,
    impact_path_to_dict,
)


class AdversarialReachabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assumptions = [
            Assumption(
                id="fresh-policy-state",
                description="Authorization evaluates the latest spending policy.",
            ),
            Assumption(
                id="unique-settlement",
                description="A logical payment is settled at most once.",
            ),
        ]
        self.capabilities = [
            Capability("request-spend", "Agent may request a spend."),
            Capability("authorized-spend", "A spend request is authorized."),
            Capability("overspend", "Agent can exceed its delegated daily limit.", forbidden=True),
            Capability("duplicate-settlement", "One logical payment can settle twice.", forbidden=True),
        ]
        self.transitions = [
            CapabilityTransition(
                id="authorize-with-stale-policy",
                source="request-spend",
                target="authorized-spend",
                requires_violations=("fresh-policy-state",),
            ),
            CapabilityTransition(
                id="exceed-daily-limit",
                source="authorized-spend",
                target="overspend",
                invariant_id="daily-limit",
                boundary="delegated-spend-policy",
                impact="unauthorized financial loss",
            ),
            CapabilityTransition(
                id="replay-settlement",
                source="authorized-spend",
                target="duplicate-settlement",
                requires_violations=("unique-settlement",),
                invariant_id="settlement-at-most-once",
                boundary="settlement-idempotency",
                impact="duplicate financial settlement",
            ),
        ]

    def test_reachable_impact_requires_broken_assumption(self) -> None:
        path = find_shortest_impact_path(
            initial_capabilities=["request-spend"],
            target_capabilities=["overspend"],
            capabilities=self.capabilities,
            transitions=self.transitions,
            assumptions=self.assumptions,
            violated_assumptions=["fresh-policy-state"],
            max_depth=4,
        )

        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual(
            [edge.id for edge in path.transitions],
            ["authorize-with-stale-policy", "exceed-daily-limit"],
        )
        self.assertEqual(path.invariant_ids, ("daily-limit",))
        self.assertEqual(path.crossed_boundaries, ("delegated-spend-policy",))
        self.assertEqual(path.impact, "unauthorized financial loss")

    def test_missing_violation_keeps_path_unreachable(self) -> None:
        path = find_shortest_impact_path(
            initial_capabilities=["request-spend"],
            target_capabilities=["overspend"],
            capabilities=self.capabilities,
            transitions=self.transitions,
            assumptions=self.assumptions,
            violated_assumptions=[],
        )
        self.assertIsNone(path)

    def test_shortest_reachable_target_is_selected_deterministically(self) -> None:
        transitions = [
            *self.transitions,
            CapabilityTransition(
                id="direct-overspend",
                source="request-spend",
                target="overspend",
                requires_violations=("fresh-policy-state",),
                invariant_id="daily-limit",
                impact="unauthorized financial loss",
            ),
        ]
        path = find_shortest_impact_path(
            initial_capabilities=["request-spend"],
            target_capabilities=["overspend"],
            capabilities=self.capabilities,
            transitions=transitions,
            assumptions=self.assumptions,
            violated_assumptions=["fresh-policy-state"],
        )

        self.assertIsNotNone(path)
        assert path is not None
        self.assertEqual([edge.id for edge in path.transitions], ["direct-overspend"])

    def test_serialization_exposes_capability_escalation_evidence(self) -> None:
        path = find_shortest_impact_path(
            initial_capabilities=["request-spend"],
            target_capabilities=["duplicate-settlement"],
            capabilities=self.capabilities,
            transitions=self.transitions,
            assumptions=self.assumptions,
            violated_assumptions=["fresh-policy-state", "unique-settlement"],
        )

        self.assertIsNotNone(path)
        assert path is not None
        document = impact_path_to_dict(path)
        self.assertEqual(document["targetCapability"], "duplicate-settlement")
        self.assertEqual(document["invariantIds"], ["settlement-at-most-once"])
        self.assertEqual(document["crossedBoundaries"], ["settlement-idempotency"])


if __name__ == "__main__":
    unittest.main()
