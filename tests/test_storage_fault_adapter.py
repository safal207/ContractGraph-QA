from __future__ import annotations

import copy
import unittest

from contractgraph_qa.storage_fault_adapter import (
    EVIDENCE_BOUNDARY,
    EXPECTED,
    PARENT_RECOVERY_RECEIPT_DIGEST,
    PARENT_SYSTEM_008_HEAD,
    StorageFaultError,
    finalize_storage_fault_receipt,
    run_fault_case,
    run_matrix,
)


class StorageFaultAdapterTests(unittest.TestCase):
    def test_matrix_matches_contract(self) -> None:
        rows = run_matrix()
        self.assertEqual(len(rows), len(EXPECTED))
        for row in rows:
            expected = EXPECTED[row["case"]]
            self.assertEqual(
                (row["projectionState"], row["rebuildDecision"], row["executionDecision"]),
                expected,
            )
            self.assertEqual(row["evidenceBoundary"], EVIDENCE_BOUNDARY)

    def test_future_projection_is_fail_closed(self) -> None:
        observation, receipt = run_fault_case("projection_future_generation")
        self.assertEqual(observation["projectionState"], "UNPROVABLE")
        self.assertEqual(receipt["rebuildDecision"], "HOLD")
        self.assertEqual(receipt["executionDecision"], "HOLD")

    def test_corrupt_authority_is_fail_closed(self) -> None:
        observation, receipt = run_fault_case("authority_header_corrupt")
        self.assertEqual(observation["authority"]["integrity"], "CORRUPT")
        self.assertEqual(receipt["rebuildDecision"], "HOLD")
        self.assertFalse(receipt["executionAuthorized"])

    def test_orphan_temp_candidate_never_becomes_authority(self) -> None:
        observation, receipt = run_fault_case("orphan_temp_candidate")
        self.assertEqual(observation["tempCandidate"]["generation"], 3)
        self.assertEqual(observation["projection"]["generation"], 2)
        self.assertEqual(observation["authority"]["generation"], 3)
        self.assertFalse(receipt["tempCandidateAuthority"])
        self.assertEqual(receipt["rebuildDecision"], "ALLOW_REBUILD")
        self.assertEqual(receipt["executionDecision"], "HOLD")

    def test_parent_recovery_receipt_pin_cannot_drift(self) -> None:
        observation, _ = run_fault_case("healthy")
        with self.assertRaises(StorageFaultError):
            finalize_storage_fault_receipt(
                case="healthy",
                observation=observation,
                parent_head=PARENT_SYSTEM_008_HEAD,
                parent_receipt_digest=PARENT_RECOVERY_RECEIPT_DIGEST[:-1] + "0",
            )

    def test_physical_power_loss_claim_is_rejected(self) -> None:
        observation, _ = run_fault_case("healthy")
        with self.assertRaises(StorageFaultError):
            finalize_storage_fault_receipt(
                case="healthy",
                observation=observation,
                evidence_boundary="PHYSICAL_POWER_LOSS_PROVEN",
            )

    def test_execution_authority_escalation_is_rejected(self) -> None:
        observation, _ = run_fault_case("projection_truncated")
        escalated = copy.deepcopy(observation)
        escalated["executionAuthorized"] = True
        with self.assertRaises(StorageFaultError):
            finalize_storage_fault_receipt(
                case="projection_truncated",
                observation=escalated,
            )


if __name__ == "__main__":
    unittest.main()
