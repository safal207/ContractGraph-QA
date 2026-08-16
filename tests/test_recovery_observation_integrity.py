from __future__ import annotations

import unittest

from contractgraph_qa.recovery_observation_integrity import (
    EVIDENCE_BOUNDARY,
    PARENT_SYSTEM_012_HEAD,
    PARENT_SYSTEM_012_RECEIPT_DIGEST,
    RecoveryObservationError,
    finalize_case_receipt,
    run_case,
)


def good_observation(classification: str, decision: str) -> dict:
    generation = 2 if classification == "CONSISTENT_CURRENT" else 1
    return {
        "byteInventory": {
            "main": {"present": True, "digest": "sha256:main"},
            "wal": {"present": classification == "DIVERGENT_READ_VIEWS", "digest": "sha256:wal"},
            "shm": {"present": False, "digest": None},
        },
        "plainRead": {"mode": "plain-ro", "status": "READABLE", "generation": 2 if classification == "DIVERGENT_READ_VIEWS" else generation, "error": None},
        "immutableRead": {"mode": "immutable-ro", "status": "READABLE", "generation": generation, "error": None},
        "producerCommittedGeneration": 2,
        "classification": classification,
        "observationDecision": decision,
        "executionDecision": "HOLD",
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
    }


class RecoveryObservationIntegrityTests(unittest.TestCase):
    def test_live_wal_divergence_is_observed(self) -> None:
        receipt = run_case("live_wal_divergence")
        self.assertEqual(receipt["classification"], "DIVERGENT_READ_VIEWS")
        self.assertEqual(receipt["plainRead"]["generation"], 2)
        self.assertEqual(receipt["immutableRead"]["generation"], 1)
        self.assertEqual(receipt["observationDecision"], "HOLD")
        self.assertEqual(receipt["executionDecision"], "HOLD")

    def test_main_only_snapshot_is_readable_but_stale(self) -> None:
        receipt = run_case("main_db_only_snapshot")
        self.assertEqual(receipt["classification"], "READABLE_STALE_VIEW")
        self.assertEqual(receipt["plainRead"]["generation"], 1)
        self.assertEqual(receipt["immutableRead"]["generation"], 1)
        self.assertEqual(receipt["producerCommittedGeneration"], 2)
        self.assertEqual(receipt["observationDecision"], "HOLD")

    def test_checkpointed_snapshot_is_consistent_current_but_execution_held(self) -> None:
        receipt = run_case("checkpointed_current")
        self.assertEqual(receipt["classification"], "CONSISTENT_CURRENT")
        self.assertEqual(receipt["plainRead"]["generation"], 2)
        self.assertEqual(receipt["immutableRead"]["generation"], 2)
        self.assertEqual(receipt["observationDecision"], "ACCEPT_OBSERVATION")
        self.assertEqual(receipt["executionDecision"], "HOLD")
        self.assertFalse(receipt["authorityClaimed"])

    def test_parent_head_drift_rejected(self) -> None:
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(
                case="checkpointed_current",
                observation=good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION"),
                parent_head="deadbeef",
            )

    def test_parent_receipt_drift_rejected(self) -> None:
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(
                case="checkpointed_current",
                observation=good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION"),
                parent_receipt_digest="sha256:deadbeef",
            )

    def test_evidence_boundary_promotion_rejected(self) -> None:
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(
                case="checkpointed_current",
                observation=good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION"),
                evidence_boundary="OBSERVATION_PROVES_AUTHORITY",
            )

    def test_observation_cannot_claim_authority(self) -> None:
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(
                case="checkpointed_current",
                observation=good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION"),
                authority_claimed=True,
            )

    def test_divergent_views_cannot_be_accepted(self) -> None:
        observation = good_observation("DIVERGENT_READ_VIEWS", "ACCEPT_OBSERVATION")
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(case="live_wal_divergence", observation=observation)

    def test_readable_stale_view_cannot_be_accepted(self) -> None:
        observation = good_observation("READABLE_STALE_VIEW", "ACCEPT_OBSERVATION")
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(case="main_db_only_snapshot", observation=observation)

    def test_execution_escalation_rejected(self) -> None:
        observation = good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION")
        observation["executionDecision"] = "ALLOW_FORK"
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(case="checkpointed_current", observation=observation)

    def test_authority_transfer_rejected(self) -> None:
        observation = good_observation("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION")
        observation["authorityTransfer"] = "OBSERVER"
        with self.assertRaises(RecoveryObservationError):
            finalize_case_receipt(case="checkpointed_current", observation=observation)

    def test_constants_are_pinned(self) -> None:
        self.assertEqual(PARENT_SYSTEM_012_HEAD, "82ff749eba2d257cfbebf873b52ec152c5b4664a")
        self.assertEqual(PARENT_SYSTEM_012_RECEIPT_DIGEST, "sha256:a7ea56e8d8b9515301bf7f99e20c2817eb9848f2279aaa969c2ab08b25c42563")
        self.assertEqual(EVIDENCE_BOUNDARY, "RECOVERY_OBSERVATION_MODE_NOT_AUTHORITY")


if __name__ == "__main__":
    unittest.main()
