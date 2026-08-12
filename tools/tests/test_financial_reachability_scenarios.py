from __future__ import annotations

import unittest
from pathlib import Path

from contractgraph_qa.reachability import load_reachability_model, run_reachability_model


class FinancialReachabilityScenarioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.scenarios = {
            "escrow-approval-bypass": ("release-without-required-approval", "escrow-release-requires-approval", "approval-threshold"),
            "stale-authority": ("spend-under-stale-authority", "payment-authority-must-be-current", "authority-freshness"),
            "revoked-authority": ("spend-after-revocation", "revoked-authority-cannot-spend", "authority-revocation"),
            "idempotency-replay": ("create-second-payment-attempt", "retry-must-preserve-idempotency", "idempotency-continuity"),
            "duplicate-settlement": ("apply-duplicate-settlement", "settlement-applied-once", "settlement-deduplication"),
        }

    def test_financial_scenarios_reach_declared_forbidden_target(self) -> None:
        for name, (target, invariant, boundary) in self.scenarios.items():
            with self.subTest(name=name):
                model = load_reachability_model(self.root / "scenarios" / f"{name}.json")
                result = run_reachability_model(model)
                self.assertEqual(result["status"], "reachable")
                path = result["path"]
                self.assertEqual(path["targetCapability"], target)
                self.assertEqual(path["invariantIds"], [invariant])
                self.assertEqual(path["crossedBoundaries"], [boundary])
                self.assertEqual(len(path["transitions"]), 1)


if __name__ == "__main__":
    unittest.main()
