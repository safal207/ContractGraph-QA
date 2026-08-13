"""Bridge provider reconciliation into the Unified Agent Payment Decision Gate.

The bridge never calls a provider and never infers financial authority. It composes
already-captured provider observations with explicit authority evidence, then applies
a fail-closed retry-authority mapping before delegating the final decision to the
repository's Unified Agent Payment Decision Gate.
"""

from __future__ import annotations

from typing import Any

from contractgraph_qa.agent_payment_decision import evaluate_agent_payment_decision
from contractgraph_qa.provider_adapter import (
    ADAPTER_SCHEMA_V1,
    ADAPTER_SCHEMA_V2,
    ADAPTER_SCHEMA_V3,
    reconcile_provider_observations,
    validate_provider_adapter,
)

RESULT_SCHEMA = "cgqa.provider-payment-decision.v0.1"
_AUTHORITY = {"authorized", "revoked", "expired", "unknown"}


class ProviderPaymentDecisionError(ValueError):
    """Raised when bridge inputs cannot be mapped without inventing semantics."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderPaymentDecisionError(f"{field} must be a non-empty string")
    return value.strip()


def _authority_payload(authority: dict[str, Any]) -> dict[str, str]:
    if not isinstance(authority, dict):
        raise ProviderPaymentDecisionError("authority must be an object")
    status = _required_text(authority.get("status"), "authority.status").lower()
    if status not in _AUTHORITY:
        raise ProviderPaymentDecisionError(
            "authority.status must be authorized, revoked, expired, or unknown"
        )
    evidence_ref = _required_text(authority.get("evidenceRef"), "authority.evidenceRef")
    return {"status": status, "evidenceRef": evidence_ref}


def _retry_authority(
    adapter: dict[str, Any], reconciliation: dict[str, Any]
) -> tuple[str, bool, str | None]:
    """Map provider retry semantics into the stricter unified decision vocabulary."""
    if reconciliation["outcome"] != "failed":
        return "not_applicable", False, None

    schema = adapter["schema"]
    if schema == ADAPTER_SCHEMA_V3:
        status = str(adapter.get("retrySemanticsStatus", "unresolved")).lower()
        if status == "documented":
            return "documented", bool(reconciliation.get("retryAllowed", False)), None
        return "unresolved", False, "provider_retry_semantics_unresolved"

    if schema == ADAPTER_SCHEMA_V2:
        # v0.2 can represent evidence-precedence uncertainty, but it has no field that
        # can establish retry authority. The legacy reconciler's retryAllowed value is
        # therefore deliberately NOT promoted into a monetary authorization here.
        return "unresolved", False, "adapter_schema_does_not_encode_retry_authority"

    if schema == ADAPTER_SCHEMA_V1:
        # v0.1 requires an explicit retryPolicy contract. Preserve its final-failure
        # decision while keeping the stronger unified gate as the final authority.
        return "documented", bool(reconciliation.get("retryAllowed", False)), None

    raise ProviderPaymentDecisionError(f"unsupported adapter schema: {schema}")


def evaluate_provider_payment_decision(
    adapter: dict[str, Any],
    observations: dict[str, Any],
    authority: dict[str, Any],
    *,
    fulfillment: dict[str, Any] | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Reconcile provider evidence and derive one fail-closed agent-payment decision."""
    validate_provider_adapter(adapter)
    authority_state = _authority_payload(authority)
    reconciliation = reconcile_provider_observations(adapter, observations)

    logical_operation_id = _required_text(
        reconciliation.get("logicalOperationId"), "reconciliation.logicalOperationId"
    )
    execution_id = _required_text(
        reconciliation.get("executionId"), "reconciliation.executionId"
    )
    selected = reconciliation.get("selectedEvidence")
    if not isinstance(selected, dict):
        raise ProviderPaymentDecisionError("reconciliation.selectedEvidence must be an object")
    payment_evidence_ref = _required_text(
        selected.get("evidenceRef"), "reconciliation.selectedEvidence.evidenceRef"
    )

    retry_status, retry_allowed, retry_reason = _retry_authority(adapter, reconciliation)

    if fulfillment is None:
        fulfillment_state: dict[str, Any] = {
            "required": False,
            "outcome": "not_applicable",
            "recoveryStatus": "not_applicable",
        }
    elif not isinstance(fulfillment, dict):
        raise ProviderPaymentDecisionError("fulfillment must be an object")
    else:
        fulfillment_state = dict(fulfillment)

    resolved_decision_id = decision_id or (
        f"{adapter['providerId']}:{logical_operation_id}:{execution_id}"
    )
    decision_input = {
        "schema": "cgqa.agent-payment-decision-input.v0.1",
        "decisionId": resolved_decision_id,
        "logicalOperationId": logical_operation_id,
        "authority": authority_state,
        "payment": {
            "outcome": reconciliation["outcome"],
            "reconciliationStatus": reconciliation["status"],
            "evidenceRef": payment_evidence_ref,
            "retryAuthorityStatus": retry_status,
            "retryAllowed": retry_allowed,
        },
        "fulfillment": fulfillment_state,
    }
    decision = evaluate_agent_payment_decision(decision_input)

    return {
        "schema": RESULT_SCHEMA,
        "providerId": adapter["providerId"],
        "profileVersion": adapter["profileVersion"],
        "adapterSchema": adapter["schema"],
        "logicalOperationId": logical_operation_id,
        "executionId": execution_id,
        "reconciliation": reconciliation,
        "retryAuthority": {
            "status": retry_status,
            "allowed": retry_allowed,
            "reason": retry_reason,
        },
        "decisionInput": decision_input,
        "decision": decision,
        "authority": {
            "classification": "PUBLIC_CONTRACT_COMPOSITION",
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }
