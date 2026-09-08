from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from contractgraph_qa.trading_recovery import (
    TradingRecoveryError,
    evaluate_trading_recovery_replay,
)

ROOT = Path(__file__).resolve().parents[2]
CASE = (
    ROOT
    / "benchmarks"
    / "trading-recovery-replay-v0.1"
    / "cases"
    / "failed-zero-retry-allowed.json"
)


def _base() -> dict:
    return json.loads(CASE.read_text(encoding="utf-8"))


def _committed_one() -> dict:
    payload = _base()
    payload["scenarioId"] = "TRR-COMMITTED-ONE"
    payload["recoveryScenario"]["events"][-1]["outcome"] = "committed"
    payload["cardinalityModel"]["events"] = [
        {
            "eventId": "exchange-observation-1",
            "actionId": "order:btc-001",
            "effectKey": "exchange-order-acceptance",
            "occurrenceId": "exchange-order-777",
            "applied": True,
        }
    ]
    return payload


class TradingRecoveryReplayTest(unittest.TestCase):
    def test_failed_and_complete_zero_allows_policy_retry_but_never_execution(self) -> None:
        result = evaluate_trading_recovery_replay(_base())
        self.assertEqual(result["stateCardinality"], "ZERO")
        self.assertEqual(result["retryVerdict"], "RETRY_ALLOWED")
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["authority"]["financialAuthorization"])
        self.assertFalse(result["authority"]["liveExecution"])

    def test_committed_one_blocks_retry(self) -> None:
        result = evaluate_trading_recovery_replay(_committed_one())
        self.assertEqual(result["stateCardinality"], "ONE")
        self.assertEqual(result["retryVerdict"], "BLOCK_ALREADY_APPLIED")
        self.assertFalse(result["executionAuthorized"])

    def test_unresolved_reconciliation_holds(self) -> None:
        payload = _base()
        payload["recoveryScenario"]["events"][-1]["outcome"] = "unknown"
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "UNKNOWN")
        self.assertEqual(result["retryVerdict"], "HOLD_UNRESOLVED")

    def test_incomplete_effect_evidence_cannot_prove_zero(self) -> None:
        payload = _base()
        payload["evidencePolicy"]["effectEvidenceComplete"] = False
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "UNKNOWN")
        self.assertEqual(
            result["retryVerdict"], "HOLD_EFFECT_EVIDENCE_INCOMPLETE"
        )

    def test_non_authoritative_reconciliation_cannot_release_retry(self) -> None:
        payload = _base()
        payload["evidencePolicy"]["reconciliationAuthoritative"] = False
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "UNKNOWN")
        self.assertEqual(
            result["retryVerdict"], "HOLD_NON_AUTHORITATIVE_RECONCILIATION"
        )

    def test_two_distinct_applied_occurrences_block_as_duplicate(self) -> None:
        payload = _committed_one()
        second = copy.deepcopy(payload["cardinalityModel"]["events"][0])
        second["eventId"] = "exchange-observation-2"
        second["occurrenceId"] = "exchange-order-888"
        payload["cardinalityModel"]["events"].append(second)
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "MULTIPLE")
        self.assertEqual(result["retryVerdict"], "BLOCK_DUPLICATE_EFFECT")

    def test_failed_reconcile_with_one_applied_occurrence_holds_conflict(self) -> None:
        payload = _base()
        payload["cardinalityModel"]["events"] = [
            {
                "eventId": "late-observation",
                "actionId": "order:btc-001",
                "effectKey": "exchange-order-acceptance",
                "occurrenceId": "exchange-order-late",
                "applied": True,
            }
        ]
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "UNKNOWN")
        self.assertEqual(result["retryVerdict"], "HOLD_EVIDENCE_CONFLICT")

    def test_retry_before_reconciliation_blocks_recovery_invariant(self) -> None:
        payload = _base()
        payload["recoveryScenario"]["events"].insert(
            3,
            {
                "seq": 4,
                "type": "retry",
                "logicalOperationId": "order-btc-001",
                "executionId": "attempt-b",
                "retryOfExecutionId": "attempt-a",
                "idempotencyKey": "order-btc-001",
            },
        )
        payload["recoveryScenario"]["events"][-1]["seq"] = 5
        result = evaluate_trading_recovery_replay(payload)
        self.assertEqual(result["stateCardinality"], "UNKNOWN")
        self.assertEqual(result["retryVerdict"], "BLOCK_RECOVERY_INVARIANT")
        self.assertIn(
            "APR-001_UNRESOLVED_AMBIGUITY_FINANCIAL_ACTION",
            result["observed"]["recoveryViolationCodes"],
        )

    def test_policy_flags_are_required_booleans(self) -> None:
        payload = _base()
        payload["evidencePolicy"]["effectEvidenceComplete"] = "yes"
        with self.assertRaisesRegex(TradingRecoveryError, "must be boolean"):
            evaluate_trading_recovery_replay(payload)


if __name__ == "__main__":
    unittest.main()
