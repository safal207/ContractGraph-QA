"""ProofPath native receipt -> LiminalDB AuditEvent artifact bridge.

SYSTEM-004 stops deliberately at the persistence frontier. The bridge proves that a
native ProofPath SCIG result can be represented as the dedicated canonical
LiminalDB ProofPath AuditEvent import profile without inventing durable-memory or
execution authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

LIMINALDB_REPOSITORY = "safal207/LiminalDB"
LIMINALDB_PROOFPATH_CONTRACT_COMMIT = "00580ff097dee61b45ad3c8a3c36ae5f548f572d"
LIMINALDB_AUDIT_EVENT_CONTRACT_PATH = "sdk/ts/src/protocol-types.ts"
LIMINALDB_AUDIT_EVENT_CONTRACT_BLOB = "fd733971aaae089df770062bcf7f2c2d6d19ca1d"
PROOFPATH_REPOSITORY = "safal207/ProofPath"
PROOFPATH_CAPABILITY = "proofpath.scig.v0.1"
PROOFPATH_CAPABILITY_COMMIT = "685d50e256a5125a21f4c4584b326411caaa64ad"
SOURCE_RECEIPT_SCHEMA = "cgqa.proofpath-scig-native-bridge-receipt.v0.1"
EVENT_SCHEMA = "liminaldb-proofpath-audit-event-v0.1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class LiminalDBProofPathBridgeError(ValueError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiminalDBProofPathBridgeError(f"{field} must be an object")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LiminalDBProofPathBridgeError(f"{field} must be a non-empty string")
    return value.strip()


def _false(value: object, field: str) -> None:
    if value is not False:
        raise LiminalDBProofPathBridgeError(f"{field} must be false")


def _verify_native_receipt(scig: dict[str, Any], receipt: dict[str, Any]) -> tuple[str, str, str]:
    if receipt.get("schema") != SOURCE_RECEIPT_SCHEMA:
        raise LiminalDBProofPathBridgeError("receipt schema is not the native ProofPath bridge receipt")
    logical_operation_id = _text(receipt.get("logicalOperationId"), "receipt.logicalOperationId")
    incident_id = _text(receipt.get("incidentId"), "receipt.incidentId")
    if scig.get("logical_operation_id") != logical_operation_id:
        raise LiminalDBProofPathBridgeError("SCIG and native receipt logical operation identities differ")
    if scig.get("incident_id") != incident_id:
        raise LiminalDBProofPathBridgeError("SCIG and native receipt incident identities differ")

    scig_sha = _text(receipt.get("scigSha256"), "receipt.scigSha256")
    if HEX64.fullmatch(scig_sha) is None or scig_sha != _sha256(scig):
        raise LiminalDBProofPathBridgeError("native receipt does not bind the exact SCIG bytes")

    proofpath = _mapping(receipt.get("proofpath"), "receipt.proofpath")
    exact = {
        "repository": PROOFPATH_REPOSITORY,
        "capabilityId": PROOFPATH_CAPABILITY,
        "capabilityCommit": PROOFPATH_CAPABILITY_COMMIT,
        "nativeVerifier": "proofpath-scig",
        "result": "VALID",
    }
    for key, expected in exact.items():
        if proofpath.get(key) != expected:
            raise LiminalDBProofPathBridgeError(f"receipt.proofpath.{key} must equal {expected}")

    if receipt.get("authorityTransfer") != "NONE":
        raise LiminalDBProofPathBridgeError("ProofPath -> LiminalDB artifact bridge cannot transfer authority")
    for key in ("executionAuthorized", "mutationAuthorized", "externalEffectsPerformed"):
        _false(receipt.get(key), f"receipt.{key}")

    recorded = _text(receipt.get("receiptDigest"), "receipt.receiptDigest")
    if not recorded.startswith("sha256:") or HEX64.fullmatch(recorded[7:]) is None:
        raise LiminalDBProofPathBridgeError("receipt.receiptDigest must be sha256:<64hex>")
    unhashed = copy.deepcopy(receipt)
    unhashed.pop("receiptDigest", None)
    if recorded != "sha256:" + _sha256(unhashed):
        raise LiminalDBProofPathBridgeError("native ProofPath receipt digest mismatch")
    return logical_operation_id, incident_id, recorded[7:]


def build_liminaldb_proofpath_audit_event(
    scig: dict[str, Any],
    native_receipt: dict[str, Any],
    *,
    observed_at: str,
    liminaldb_commit: str = LIMINALDB_PROOFPATH_CONTRACT_COMMIT,
    liminaldb_contract_blob_sha: str = LIMINALDB_AUDIT_EVENT_CONTRACT_BLOB,
) -> dict[str, Any]:
    scig = copy.deepcopy(_mapping(scig, "scig"))
    receipt = copy.deepcopy(_mapping(native_receipt, "native_receipt"))
    logical_operation_id, incident_id, receipt_sha = _verify_native_receipt(scig, receipt)

    observed_at = _text(observed_at, "observed_at")
    if "T" not in observed_at or not observed_at.endswith("Z"):
        raise LiminalDBProofPathBridgeError("observed_at must be an RFC3339-like UTC timestamp")
    if HEX40.fullmatch(liminaldb_commit) is None:
        raise LiminalDBProofPathBridgeError("liminaldb_commit must be a full SHA")
    if liminaldb_commit != LIMINALDB_PROOFPATH_CONTRACT_COMMIT:
        raise LiminalDBProofPathBridgeError("SYSTEM-004 must target the canonical ProofPath import contract commit")
    if HEX40.fullmatch(liminaldb_contract_blob_sha) is None:
        raise LiminalDBProofPathBridgeError("liminaldb_contract_blob_sha must be a Git blob SHA")
    if liminaldb_contract_blob_sha != LIMINALDB_AUDIT_EVENT_CONTRACT_BLOB:
        raise LiminalDBProofPathBridgeError("SYSTEM-004 AuditEvent contract blob identity mismatch")

    event_seed = f"{logical_operation_id}|{incident_id}|{receipt_sha}|{liminaldb_commit}".encode("utf-8")
    event = {
        "id": "proofpath-" + hashlib.sha256(event_seed).hexdigest()[:32],
        "ts": observed_at,
        "correlationId": logical_operation_id,
        "kind": "audit",
        "actor": "proofpath-scig-native-verifier",
        "action": "proofpath.scig.verification.observed",
        "details": {
            "schema_version": EVENT_SCHEMA,
            "logical_operation_id": logical_operation_id,
            "source": {
                "repository": PROOFPATH_REPOSITORY,
                "capability_id": PROOFPATH_CAPABILITY,
                "capability_commit": PROOFPATH_CAPABILITY_COMMIT,
                "incident_id": incident_id,
                "scig_sha256": _sha256(scig),
                "native_result": "VALID",
                "native_verifier": "proofpath-scig",
                "bridge_receipt_sha256": receipt_sha,
                "verification_class": "native_recomputed",
            },
            "evidence": {
                "bounded": True,
                "replayable": True,
                "source_receipt_bound": True,
            },
            "authority": {
                "mode": "evidence_only",
                "execution": False,
                "mutation": False,
                "persistence": False,
                "deployment": False,
                "merge": False,
            },
            "persistence": {
                "write_mode": "artifact_only",
                "durable_memory": False,
                "live_ingestion": False,
                "namespace_mutation": False,
            },
            "adapter": {
                "repository": LIMINALDB_REPOSITORY,
                "commit": liminaldb_commit,
                "contract_path": LIMINALDB_AUDIT_EVENT_CONTRACT_PATH,
                "contract_blob_sha": liminaldb_contract_blob_sha,
                "event_contract": "AuditEvent",
                "write_mode": "artifact_only",
            },
        },
    }
    event["details"]["event_sha256"] = _sha256(event)
    return event


def build_system_004_path_trace(event: dict[str, Any], import_summary: dict[str, Any]) -> list[dict[str, Any]]:
    event = copy.deepcopy(_mapping(event, "event"))
    summary = copy.deepcopy(_mapping(import_summary, "import_summary"))
    logical_operation_id = _text(event.get("correlationId"), "event.correlationId")
    if summary.get("logical_operation_ids") != [logical_operation_id]:
        raise LiminalDBProofPathBridgeError("LiminalDB summary did not preserve the logical operation identity")
    if summary.get("mode") != "dry_run" or summary.get("write_performed") is not False:
        raise LiminalDBProofPathBridgeError("SYSTEM-004 requires mutation-free LiminalDB dry-run validation")
    authority = _mapping(summary.get("authority"), "import_summary.authority")
    for key in ("execution_authorized", "mutation_authorized", "durable_memory_accepted", "live_ingestion_performed"):
        _false(authority.get(key), f"import_summary.authority.{key}")

    token = "neo-rezonans-system-004:" + hashlib.sha256(logical_operation_id.encode()).hexdigest()[:16]
    return [
        {"v": "0.1", "id": "system-004-0", "ts": 1, "type": "orientation", "payload": {"identity": "neo-rezonans-system-004", "logical_operation_id": logical_operation_id, "stage": "proofpath-native-verified"}, "continuity_token": token},
        {"v": "0.1", "id": "system-004-1", "ts": 2, "type": "focus_snapshot", "payload": {"drift": 0.0, "logical_operation_id": logical_operation_id, "stage": "liminaldb-audit-event-projected"}, "continuity_token": token},
        {"v": "0.1", "id": "system-004-2", "ts": 3, "type": "focus_snapshot", "payload": {"drift": 0.0, "logical_operation_id": logical_operation_id, "stage": "liminaldb-dry-run-validated"}, "continuity_token": token},
        {"v": "0.1", "id": "system-004-3", "ts": 4, "type": "route_response", "payload": {"logical_operation_id": logical_operation_id, "stage": "stop-before-persistence", "branches": [{"id": "artifact-only-handoff", "confidence": 1.0, "status": "admissible"}]}, "continuity_token": token},
    ]
