from __future__ import annotations

from pathlib import Path
import unittest

from contractgraph_qa.reachability import find_shortest_impact_path, load_reachability_model


class OpenEscrowPartialFundingReachabilityTest(unittest.TestCase):
    def test_partial_funding_can_reach_permanent_principal_lock(self) -> None:
        root = Path(__file__).resolve().parents[2]
        model = load_reachability_model(root / "scenarios" / "openescrow-partial-funding-lock.json")

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
        self.assertEqual(path.initial_capability, "ready-to-fund")
        self.assertEqual(path.target_capability, "permanent-principal-lock")
        self.assertEqual(
            tuple(edge.id for edge in path.transitions),
            (
                "first-tenant-funds",
                "funding-stalls-without-unilateral-exit",
            ),
        )
        self.assertEqual(path.invariant_ids, ("funded-tenant-unilateral-recovery",))
        self.assertIn("escrow-liveness", path.crossed_boundaries)
        self.assertEqual(
            path.impact,
            "previously deposited tenant principal can remain locked indefinitely when a co-tenant and landlord stop progressing the agreement",
        )


if __name__ == "__main__":
    unittest.main()
