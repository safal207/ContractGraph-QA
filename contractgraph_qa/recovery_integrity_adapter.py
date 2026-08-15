"""Independent Recovery Integrity verification bridge for FCRP-SYSTEM-008.

This module consumes one already-validated RecoveryIntegrityRecord produced by
RESONANCE and projects it into the existing ProofPath SCIG v0.1 capability.
It then binds native ProofPath output and a native CML InformationFitness result
into a deterministic, non-authorizing Recovery Receipt.

No lane in this bridge grants execution, mutation, deployment, or recovery
continuation authority.  In particular, projection rebuild eligibility remains
separate from execution continuation.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

RESONANCE_REPOSITORY = "safal207/RESONANCE"
RECOVERY_PROTOCOL = "recovery-integrity-v0.1"
PROOFPATH_REPOSITORY = "safal207/ProofPath"
PROOFPATH_CAPABILITY = "proofpath.scig.v0.1"
PROOFPATH_CAPABILITY_COMMIT = "685d50e256a5125a21f4c4584b326411caaa64ad"
CML_REPOSITORY = "safal207/Causal-Memory-Layer"
CML_INFORMATION_FITNESS_COMMIT = "90c7fdaaf31ad7c17ddc0c3c55b7ccd33f6affc2"
SCIG_SCHEMA_VERSION = "0.1"
RECEIPT_SCHEMA = "cgqa.recovery-integrity-receipt.v0.1"


class RecoveryIntegrityBridgeError(ValueError):
    """Raised when a recovery claim cannot cross a verification boundary safely."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecoveryIntegrityBridgeError(f"{field} must be an object")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecoveryIntegrityBridgeError(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise RecoveryIntegrityBridgeError(f"{field} must be a boolean")
    return value


def canonical_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RecoveryIntegrityBridgeError(
            f"value is not canonical-JSON encodable: {exc}"
        ) from exc
    return encoded.encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def verify_system_008_source_record(record: dict[str, Any]) -> dict[str, Any]:
    """Verify the bounded SYSTEM-008 source shape before projecting it.

    SYSTEM-008 intentionally selects the real process-crash case where SQLite
    authority advanced to generation N+1 while the JSON projection remained at
    N.  The source may authorize *projection rebuild* but must still HOLD
    execution continuation because rollout, side effects, and current authority
    are not proven.
    """

    record = copy.deepcopy(_object(record, "record"))
    if record.get("protocol_version") != RECOVERY_PROTOCOL:
        raise RecoveryIntegrityBridgeError(
            f"record.protocol_version must be {RECOVERY_PROTOCOL}"
        )

    authority = _object(record.get("authority"), "record.authority")
    projection = _object(record.get("projection"), "record.projection")
    rollout = _object(record.get("rollout"), "record.rollout")
    decision = _object(record.get("decision"), "record.decision")
    verifier = _object(record.get("verifier"), "record.verifier")
    outcome = _object(record.get("observed_outcome"), "record.observed_outcome")

    if authority.get("integrity") != "VALID":
        raise RecoveryIntegrityBridgeError("SYSTEM-008 requires VALID authority evidence")
    if projection.get("state") != "STALE":
        raise RecoveryIntegrityBridgeError("SYSTEM-008 requires projection.state=STALE")
    agen = authority.get("generation")
    pgen = projection.get("generation")
    if not isinstance(agen, int) or not isinstance(pgen, int) or agen <= pgen:
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 requires authority generation newer than projection generation"
        )
    if decision.get("rebuild_projection") != "ALLOW_REBUILD":
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 requires rebuild_projection=ALLOW_REBUILD"
        )
    if decision.get("execution_continuation") != "HOLD":
        raise RecoveryIntegrityBridgeError(
            "projection rebuild eligibility must not become execution continuation"
        )
    if rollout.get("continuation_proof") != "NOT_PROVEN":
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 fixture requires rollout.continuation_proof=NOT_PROVEN"
        )
    if record.get("external_side_effect_state") != "UNKNOWN":
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 fixture requires external_side_effect_state=UNKNOWN"
        )
    if record.get("current_authority_proof") != "NOT_PROVEN":
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 fixture requires current_authority_proof=NOT_PROVEN"
        )
    if verifier.get("mode") != "read-only":
        raise RecoveryIntegrityBridgeError("source recovery verifier must remain read-only")
    if outcome.get("status") != "HELD":
        raise RecoveryIntegrityBridgeError("SYSTEM-008 source outcome must remain HELD")
    if not record.get("evidence_refs"):
        raise RecoveryIntegrityBridgeError("source record must carry evidence_refs")
    _text(record.get("recovery_id"), "record.recovery_id")
    return record


