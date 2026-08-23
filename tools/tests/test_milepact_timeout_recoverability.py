from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.lifecycle_liveness import (  # noqa: E402
    lifecycle_liveness_model_from_dict,
    load_lifecycle_liveness_model,
    run_lifecycle_liveness_model,
)


class MilepactTimeoutRecoverabilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "scenarios" / "milepact-funded-timeout-client-unavailable.json"

    def test_client_unavailable_timeout_branch_fails_live_002(self) -> None:
        result = run_lifecycle_liveness_model(load_lifecycle_liveness_model(self.path))

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["invariantId"], "CGQ-LIVE-002")
        violation = next(
            item for item in result["violations"]
            if item["state"] == "FundedAfterDeadlineClientUnavailable"
        )
        self.assertEqual(violation["reason"], "reachable_value_holding_dead_end")
        self.assertEqual(
            violation["counterexampleStates"],
            ["Funded", "FundedAfterDeadlineClientUnavailable"],
        )
        self.assertEqual(
            violation["counterexampleTransitions"],
            ["deadline-elapses-client-unavailable"],
        )

    def test_independent_timeout_recovery_restores_pass(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fixed = copy.deepcopy(data)
        fixed["transitions"].append(
            {
                "id": "independent-refund-after-timeout",
                "source": "FundedAfterDeadlineClientUnavailable",
                "target": "Refunded",
            }
        )
        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(fixed))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])


if __name__ == "__main__":
    unittest.main()
