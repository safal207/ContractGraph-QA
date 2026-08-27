from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.active_verification import (  # noqa: E402
    ActiveVerificationError,
    evaluate_active_verification,
    evaluate_cost_observation,
)
from contractgraph_qa.active_verification_cli import main as phase4_cli_main  # noqa: E402
from contractgraph_qa.causal_temporal_utils import canonical_sha256  # noqa: E402
from contractgraph_qa.verification_debt import evaluate_verification_debt  # noqa: E402


class ActiveVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = {"repo": "example/repo", "commit": "abc"}
        self.subject_hash = canonical_sha256(self.subject)

    def _item(
        self,
        work_id: str,
        *,
        risk: float = 1,
        priority: float = 1,
        age: int = 0,
        estimated: float = 1,
        declared: float | None = None,
        observed: float | None = None,
        capacity: int = 1,
        eig: float | None = 1,
        prerequisites: list[str] | None = None,
        required: bool = True,
    ) -> dict[str, object]:
        cost: dict[str, object] = {"estimated": estimated}
        if declared is not None:
            cost["declared"] = declared
        if observed is not None:
            cost["observed"] = observed
            cost["observedReceiptHash"] = f"receipt-{work_id}"
        item: dict[str, object] = {
            "id": work_id,
            "subjectHash": self.subject_hash,
            "capability": work_id,
            "required": required,
            "riskWeight": risk,
            "priority": priority,
            "age": age,
            "capacityUnits": capacity,
            "cost": cost,
            "prerequisites": prerequisites or [],
        }
        if eig is not None:
            item["expectedInformationGain"] = eig
        return item

    def _campaign(self, work: list[dict[str, object]], *, capacity: int = 1, budget: float = 10) -> dict[str, object]:
        return {
            "schema": "cgqa/active-verification/v0.1",
            "subject": self.subject,
            "completedWorkIds": [],
            "policy": {
                "capacityUnits": capacity,
                "budget": budget,
                "requireInformationGain": False,
                "weights": {
                    "risk": 10,
                    "priority": 2,
                    "age": 1,
                    "informationGain": 1,
                    "cost": 1,
                },
            },
            "work": work,
        }

    def _row(self, result: dict[str, object], work_id: str) -> dict[str, object]:
        return next(row for row in result["work"] if row["id"] == work_id)

    def test_high_risk_work_selected_deterministically(self) -> None:
        result = evaluate_active_verification(
            self._campaign([self._item("low", risk=1), self._item("high", risk=5)])
        )
        self.assertEqual(result["selectedWorkIds"], ["high"])
        self.assertFalse(result["selectionIsVerification"])
        self.assertFalse(result["informationGainIsTruth"])

    def test_fake_declared_cost_cannot_force_selection(self) -> None:
        cheap_claim = self._item("cheap-claim", risk=2, estimated=9, declared=0.0001)
        honest = self._item("honest", risk=2, estimated=1, declared=1)
        result = evaluate_active_verification(self._campaign([cheap_claim, honest], budget=10))
        self.assertEqual(result["selectedWorkIds"], ["honest"])
        self.assertEqual(self._row(result, "cheap-claim")["costBasis"], "ESTIMATED_COST")

    def test_observed_cost_has_precedence_over_estimate(self) -> None:
        item = self._item("observed", estimated=100, observed=2)
        result = evaluate_active_verification(self._campaign([item], budget=5))
        row = self._row(result, "observed")
        self.assertEqual(row["costBasis"], "OBSERVED_COST")
        self.assertEqual(row["planningCost"], 2)

    def test_age_provides_anti_starvation_signal(self) -> None:
        fresh = self._item("fresh", risk=2, priority=1, age=0, eig=0)
        old = self._item("old", risk=2, priority=1, age=20, eig=0)
        result = evaluate_active_verification(self._campaign([fresh, old]))
        self.assertEqual(result["selectedWorkIds"], ["old"])

    def test_blocked_prerequisite_is_never_selected(self) -> None:
        blocked = self._item("blocked", risk=100, prerequisites=["foundation"])
        result = evaluate_active_verification(self._campaign([blocked]))
        self.assertEqual(result["selectedWorkIds"], [])
        self.assertEqual(self._row(result, "blocked")["disposition"], "BLOCKED_PREREQUISITE")

    def test_unmodeled_information_value_remains_visible(self) -> None:
        campaign = self._campaign([self._item("unknown-eig", eig=None)])
        campaign["policy"]["requireInformationGain"] = True
        result = evaluate_active_verification(campaign)
        self.assertEqual(self._row(result, "unknown-eig")["disposition"], "UNMODELED_INFORMATION_VALUE")

    def test_capacity_and_budget_defer_without_dropping_work(self) -> None:
        work = [
            self._item("first", risk=5, estimated=4, capacity=1),
            self._item("second", risk=4, estimated=4, capacity=1),
            self._item("oversized", risk=10, estimated=100, capacity=1),
        ]
        result = evaluate_active_verification(self._campaign(work, capacity=1, budget=5))
        dispositions = {row["id"]: row["disposition"] for row in result["work"]}
        self.assertEqual(dispositions["first"], "SELECTED")
        self.assertEqual(dispositions["second"], "DEFERRED_CAPACITY")
        self.assertEqual(dispositions["oversized"], "DEFERRED_OVERSIZED")
        self.assertEqual(set(dispositions), {"first", "second", "oversized"})

    def test_selected_work_remains_verification_debt_until_executed(self) -> None:
        result = evaluate_active_verification(self._campaign([self._item("geometry")]))
        row = self._row(result, "geometry")
        self.assertEqual(row["disposition"], "SELECTED")
        self.assertFalse(row["verified"])
        debt = evaluate_verification_debt(
            {
                "schema": "cgqa/verification-debt/v0.1",
                "subject": self.subject,
                "work": result["verificationDebtReceipts"],
            }
        )
        self.assertEqual(debt["status"], "hold")
        self.assertIn("geometry", debt["unresolvedRequiredIds"])

    def test_stale_subject_work_fails_closed(self) -> None:
        item = self._item("geometry")
        item["subjectHash"] = "f" * 64
        with self.assertRaises(ActiveVerificationError):
            evaluate_active_verification(self._campaign([item]))

    def test_expected_information_gain_is_only_ranking_input(self) -> None:
        high_eig = self._item("high-eig", risk=1, eig=100)
        result = evaluate_active_verification(self._campaign([high_eig]))
        self.assertEqual(result["selectedWorkIds"], ["high-eig"])
        self.assertFalse(result["informationGainIsTruth"])
        self.assertFalse(self._row(result, "high-eig")["verified"])

    def test_cost_observation_preserves_accounting_nonclaim(self) -> None:
        work_payload = {"id": "geometry", "subjectHash": self.subject_hash, "workHash": "work-hash"}
        result = evaluate_cost_observation(
            {
                "schema": "cgqa/verification-cost-observation/v0.1",
                "subject": self.subject,
                "work": work_payload,
                "observation": {
                    "sourceId": "ci-run",
                    "receiptHash": "receipt-hash",
                    "measuredCost": 12.5,
                },
            }
        )
        self.assertEqual(result["observedCost"], 12.5)
        self.assertFalse(result["costIsQuality"])

    def test_cli_output_is_deterministic(self) -> None:
        campaign = self._campaign([self._item("geometry")])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "campaign.json"
            path.write_text(json.dumps(campaign), encoding="utf-8")
            outputs: list[str] = []
            for _ in range(2):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    self.assertEqual(phase4_cli_main(["plan", "--input", str(path)]), 0)
                outputs.append(stdout.getvalue())
            self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
