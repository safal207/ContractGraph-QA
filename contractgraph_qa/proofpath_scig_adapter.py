"""Canonical ContractGraph-QA -> ProofPath SCIG v0.1 bridge.

The bridge consumes a *verified* native ContractGraph-QA provider-decision evidence
pack and projects that evidence into the canonical ProofPath SAFE Causal Incident
Graph (SCIG) v0.1 contract.  It deliberately does not consume ProofPath's proposed
PoCI / Evidence Builder / Control Cloud stack.

A bridge PASS is evidence portability only.  The ContractGraph-QA -> ProofPath edge
carries no live execution authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from contractgraph_qa.provider_decision_evidence import (
    ProviderDecisionEvidenceError,
    canonical_evidence_pack_sha256,
    canonical_sha256,
    verify_provider_decision_evidence,
)

PROOFPATH_REPOSITORY = "safal207/ProofPath"
PROOFPATH_SCIG_CAPABILITY = "proofpath.scig.v0.1"
PROOFPATH_SCIG_CANONICAL_COMMIT = "685d50e256a5125a21f4c4584b326411caaa64ad"
SCIG_SCHEMA_VERSION = "0.1"
BRIDGE_RECEIPT_SCHEMA = "cgqa.proofpath-scig-native-bridge-receipt.v0.1"


class ProofPathScigBridgeError(ValueError):
    """Raised when evidence cannot cross the CGQA -> ProofPath boundary safely."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProofPathScigBridgeError(f"{field} must be an object")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProofPathScigBridgeError(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ProofPathScigBridgeError(f"{field} must be a boolean")
    return value


def _canonical_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProofPathScigBridgeError(f"value is not canonical-JSON encodable: {exc}") from exc
    return encoded.encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_non_authorizing_claim_boundary(pack: dict[str, Any]) -> None:
    boundary = _object(pack.get("claimBoundary"), "evidencePack.claimBoundary")
    if boundary.get("classification") != "PUBLIC_CONTRACT_REPLAY_EVIDENCE":
        raise ProofPathScigBridgeError(
            "evidencePack.claimBoundary.classification must remain PUBLIC_CONTRACT_REPLAY_EVIDENCE"
        )
    for field in (
        "networkCallsPerformed",
        "walletExecutionPerformed",
        "securityCertification",
        "productionAuthorization",
        "financialAuthorization",
    ):
        if _bool(boundary.get(field), f"evidencePack.claimBoundary.{field}"):
            raise ProofPathScigBridgeError(
                f"evidencePack.claimBoundary.{field} must remain false at the ProofPath boundary"
            )


def _require_non_authorizing_provider_decision(provider_decision: dict[str, Any]) -> None:
    authority = _object(provider_decision.get("authority"), "providerDecision.authority")
    if authority.get("classification") != "PUBLIC_CONTRACT_COMPOSITION":
        raise ProofPathScigBridgeError(
            "providerDecision.authority.classification must remain PUBLIC_CONTRACT_COMPOSITION"
        )
    for field in ("securityCertification", "productionAuthorization", "financialAuthorization"):
        if _bool(authority.get(field), f"providerDecision.authority.{field}"):
            raise ProofPathScigBridgeError(
                f"providerDecision.authority.{field} must remain false at the ProofPath boundary"
            )