def build_recovery_integrity_scig(
    record: dict[str, Any],
    *,
    resonance_commit: str,
    observed_at: str,
) -> dict[str, Any]:
    """Project one bounded recovery record into canonical ProofPath SCIG v0.1."""

    record = verify_system_008_source_record(record)
    resonance_commit = _text(resonance_commit, "resonance_commit")
    if len(resonance_commit) != 40:
        raise RecoveryIntegrityBridgeError("resonance_commit must be a 40-character Git SHA")
    observed_at = _text(observed_at, "observed_at")
    if "T" not in observed_at or not observed_at.endswith("Z"):
        raise RecoveryIntegrityBridgeError("observed_at must be an RFC3339-like UTC timestamp")

    record_digest = canonical_sha256(record)
    recovery_id = _text(record.get("recovery_id"), "record.recovery_id")
    logical_operation_id = f"recovery-integrity:{recovery_id}"
    incident_id = f"RECOVERY-INTEGRITY-{record_digest[:16]}"
    action_id = f"recovery-evaluation:{recovery_id}"
    pre_state_id = f"recovery-observed:{recovery_id}"
    post_state_id = f"recovery-held:{recovery_id}"
    verification_id = "VERIFY-RECOVERY-INTEGRITY-SYSTEM-008"

    return {
        "schema_version": SCIG_SCHEMA_VERSION,
        "incident_id": incident_id,
        "logical_operation_id": logical_operation_id,
        "bridge_contract": {
            "schema": "cgqa.recovery-integrity-proofpath-bridge.v0.1",
            "producer": "safal207/ContractGraph-QA",
            "source_repository": RESONANCE_REPOSITORY,
            "source_commit": resonance_commit,
            "source_record_sha256": record_digest,
            "consumer": PROOFPATH_REPOSITORY,
            "consumer_capability": PROOFPATH_CAPABILITY,
            "consumer_capability_commit": PROOFPATH_CAPABILITY_COMMIT,
            "cml_repository": CML_REPOSITORY,
            "cml_commit": CML_INFORMATION_FITNESS_COMMIT,
            "authority_transfer": "NONE",
            "authorization_ref": None,
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_performed": False,
        },
        "actor": {
            "id": "contractgraph-qa-recovery-verifier",
            "type": "verification_service",
            "phase": "verification",
            "provenance": "RecoveryIntegrityRecord v0.1 exact-head replay",
        },
        "action": {
            "id": action_id,
            "type": "recovery_integrity_verification",
            "phase": "verification",
        },
        "pre_state": {
            "id": pre_state_id,
            "type": "stale_projection_with_newer_durable_authority",
            "authority_generation": record["authority"]["generation"],
            "projection_generation": record["projection"]["generation"],
        },
        "control": {
            "id": "recovery-integrity-separation-gate",
            "type": "recovery_state_transition_guard",
            "expected_outcome": "allow_projection_rebuild_hold_execution",
        },
        "transition": {
            "id": f"transition:{recovery_id}",
            "from": pre_state_id,
            "action": action_id,
            "to": post_state_id,
            "phase": "verification",
            "observed_at": observed_at,
            "provenance": "ContractGraph-QA independent exact-source verification",
            "logical_operation_id": logical_operation_id,
        },
        "post_state": {
            "id": post_state_id,
            "type": "projection_rebuild_eligible_execution_held",
            "rebuild_projection": "ALLOW_REBUILD",
            "execution_continuation": "HOLD",
            "execution_authorized": False,
        },
        "invariants": [
            {
                "id": "INV-RECOVERY-PROJECTION-NOT-AUTHORITY",
                "description": "A stale projection MUST NOT redefine surviving durable authority state.",
                "result": "held",
                "evidence_reference": "evidence-recovery-record",
            },
            {
                "id": "INV-RECOVERY-REBUILD-NOT-CONTINUATION",
                "description": "ALLOW_REBUILD MUST NOT imply ALLOW_FORK or execution authority.",
                "result": "held",
                "evidence_reference": "evidence-recovery-record",
            },
            {
                "id": "INV-RECOVERY-UNPROVEN-AUTHORITY-HOLDS",
                "description": "Unproven current authority or external side effects MUST keep continuation fail-closed.",
                "result": "held",
                "evidence_reference": "evidence-recovery-record",
            },
        ],
        "cause": [
            {
                "type": "required",
                "source": "recovery-integrity-separation-gate",
                "target": action_id,
                "evidence_reference": "evidence-recovery-record",
            },
            {
                "type": "verified_by",
                "source": action_id,
                "target": verification_id,
                "evidence_reference": "evidence-recovery-record",
            },
        ],
        "containment": {
            "action": "hold-execution-continuation",
            "result": "passed",
            "target_state": "no-execution-authority",
            "evidence_reference": "evidence-recovery-record",
        },
        "recovery": {
            "action": "classify-projection-rebuild-without-execution",
            "result": "passed",
            "target_state": "projection-rebuild-eligible-execution-held",
            "evidence_reference": "evidence-recovery-record",
        },
        "verification": {
            "test_id": verification_id,
            "expected": "allow_projection_rebuild_hold_execution",
            "observed": "allow_projection_rebuild_hold_execution",
            "result": "passed",
            "evidence_reference": "evidence-recovery-record",
        },
        "evidence": [
            {
                "id": "evidence-recovery-record",
                "type": "recovery_integrity_record",
                "sha256": record_digest,
                "provenance": f"{RESONANCE_REPOSITORY}@{resonance_commit}",
                "authority_effect": "none",
            }
        ],
    }


