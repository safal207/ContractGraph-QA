from __future__ import annotations

import copy
import unittest

from contractgraph_qa.recovery_integrity_adapter import (
    CML_INFORMATION_FITNESS_COMMIT,
    CML_REPOSITORY,
    RecoveryIntegrityBridgeError,
    build_recovery_integrity_scig,
    finalize_recovery_integrity_receipt,
)


RESONANCE_COMMIT = "361b93cb773779afe24ca38e28d0ac22c60a93b6"


def source_record() -> dict:
    return {
        "protocol_version": "recovery-integrity-v0.1",
        "recovery_id": "process-crash-after_authority_commit",
        "source_case_ref": "local://process-crash/after_authority_commit",
        "authority": {
            "source_ref": "/tmp/authority.sqlite3",
            "generation": 2,
            "integrity": "VALID",
        },
        "projection": {
            "source_ref": "/tmp/projection.json",
            "generation": 1,
            "state": "STALE",
            "preserved_broken_ref": "/tmp/projection.json",
        },
        "rollout": {
            "source_ref": None,
            "integrity": "UNKNOWN",
            "continuation_proof": "NOT_PROVEN",
        },
        "last_committed_action_ref": None,
        "pending_action_ref": None,
        "external_side_effect_state": "UNKNOWN",
        "current_authority_proof": "NOT_PROVEN",
        "decision": {
            "rebuild_projection": "ALLOW_REBUILD",
            "execution_continuation": "HOLD",
        },
        "evidence_refs": [
            "authority_generation=2",
            "projection_generation=1",
        ],
        "verifier": {
            "verifier_id": "recovery-integrity-process-crash-harness-v0.1",
            "mode": "read-only",
        },
        "pre_recovery_snapshot_ref": "/tmp",
        "post_recovery_snapshot_ref": None,
        "observed_outcome": {
            "status": "HELD",
            "outcome_ref": "classification-only; no rebuild or continuation executed",
        },
    }


def cml_result() -> dict:
    return {
        "repository": CML_REPOSITORY,
        "commit": CML_INFORMATION_FITNESS_COMMIT,
        "status": "READY_FOR_AUTHORITY_CHECK",
        "readyForAuthorityCheck": True,
        "authorizesAction": False,
        "reasons": ["recovery_record_exact_source_validated"],
    }


class RecoveryIntegrityAdapterTests(unittest.TestCase):
    def test_positive_receipt_keeps_execution_held(self) -> None:
        record = source_record()
        scig = build_recovery_integrity_scig(
            record,
            resonance_commit=RESONANCE_COMMIT,
            observed_at="2026-08-15T12:06:58Z",
        )
        stdout = (
            f"SCIG {scig['incident_id']}\n"
            "RESULT VALID\n"
            "VERIFICATION PASSED\n"
        )
        receipt = finalize_recovery_integrity_receipt(
            record,
            scig,
            stdout,
            cml_result(),
        )
        self.assertEqual(
            receipt["verdict"],
            "PROJECTION_REBUILD_ALLOWED_EXECUTION_HELD",
        )
        self.assertEqual(receipt["projectionDecision"], "ALLOW_REBUILD")
        self.assertEqual(receipt["executionDecision"], "HOLD")
        self.assertFalse(receipt["executionAuthorized"])
        self.assertFalse(receipt["mutationAuthorized"])
        self.assertFalse(receipt["cml"]["authorizesAction"])
        self.assertTrue(receipt["receiptDigest"].startswith("sha256:"))

    def test_allow_fork_escalation_is_rejected_before_bridge(self) -> None:
        record = source_record()
        record["decision"]["execution_continuation"] = "ALLOW_FORK"
        with self.assertRaisesRegex(
            RecoveryIntegrityBridgeError,
            "must not become execution continuation",
        ):
            build_recovery_integrity_scig(
                record,
                resonance_commit=RESONANCE_COMMIT,
                observed_at="2026-08-15T12:06:58Z",
            )

    def test_cml_cannot_be_promoted_to_action_authority(self) -> None:
        record = source_record()
        scig = build_recovery_integrity_scig(
            record,
            resonance_commit=RESONANCE_COMMIT,
            observed_at="2026-08-15T12:06:58Z",
        )
        stdout = (
            f"SCIG {scig['incident_id']}\n"
            "RESULT VALID\n"
            "VERIFICATION PASSED\n"
        )
        cml = cml_result()
        cml["authorizesAction"] = True
        with self.assertRaisesRegex(
            RecoveryIntegrityBridgeError,
            "must never authorize action",
        ):
            finalize_recovery_integrity_receipt(record, scig, stdout, cml)

    def test_invalid_proofpath_output_cannot_mint_receipt(self) -> None:
        record = source_record()
        scig = build_recovery_integrity_scig(
            record,
            resonance_commit=RESONANCE_COMMIT,
            observed_at="2026-08-15T12:06:58Z",
        )
        with self.assertRaisesRegex(
            RecoveryIntegrityBridgeError,
            "not VALID/PASSED",
        ):
            finalize_recovery_integrity_receipt(
                record,
                scig,
                f"SCIG {scig['incident_id']}\nRESULT INVALID\n",
                cml_result(),
            )

    def test_source_digest_is_bound_into_scig(self) -> None:
        record = source_record()
        scig = build_recovery_integrity_scig(
            record,
            resonance_commit=RESONANCE_COMMIT,
            observed_at="2026-08-15T12:06:58Z",
        )
        mutated = copy.deepcopy(record)
        mutated["evidence_refs"].append("post_bridge_mutation")
        stdout = (
            f"SCIG {scig['incident_id']}\n"
            "RESULT VALID\n"
            "VERIFICATION PASSED\n"
        )
        with self.assertRaisesRegex(
            RecoveryIntegrityBridgeError,
            "source digest does not match",
        ):
            finalize_recovery_integrity_receipt(
                mutated,
                scig,
                stdout,
                cml_result(),
            )


if __name__ == "__main__":
    unittest.main()