def build_proofpath_scig_from_provider_evidence(
    pack: dict[str, Any],
    *,
    observed_at: str,
) -> dict[str, Any]:
    """Project one verified CGQA provider-decision evidence pack into SCIG v0.1.

    The first native segment intentionally uses the already-reviewed Crossmint public
    contract case whose unified payment gate result is STOP with no new monetary
    action.  A different result must be modelled as a separate bridge case rather than
    silently inheriting these positive invariants.
    """

    pack = copy.deepcopy(_object(pack, "evidencePack"))
    try:
        provider_decision = verify_provider_decision_evidence(pack)
    except ProviderDecisionEvidenceError as exc:
        raise ProofPathScigBridgeError(f"CGQA evidence pack failed native replay: {exc}") from exc

    _require_non_authorizing_claim_boundary(pack)
    _require_non_authorizing_provider_decision(provider_decision)

    observed_at = _text(observed_at, "observed_at")
    if "T" not in observed_at or not observed_at.endswith("Z"):
        raise ProofPathScigBridgeError("observed_at must be an RFC3339-like UTC timestamp")

    logical_operation_id = _text(
        provider_decision.get("logicalOperationId"),
        "providerDecision.logicalOperationId",
    )
    execution_id = _text(provider_decision.get("executionId"), "providerDecision.executionId")
    decision = _object(provider_decision.get("decision"), "providerDecision.decision")
    if decision.get("decision") != "STOP":
        raise ProofPathScigBridgeError("SYSTEM-003 pilot requires CGQA decision STOP")
    if decision.get("monetaryActionAllowed") is not False:
        raise ProofPathScigBridgeError(
            "SYSTEM-003 pilot requires monetaryActionAllowed to be exactly false"
        )

    pack_digest = canonical_evidence_pack_sha256(pack)
    decision_digest = canonical_sha256(provider_decision)
    incident_id = f"CGQA-PROOFPATH-{pack_digest[:16]}"
    action_id = f"cgqa-payment-decision:{execution_id}"
    pre_state_id = f"cgqa-provider-observation:{execution_id}"
    post_state_id = f"cgqa-payment-stopped:{execution_id}"
    verification_id = "VERIFY-CGQA-PROOFPATH-001"

    return {
        "schema_version": SCIG_SCHEMA_VERSION,
        "incident_id": incident_id,
        # SCIG v0.1 explicitly allows additional properties.  These extensions bind
        # system identity without changing ProofPath's native protocol schema.
        "logical_operation_id": logical_operation_id,
        "bridge_contract": {
            "schema": "cgqa.proofpath-scig-bridge.v0.1",
            "producer": "safal207/ContractGraph-QA",
            "consumer": PROOFPATH_REPOSITORY,
            "consumer_capability": PROOFPATH_SCIG_CAPABILITY,
            "consumer_capability_commit": PROOFPATH_SCIG_CANONICAL_COMMIT,
            "source_evidence_pack_sha256": pack_digest,
            "authority_transfer": "NONE",
            "authorization_ref": None,
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_performed": False,
        },
        "actor": {
            "id": "contractgraph-qa-provider-decision-gate",
            "type": "verification_service",
            "phase": "verification",
            "provenance": "ContractGraph-QA provider decision evidence v0.1",
        },
        "action": {
            "id": action_id,
            "type": "provider_payment_decision_replay",
            "phase": "verification",
        },
        "pre_state": {
            "id": pre_state_id,
            "type": "provider_evidence_observed",
            "logical_operation_id": logical_operation_id,
        },
        "control": {
            "id": "cgqa-unified-agent-payment-gate",
            "type": "financial_state_transition_guard",
            "expected_outcome": "stop_without_new_monetary_action",
        },
        "transition": {
            "id": f"transition:{execution_id}",
            "from": pre_state_id,
            "action": action_id,
            "to": post_state_id,
            "phase": "verification",
            "observed_at": observed_at,
            "provenance": "ContractGraph-QA exact local replay",
            "logical_operation_id": logical_operation_id,
        },
        "post_state": {
            "id": post_state_id,
            "type": "logical_operation_satisfied_no_new_money",
            "logical_operation_id": logical_operation_id,
            "decision": "STOP",
            "monetary_action_allowed": False,
        },
        "invariants": [
            {
                "id": "INV-CGQA-NO-DUPLICATE-MONEY",
                "description": "A reconciled committed logical operation MUST NOT authorize a second monetary action.",
                "result": "held",
                "evidence_reference": "evidence-cgqa-provider-decision",
            },
            {
                "id": "INV-CGQA-LOGICAL-IDENTITY",
                "description": "The provider decision and ProofPath projection MUST preserve the same logical operation identity.",
                "result": "held",
                "evidence_reference": "evidence-cgqa-provider-pack",
            },
            {
                "id": "INV-CGQA-EVIDENCE-NOT-AUTHORITY",
                "description": "Evidence crossing ContractGraph-QA to ProofPath MUST NOT transfer execution or mutation authority.",
                "result": "held",
                "evidence_reference": "evidence-cgqa-provider-pack",
            },
        ],
        "cause": [
            {
                "type": "required",
                "source": "cgqa-unified-agent-payment-gate",
                "target": action_id,
                "evidence_reference": "evidence-cgqa-provider-pack",
            },
            {
                "type": "verified_by",
                "source": action_id,
                "target": verification_id,
                "evidence_reference": "evidence-cgqa-provider-decision",
            },
        ],
        "containment": {
            "action": "stop-additional-monetary-action",
            "result": "passed",
            "target_state": "no-new-monetary-action",
            "evidence_reference": "evidence-cgqa-provider-decision",
        },
        "recovery": {
            "action": "preserve-original-logical-operation-and-stop-retry",
            "result": "passed",
            "target_state": "logical-operation-satisfied-without-duplicate-payment",
            "evidence_reference": "evidence-cgqa-provider-decision",
        },
        "verification": {
            "test_id": verification_id,
            "expected": "stop_without_new_monetary_action",
            "observed": "stop_without_new_monetary_action",
            "result": "passed",
            "evidence_reference": "evidence-cgqa-provider-decision",
        },
        "evidence": [
            {
                "id": "evidence-cgqa-provider-pack",
                "type": "deterministic_replay_pack",
                "sha256": pack_digest,
                "provenance": "safal207/ContractGraph-QA:provider_decision_evidence.v0.1",
                "authority_effect": "none",
            },
            {
                "id": "evidence-cgqa-provider-decision",
                "type": "recomputed_payment_decision",
                "sha256": decision_digest,
                "provenance": "safal207/ContractGraph-QA:provider_payment_decision.v0.1",
                "authority_effect": "none",
            },
        ],
    }


