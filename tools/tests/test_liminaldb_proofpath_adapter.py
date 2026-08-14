from __future__ import annotations

import copy
import unittest

from contractgraph_qa.liminaldb_proofpath_adapter import (
    LIMINALDB_AUDIT_EVENT_CONTRACT_BLOB,
    LIMINALDB_PROOFPATH_CONTRACT_COMMIT,
    LiminalDBProofPathBridgeError,
    _sha256,
    build_liminaldb_proofpath_audit_event,
    build_system_004_path_trace,
)

LOGICAL_OPERATION_ID = "crossmint-public-example-001"


def sample_scig() -> dict:
    return {
        "schema_version": "0.1",
        "incident_id": "CGQA-PROOFPATH-0123456789abcdef",
        "logical_operation_id": LOGICAL_OPERATION_ID,
        "evidence": [{"id": "e1", "sha256": "1" * 64}],
    }


def sample_receipt(scig: dict | None = None) -> dict:
    scig = scig or sample_scig()
    receipt = {
        "schema": "cgqa.proofpath-scig-native-bridge-receipt.v0.1",
        "logicalOperationId": scig["logical_operation_id"],
        "incidentId": scig["incident_id"],
        "sourceEvidencePackSha256": "2" * 64,
        "scigSha256": _sha256(scig),
        "proofpath": {
            "repository": "safal207/ProofPath",
            "capabilityId": "proofpath.scig.v0.1",
            "capabilityCommit": "685d50e256a5125a21f4c4584b326411caaa64ad",
            "nativeVerifier": "proofpath-scig",
            "result": "VALID",
        },
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
    }
    receipt["receiptDigest"] = "sha256:" + _sha256(receipt)
    return receipt


def sample_import_summary(logical_operation_id: str = LOGICAL_OPERATION_ID) -> dict:
    return {
        "schema_version": "liminaldb-proofpath-import-check-v0.1",
        "mode": "dry_run",
        "write_performed": False,
        "logical_operation_ids": [logical_operation_id],
        "authority": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "durable_memory_accepted": False,
            "live_ingestion_performed": False,
        },
    }


class LiminalDBProofPathAdapterTests(unittest.TestCase):
    def test_builds_artifact_only_event(self) -> None:
        scig = sample_scig()
        event = build_liminaldb_proofpath_audit_event(
            scig,
            sample_receipt(scig),
            observed_at="2026-08-14T08:00:00Z",
        )
        self.assertEqual(event["correlationId"], scig["logical_operation_id"])
        self.assertEqual(event["actor"], "proofpath-scig-native-verifier")
        self.assertEqual(event["action"], "proofpath.scig.verification.observed")
        self.assertFalse(event["details"]["persistence"]["durable_memory"])
        self.assertFalse(event["details"]["persistence"]["live_ingestion"])
        self.assertFalse(event["details"]["authority"]["persistence"])
        self.assertEqual(event["details"]["adapter"]["commit"], LIMINALDB_PROOFPATH_CONTRACT_COMMIT)
        self.assertEqual(event["details"]["adapter"]["contract_blob_sha"], LIMINALDB_AUDIT_EVENT_CONTRACT_BLOB)

    def test_rejects_logical_operation_drift(self) -> None:
        scig = sample_scig()
        receipt = sample_receipt(scig)
        receipt["logicalOperationId"] = "lop:other"
        receipt["receiptDigest"] = "sha256:" + _sha256({k: v for k, v in receipt.items() if k != "receiptDigest"})
        with self.assertRaisesRegex(LiminalDBProofPathBridgeError, "logical operation"):
            build_liminaldb_proofpath_audit_event(scig, receipt, observed_at="2026-08-14T08:00:00Z")

    def test_rejects_tampered_receipt_digest(self) -> None:
        scig = sample_scig()
        receipt = sample_receipt(scig)
        receipt["receiptDigest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(LiminalDBProofPathBridgeError, "digest mismatch"):
            build_liminaldb_proofpath_audit_event(scig, receipt, observed_at="2026-08-14T08:00:00Z")

    def test_rejects_authority_transfer(self) -> None:
        scig = sample_scig()
        receipt = sample_receipt(scig)
        receipt["authorityTransfer"] = "EXPLICIT"
        unhashed = copy.deepcopy(receipt)
        unhashed.pop("receiptDigest")
        receipt["receiptDigest"] = "sha256:" + _sha256(unhashed)
        with self.assertRaisesRegex(LiminalDBProofPathBridgeError, "cannot transfer authority"):
            build_liminaldb_proofpath_audit_event(scig, receipt, observed_at="2026-08-14T08:00:00Z")

    def test_rejects_wrong_consumer_capability_commit(self) -> None:
        with self.assertRaisesRegex(LiminalDBProofPathBridgeError, "canonical ProofPath import contract"):
            build_liminaldb_proofpath_audit_event(
                sample_scig(),
                sample_receipt(),
                observed_at="2026-08-14T08:00:00Z",
                liminaldb_commit="0" * 40,
            )

    def test_path_trace_stops_before_persistence(self) -> None:
        event = build_liminaldb_proofpath_audit_event(
            sample_scig(), sample_receipt(), observed_at="2026-08-14T08:00:00Z"
        )
        trace = build_system_004_path_trace(event, sample_import_summary())
        self.assertEqual([frame["payload"]["stage"] for frame in trace], [
            "proofpath-native-verified",
            "liminaldb-audit-event-projected",
            "liminaldb-dry-run-validated",
            "stop-before-persistence",
        ])
        self.assertEqual(len({frame["continuity_token"] for frame in trace}), 1)
        self.assertEqual({frame["payload"]["logical_operation_id"] for frame in trace}, {LOGICAL_OPERATION_ID})

    def test_path_trace_rejects_false_durable_claim(self) -> None:
        event = build_liminaldb_proofpath_audit_event(
            sample_scig(), sample_receipt(), observed_at="2026-08-14T08:00:00Z"
        )
        summary = sample_import_summary()
        summary["authority"]["durable_memory_accepted"] = True
        with self.assertRaisesRegex(LiminalDBProofPathBridgeError, "durable_memory_accepted"):
            build_system_004_path_trace(event, summary)


if __name__ == "__main__":
    unittest.main()
