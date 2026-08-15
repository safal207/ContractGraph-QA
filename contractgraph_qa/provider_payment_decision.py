"""Bridge reviewed public provider profiles into the Unified Payment Gate.

The bridge never calls a provider and never infers financial authority. It composes
already-captured provider observations with explicit authority evidence, applies
fail-closed retry-authority semantics, and delegates the final decision to the
repository's Unified Agent Payment Decision Gate.
"""

from __future__ import annotations

from typing import Any

from contractgraph_qa.agent_payment_decision import evaluate_agent_payment_decision
from contractgraph_qa.provider_adapter import (
    ADAPTER_SCHEMA_V3,
    reconcile_provider_observations,
    validate_provider_adapter,
)

RESULT_SCHEMA = "cgqa.provider-payment-decision.v0.1"
_AUTHORITY = {"authorized", "revoked", "expired", "unknown"}
_REVIEWED_PROFILES: dict[str, dict[str, Any]] = {
    "crossmint-wallet-transactions-public": {
        "label": "Crossmint",
        "profileVersion": "0.2",
        "evidenceRoles": {
            "get-transaction": True,
            "wallet-transfer-webhook": False,
        },
        "evidenceRoleError": (
            "reviewed Crossmint profile requires GET transaction as finality authority "
            "and webhook as notification evidence"
        ),
    },
    "stripe-payment-intents-public": {
        "label": "Stripe PaymentIntents",
        "profileVersion": "0.1",
        "evidenceRoles": {
            "get-payment-intent": True,
            "payment-intent-webhook": False,
        },
        "evidenceRoleError": (
            "reviewed Stripe PaymentIntents profile requires GET PaymentIntent as "
            "finality authority and webhook as notification evidence"
        ),
    },
}


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


def _validate_reviewed_profile(adapter: dict[str, Any]) -> None:
    """Accept only exact reviewed AFSP public-contract profiles."""
    validate_provider_adapter(adapter)
    provider_id = _required_text(adapter.get("providerId"), "providerId")
    profile = _REVIEWED_PROFILES.get(provider_id)
    if profile is None:
        raise ProviderPaymentDecisionError(
            f"providerId={provider_id} is not a reviewed AFSP profile"
        )

    label = str(profile["label"])
    if adapter.get("schema") != ADAPTER_SCHEMA_V3:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile requires Provider Adapter Contract v0.3"
        )
    if adapter.get("profileVersion") != profile["profileVersion"]:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile requires profileVersion={profile['profileVersion']}"
        )

    create = adapter.get("create")
    if not isinstance(create, dict) or create.get("supportsIdempotencyKey") is not True:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile requires documented idempotent creation"
        )
    if create.get("sameKeyReplayDocumented") is not True:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile requires documented same-key replay"
        )

    if adapter.get("evidencePrecedenceStatus") != "unresolved":
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile keeps complete evidence precedence unresolved"
        )
    if adapter.get("evidencePrecedence") != []:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile must not invent a complete evidence ordering"
        )
    if adapter.get("retrySemanticsStatus") != "unresolved":
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile keeps new-operation retry authority unresolved"
        )
    if adapter.get("retryAllowedAfterProviderStates") != []:
        raise ProviderPaymentDecisionError(
            f"reviewed {label} profile must not invent retry-authorized provider states"
        )

    evidence_sources = adapter.get("evidenceSources")
    if not isinstance(evidence_sources, list):
        raise ProviderPaymentDecisionError(
            f"reviewed {label} evidenceSources must be an array"
        )
    roles = {
        str(item.get("kind")): item.get("authoritativeForFinality")
        for item in evidence_sources
        if isinstance(item, dict)
    }
    if roles != profile["evidenceRoles"]:
        raise ProviderPaymentDecisionError(str(profile["evidenceRoleError"]))


def _retry_authority(reconciliation: dict[str, Any]) -> tuple[str, bool, str | None]:
    """Map provider reconciliation into explicit money-retry authority."""
    if reconciliation["outcome"] != "failed":
        return "not_applicable", False, None

    if reconciliation.get("retryAllowed") is True:
        return "documented", True, None

    reason = reconciliation.get("retryBlockReason")
    if reason == "retry_semantics_unresolved":
        return "unresolved", False, reason

    return "documented", False, (
        str(reason) if reason else "retry_not_documented_for_state"
    )


def evaluate_provider_payment_decision(
    adapter: dict[str, Any],
    observations: dict[str, Any],
    authority: dict[str, Any],
    *,
    fulfillment: dict[str, Any] | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    """Reconcile reviewed provider evidence and derive a fail-closed decision."""
    _validate_reviewed_profile(adapter)
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

    retry_status, retry_allowed, retry_reason = _retry_authority(reconciliation)

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