def finalize_native_proofpath_receipt(
    scig: dict[str, Any],
    native_verifier_output: str,
    *,
    proofpath_capability_commit: str = PROOFPATH_SCIG_CANONICAL_COMMIT,
) -> dict[str, Any]:
    """Bind actual `proofpath-scig` stdout to a deterministic non-authorizing receipt."""

    scig = copy.deepcopy(_object(scig, "scig"))
    if scig.get("schema_version") != SCIG_SCHEMA_VERSION:
        raise ProofPathScigBridgeError("scig.schema_version must equal 0.1")
    incident_id = _text(scig.get("incident_id"), "scig.incident_id")
    logical_operation_id = _text(scig.get("logical_operation_id"), "scig.logical_operation_id")
    bridge = _object(scig.get("bridge_contract"), "scig.bridge_contract")
    if bridge.get("authority_transfer") != "NONE":
        raise ProofPathScigBridgeError("CGQA -> ProofPath bridge must transfer no authority")
    if bridge.get("authorization_ref") not in (None, ""):
        raise ProofPathScigBridgeError("CGQA -> ProofPath bridge must not carry authorization_ref")
    if _bool(bridge.get("execution_authorized"), "scig.bridge_contract.execution_authorized"):
        raise ProofPathScigBridgeError("SCIG bridge may not carry execution authority")
    if _bool(bridge.get("mutation_authorized"), "scig.bridge_contract.mutation_authorized"):
        raise ProofPathScigBridgeError("SCIG bridge may not carry mutation authority")
    if _bool(
        bridge.get("external_effects_performed"),
        "scig.bridge_contract.external_effects_performed",
    ):
        raise ProofPathScigBridgeError("SCIG bridge proof may not perform external effects")

    proofpath_capability_commit = _text(
        proofpath_capability_commit,
        "proofpath_capability_commit",
    )
    if proofpath_capability_commit != PROOFPATH_SCIG_CANONICAL_COMMIT:
        raise ProofPathScigBridgeError(
            "native verification must use the canonical proofpath.scig.v0.1 capability commit"
        )
    if bridge.get("consumer_capability_commit") != proofpath_capability_commit:
        raise ProofPathScigBridgeError("SCIG bridge capability pin does not match native verifier commit")

    output = _text(native_verifier_output, "native_verifier_output")
    normalized_lines = [" ".join(line.split()) for line in output.splitlines() if line.strip()]
    if f"SCIG {incident_id}" not in normalized_lines:
        raise ProofPathScigBridgeError("native ProofPath output does not bind the expected incident_id")
    if "RESULT VALID" not in normalized_lines:
        raise ProofPathScigBridgeError("native ProofPath verifier did not emit RESULT VALID")
    if "VERIFICATION PASSED" not in normalized_lines:
        raise ProofPathScigBridgeError("native ProofPath verifier did not emit VERIFICATION PASSED")

    result_without_digest = {
        "schema": BRIDGE_RECEIPT_SCHEMA,
        "logicalOperationId": logical_operation_id,
        "incidentId": incident_id,
        "sourceEvidencePackSha256": _text(
            bridge.get("source_evidence_pack_sha256"),
            "scig.bridge_contract.source_evidence_pack_sha256",
        ),
        "scigSha256": _sha256(scig),
        "proofpath": {
            "repository": PROOFPATH_REPOSITORY,
            "capabilityId": PROOFPATH_SCIG_CAPABILITY,
            "capabilityCommit": proofpath_capability_commit,
            "nativeVerifier": "proofpath-scig",
            "result": "VALID",
        },
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
    }
    return {
        **result_without_digest,
        "receiptDigest": "sha256:" + hashlib.sha256(_canonical_bytes(result_without_digest)).hexdigest(),
    }
