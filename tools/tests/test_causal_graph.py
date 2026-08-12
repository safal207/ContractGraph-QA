from __future__ import annotations

import unittest
from pathlib import Path

from contractgraph_qa.causal_graph import (
    CAUSAL_EDGE_RELATIONS,
    build_causal_graph,
    first_invariant_violation,
    path_used_violation_ids,
)
from contractgraph_qa.reachability import find_shortest_impact_path, load_reachability_model


class CausalGraphVocabularyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.wallet = load_reachability_model(
            cls.root / "scenarios" / "adversarial-wallet-replay.json"
        )
        cls.escrow = load_reachability_model(
            cls.root / "scenarios" / "escrow-approval-bypass.json"
        )

    def _path(self, model):
        path = find_shortest_impact_path(
            initial_capabilities=model.initial_capabilities,
            target_capabilities=model.target_capabilities,
            capabilities=model.capabilities,
            transitions=model.transitions,
            violated_assumptions=model.violated_assumptions,
            assumptions=model.assumptions,
            max_depth=model.max_depth,
        )
        self.assertIsNotNone(path)
        assert path is not None
        return path

    def test_graph_uses_shared_relation_vocabulary_deterministically(self) -> None:
        path = self._path(self.wallet)
        first = build_causal_graph(path)
        second = build_causal_graph(path)

        self.assertEqual(first, second)
        self.assertEqual(first["relationVocabulary"], list(CAUSAL_EDGE_RELATIONS))
        relations = {edge["relation"] for edge in first["edges"]}
        self.assertTrue(relations.issubset(set(CAUSAL_EDGE_RELATIONS)))
        self.assertIn("enables", relations)
        self.assertIn("escalates_to", relations)
        self.assertIn("requires", relations)
        self.assertIn("violates", relations)

    def test_first_invariant_violation_records_exact_transition(self) -> None:
        path = self._path(self.escrow)
        marker = first_invariant_violation(path)
        self.assertEqual(
            marker,
            {
                "pathIndex": 1,
                "transitionId": "bypass-approval-threshold",
                "invariantId": "escrow-release-requires-approval",
                "sourceCapability": "request-escrow-release",
                "targetCapability": "release-without-required-approval",
            },
        )
        graph = build_causal_graph(path)
        self.assertEqual(graph["firstInvariantViolation"], marker)
        self.assertIn(
            {
                "source": "transition:bypass-approval-threshold",
                "relation": "violates",
                "target": "invariant:escrow-release-requires-approval",
            },
            graph["edges"],
        )

    def test_used_assumption_violations_exclude_unrelated_declared_breaks(self) -> None:
        path = self._path(self.wallet)
        used = path_used_violation_ids(path)
        expected = tuple(
            sorted(
                {
                    violation
                    for transition in path.transitions
                    for violation in transition.requires_violations
                }
            )
        )
        self.assertEqual(used, expected)
        graph = build_causal_graph(path)
        self.assertEqual(graph["usedAssumptionViolations"], list(expected))

    def test_capability_transition_nodes_preserve_boundary_and_impact(self) -> None:
        graph = build_causal_graph(self._path(self.escrow))
        transition = next(
            node for node in graph["nodes"] if node["id"] == "transition:bypass-approval-threshold"
        )
        self.assertEqual(transition["boundary"], "approval-threshold")
        self.assertEqual(
            transition["impact"],
            "escrow value can be released without the required approval quorum",
        )


if __name__ == "__main__":
    unittest.main()
