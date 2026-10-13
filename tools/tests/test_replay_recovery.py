from __future__ import annotations

import unittest
from pathlib import Path

from contractgraph_qa.replay_recovery import (
    ReplayRecoveryError,
    evaluate_replay_recovery_file,
    evaluate_replay_recovery_scenario,
)

ROOT = Path(__file__).resolve().parents[2]
CASE = (
    ROOT
    / "benchmarks"
    / "replay-recovery-idempotence-v0.1"
    / "case-timeout-reconcile-zero.json"
)


def _retry() -> dict[str, str]:
    return {
        "priorLogicalOperationId": "order-42",
        "proposedLogicalOperationId": "order-42",
        "priorExecutionId": "attempt-1",
        "proposedExecutionId": "attempt-2",
        "priorIdempotencyKey": "order-42",
        "proposedIdempotencyKey": "order-42",
    }


def _scenario(evidence: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "cgqa.replay-recovery-scenario.v0.1",
        "scenarioId": "RR-INLINE",
        "actionId": "order-42",
        "effectKey": "broker-order-placement",
        "evidence": evidence,
        "retry": _retry(),
    }


class ReplayRecoveryTest(unittest.TestCase):
    def test_fixture_reconciles_zero_and_allows_policy_retry(self) -> None:
        result = evaluate_replay_recovery_file(CASE)
        self.assertEqual(result["cardinality"], "ZERO")
        self.assertEqual(result["verdict"], "RETRY_ALLOWED")
        self.assertEqual(result["retryIdentity"]["status"], "pass")
        self.assertFalse(result["authority"]["executionAuthorized"])

    def test_incomplete_zero_is_unknown(self) -> None:
        result = evaluate_replay_recovery_scenario(
            _scenario(
                [
                    {
                        "sourceId": "broker-rest",
                        "complete": False,
                        "occurrenceIds": [],
                    }
                ]
            )
        )
        self.assertEqual(result["cardinality"], "UNKNOWN")
        self.assertEqual(result["verdict"], "HOLD_UNRESOLVED")

    def test_incomplete_one_is_still_unknown(self) -> None:
        result = evaluate_replay_recovery_scenario(
            _scenario(
                [
                    {
                        "sourceId": "broker-rest",
                        "complete": False,
                        "occurrenceIds": ["broker-order-1"],
                    }
                ]
            )
        )
        self.assertEqual(result["cardinality"], "UNKNOWN")
        self.assertEqual(result["observed"]["distinctConfirmedOccurrenceCount"], 1)

    def test_complete_one_blocks_retry(self) -> None:
        result = evaluate_replay_recovery_scenario(
            _scenario(
                [
                    {
                        "sourceId": "broker-ledger",
                        "complete": True,
                        "occurrenceIds": ["broker-order-1"],
                    }
                ]
            )
        )
        self.assertEqual(result["cardinality"], "ONE")
        self.assertEqual(result["verdict"], "BLOCK_ALREADY_APPLIED")
        self.assertIsNone(result["retryIdentity"])

    def test_two_partial_confirmations_prove_multiple(self) -> None:
        result = evaluate_replay_recovery_scenario(
            _scenario(
                [
                    {
                        "sourceId": "broker-rest",
                        "complete": False,
                        "occurrenceIds": ["broker-order-1"],
                    },
                    {
                        "sourceId": "execution-feed",
                        "complete": False,
                        "occurrenceIds": ["broker-order-2"],
                    },
                ]
            )
        )
        self.assertEqual(result["cardinality"], "MULTIPLE")
        self.assertEqual(result["verdict"], "BLOCK_DUPLICATE_EFFECT")
        self.assertEqual(result["economicCardinality"]["status"], "fail")

    def test_conflicting_complete_evidence_holds_fail_closed(self) -> None:
        result = evaluate_replay_recovery_scenario(
            _scenario(
                [
                    {
                        "sourceId": "broker-ledger-a",
                        "complete": True,
                        "occurrenceIds": [],
                    },
                    {
                        "sourceId": "broker-ledger-b",
                        "complete": True,
                        "occurrenceIds": ["broker-order-1"],
                    },
                ]
            )
        )
        self.assertEqual(result["cardinality"], "UNKNOWN")
        self.assertEqual(result["verdict"], "HOLD_EVIDENCE_CONFLICT")

    def test_zero_with_changed_idempotency_blocks_retry(self) -> None:
        scenario = _scenario(
            [
                {
                    "sourceId": "broker-ledger",
                    "complete": True,
                    "occurrenceIds": [],
                }
            ]
        )
        retry = dict(_retry())
        retry["proposedIdempotencyKey"] = "order-42-retry"
        scenario["retry"] = retry

        result = evaluate_replay_recovery_scenario(scenario)
        self.assertEqual(result["cardinality"], "ZERO")
        self.assertEqual(result["verdict"], "BLOCK_RETRY_IDENTITY")
        self.assertIn(
            "APR-004_IDEMPOTENCY_CHANGED_ON_RETRY",
            result["retryIdentity"]["violationCodes"],
        )

    def test_duplicate_source_id_is_rejected(self) -> None:
        scenario = _scenario(
            [
                {"sourceId": "same", "complete": False, "occurrenceIds": []},
                {"sourceId": "same", "complete": False, "occurrenceIds": []},
            ]
        )
        with self.assertRaisesRegex(ReplayRecoveryError, "duplicate evidence sourceId"):
            evaluate_replay_recovery_scenario(scenario)


if __name__ == "__main__":
    unittest.main()