def finalize_recovery_integrity_receipt(
    record: dict[str, Any],
    scig: dict[str, Any],
    native_proofpath_output: str,
    cml_fitness: dict[str, Any],
) -> dict[str, Any]:
    """Bind ProofPath + CML native evidence into one deterministic receipt."""

    record = verify_system_008_source_record(record)
    scig = copy.deepcopy(_object(scig, "scig"))
    bridge = _object(scig.get("bridge_contract"), "scig.bridge_contract")
    if bridge.get("source_record_sha256") != canonical_sha256(record):
        raise RecoveryIntegrityBridgeError("SCIG source digest does not match recovery record")
    if bridge.get("authority_transfer") != "NONE":
        raise RecoveryIntegrityBridgeError("verification bridge must transfer no authority")
    for field in ("execution_authorized", "mutation_authorized", "external_effects_performed"):
        if _bool(bridge.get(field), f"scig.bridge_contract.{field}"):
            raise RecoveryIntegrityBridgeError(f"{field} must remain false")
    if bridge.get("consumer_capability_commit") != PROOFPATH_CAPABILITY_COMMIT:
        raise RecoveryIntegrityBridgeError("ProofPath capability commit pin mismatch")
    if bridge.get("cml_commit") != CML_INFORMATION_FITNESS_COMMIT:
        raise RecoveryIntegrityBridgeError("CML commit pin mismatch")

    output = _text(native_proofpath_output, "native_proofpath_output")
    normalized = [" ".join(line.split()) for line in output.splitlines() if line.strip()]
    incident_id = _text(scig.get("incident_id"), "scig.incident_id")
    if f"SCIG {incident_id}" not in normalized:
        raise RecoveryIntegrityBridgeError("ProofPath output does not bind incident_id")
    if "RESULT VALID" not in normalized or "VERIFICATION PASSED" not in normalized:
        raise RecoveryIntegrityBridgeError("ProofPath native verification is not VALID/PASSED")

    cml = copy.deepcopy(_object(cml_fitness, "cml_fitness"))
    if cml.get("repository") != CML_REPOSITORY:
        raise RecoveryIntegrityBridgeError("CML repository mismatch")
    if cml.get("commit") != CML_INFORMATION_FITNESS_COMMIT:
        raise RecoveryIntegrityBridgeError("CML exact commit mismatch")
    if cml.get("status") != "READY_FOR_AUTHORITY_CHECK":
        raise RecoveryIntegrityBridgeError(
            "SYSTEM-008 expects source information ready only for a separate authority check"
        )
    if cml.get("readyForAuthorityCheck") is not True:
        raise RecoveryIntegrityBridgeError("CML must explicitly report readyForAuthorityCheck=true")
    if cml.get("authorizesAction") is not False:
        raise RecoveryIntegrityBridgeError("CML information fitness must never authorize action")

    result = {
        "schema": RECEIPT_SCHEMA,
        "systemCase": "FCRP-SYSTEM-008",
        "recoveryId": record["recovery_id"],
        "logicalOperationId": scig["logical_operation_id"],
        "source": {
            "repository": RESONANCE_REPOSITORY,
            "commit": bridge["source_commit"],
            "recordSha256": bridge["source_record_sha256"],
            "protocol": RECOVERY_PROTOCOL,
        },
        "projectionDecision": "ALLOW_REBUILD",
        "executionDecision": "HOLD",
        "proofpath": {
            "repository": PROOFPATH_REPOSITORY,
            "capabilityId": PROOFPATH_CAPABILITY,
            "capabilityCommit": PROOFPATH_CAPABILITY_COMMIT,
            "scigSha256": canonical_sha256(scig),
            "result": "VALID",
        },
        "cml": {
            "repository": CML_REPOSITORY,
            "commit": CML_INFORMATION_FITNESS_COMMIT,
            "status": cml["status"],
            "readyForAuthorityCheck": True,
            "authorizesAction": False,
        },
        "verdict": "PROJECTION_REBUILD_ALLOWED_EXECUTION_HELD",
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": "PROCESS_CRASH_NOT_PHYSICAL_POWER_LOSS",
    }
    return {
        **result,
        "receiptDigest": "sha256:" + hashlib.sha256(canonical_bytes(result)).hexdigest(),
    }
