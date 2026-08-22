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


class TimeoutRecoveryB003Test(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "scenarios" / "timeout-without-recovery.json"

    def test_timeout_without_recovery_fails_live_002(self) -> None:
        result = run_lifecycle_liveness_model(load_lifecycle_liveness_model(self.path))

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["invariantId"], "CGQ-LIVE-002")
        deadline = next(item for item in result["violations"] if item["state"] == "DeadlineExceeded")
        self.assertEqual(deadline["reason"], "reachable_value_holding_dead_end")
        self.assertEqual(deadline["counterexampleStates"], ["Funded", "DeadlineExceeded"])
        self.assertEqual(deadline["counterexampleTransitions"], ["deadline-expires"])

    def test_refund_recovery_path_restores_liveness(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        fixed = copy.deepcopy(data)
        fixed["transitions"].append(
            {
                "id": "refund-after-timeout",
                "source": "DeadlineExceeded",
                "target": "Refunded",
            }
        )

        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(fixed))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])

    def test_timeout_trap_cycle_still_fails(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        trapped = copy.deepcopy(data)
        trapped["states"].append(
            {
                "id": "TimedReview",
                "description": "Expired escrow is under review but still holds value.",
                "holdsValue": True,
                "safeTerminal": False,
            }
        )
        trapped["transitions"].extend(
            [
                {
                    "id": "open-timeout-review",
                    "source": "DeadlineExceeded",
                    "target": "TimedReview",
                },
                {
                    "id": "review-back-to-timeout",
                    "source": "TimedReview",
                    "target": "DeadlineExceeded",
                },
            ]
        )

        result = run_lifecycle_liveness_model(lifecycle_liveness_model_from_dict(trapped))
        self.assertEqual(result["status"], "fail")
        deadline = next(item for item in result["violations"] if item["state"] == "DeadlineExceeded")
        self.assertEqual(deadline["reason"], "reachable_value_holding_trap")

    def test_b001_and_b003_share_engine_but_keep_distinct_invariant_ids(self) -> None:
        disputed = run_lifecycle_liveness_model(
            load_lifecycle_liveness_model(ROOT / "scenarios" / "escrow-disputed-dead-end.json")
        )
        timeout = run_lifecycle_liveness_model(load_lifecycle_liveness_model(self.path))

        self.assertEqual(disputed["status"], "fail")
        self.assertEqual(timeout["status"], "fail")
        self.assertEqual(disputed["invariantId"], "CGQ-LIVE-001")
        self.assertEqual(timeout["invariantId"], "CGQ-LIVE-002")


if __name__ == "__main__":
    unittest.main()
