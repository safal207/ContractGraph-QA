"""Unified Agent Payment Decision Gate v0.1.

This layer does not discover provider semantics. It consumes normalized authority,
payment reconciliation, retry-authority, and fulfillment evidence and derives one
fail-closed next-action decision for an autonomous financial agent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INPUT_SCHEMA = "cgqa.agent-payment-decision-input.v0.1"
RESULT_SCHEMA = "cgqa.agent-payment-decision-result.v0.1"
GATE_ID = "agent-payment-decision-v0.1"

DECISIONS = {"ALLOW", "HOLD", "STOP", "RECONCILE", "COMPENSATE"}
_AUTHORITY = {"authorized", "revoked", "expired", "unknown"}
_PAYMENT = {"not_started", "committed", "failed", "pending", "unknown"}
_RECONCILIATION = {"not_started", "final", "nonfinal"}
_RETRY_AUTHORITY = {"not_applicable", "documented", "unresolved"}
_FULFILLMENT = {"not_applicable", "delivered", "not_delivered", "unknown"}
_RECOVERY = {"not_applicable", "documented", "unresolved"}


class AgentPaymentDecisionError(ValueError):
    """Raised when a decision input is structurally invalid."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentPaymentDecisionError(f"{field} must be a non-empty string")
    return value.strip()


def _enum(value: object, field: str, allowed: set[str]) -> str:
    normalized = _required_text(value, field).lower()
    if normalized not in allowed:
        raise AgentPaymentDecisionError(
            f"{field} must be one of {', '.join(sorted(allowed))}"
        )
    return normalized


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentPaymentDecisionError(f"unable to read decision input: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AgentPaymentDecisionError(f"invalid decision JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentPaymentDecisionError("decision input root must be an object")
    return payload


def _evidence_ref(section: dict[str, Any], field: str, *, required: bool = True) -> str | None:
    value = section.get("evidenceRef")
    if value is None and not required:
        return None
    return _required_text(value, f"{field}.evidenceRef")


def evaluate_agent_payment_decision(payload: dict[str, Any]) -> dict[str, Any]:
    """Return one fail-closed next-action decision from normalized financial state."""
    if payload.get("schema") != INPUT_SCHEMA:
        raise AgentPaymentDecisionError(f"schema must be {INPUT_SCHEMA}")

    decision_id = _required_text(payload.get("decisionId"), "decisionId")
    logical_operation_id = _required_text(
        payload.get("logicalOperationId"), "logicalOperationId"
    )

    authority = payload.get("authority")
    if not isinstance(authority, dict):
        raise AgentPaymentDecisionError("authority must be an object")
    authority_status = _enum(authority.get("status"), "authority.status", _AUTHORITY)
    authority_ref = _evidence_ref(authority, "authority")

    payment = payload.get("payment")
    if not isinstance(payment, dict):
        raise AgentPaymentDecisionError("payment must be an object")
    payment_outcome = _enum(payment.get("outcome"), "payment.outcome", _PAYMENT)
    reconciliation_status = _enum(
        payment.get("reconciliationStatus"),
        "payment.reconciliationStatus",
        _RECONCILIATION,
    )
    payment_ref = _evidence_ref(
        payment,
        "payment",
        required=payment_outcome != "not_started",
    )

    retry_status = _enum(
        payment.get("retryAuthorityStatus"),
        "payment.retryAuthorityStatus",
        _RETRY_AUTHORITY,
    )
    retry_allowed = payment.get("retryAllowed")
    if not isinstance(retry_allowed, bool):
        raise AgentPaymentDecisionError("payment.retryAllowed must be boolean")
    if retry_status == "unresolved" and retry_allowed:
        raise AgentPaymentDecisionError(
            "unresolved retry authority cannot set retryAllowed=true"
        )
    if payment_outcome != "failed" and retry_allowed:
        raise AgentPaymentDecisionError(
            "retryAllowed=true is only meaningful for a failed payment"
        )

    fulfillment = payload.get("fulfillment")
    if not isinstance(fulfillment, dict):
        raise AgentPaymentDecisionError("fulfillment must be an object")
    required = fulfillment.get("required")
    if not isinstance(required, bool):
        raise AgentPaymentDecisionError("fulfillment.required must be boolean")
    fulfillment_outcome = _enum(
        fulfillment.get("outcome"), "fulfillment.outcome", _FULFILLMENT
    )
    fulfillment_recovery = _enum(
        fulfillment.get("recoveryStatus"),
        "fulfillment.recoveryStatus",
        _RECOVERY,
    )
    fulfillment_ref = _evidence_ref(
        fulfillment,
        "fulfillment",
        required=fulfillment_outcome != "not_applicable",
    )

    if not required and fulfillment_outcome != "not_applicable":
        raise AgentPaymentDecisionError(
            "fulfillment.outcome must be not_applicable when fulfillment.required=false"
        )
    if required and fulfillment_outcome == "not_applicable":
        raise AgentPaymentDecisionError(
            "fulfillment.outcome cannot be not_applicable when fulfillment.required=true"
        )

    decision: str
    reason: str
    blockers: list[str] = []

    # Authority is the outermost gate. Revocation/expiry is terminal for the
    # logical operation; unknown authority remains contained rather than inferred.
    if authority_status in {"revoked", "expired"}:
        decision = "STOP"
        reason = f"authority_{authority_status}"
        blockers.append("authority")
    elif authority_status == "unknown":
        decision = "HOLD"
        reason = "authority_unresolved"
        blockers.append("authority")
    elif payment_outcome == "not_started":
        if reconciliation_status != "not_started":
            raise AgentPaymentDecisionError(
                "not_started payment requires reconciliationStatus=not_started"
            )
        decision = "ALLOW"
        reason = "authorized_initial_payment"
    elif reconciliation_status != "final" or payment_outcome in {"pending", "unknown"}:
        decision = "RECONCILE"
        reason = "payment_outcome_nonfinal"
        blockers.append("payment_finality")
    elif payment_outcome == "committed":
        if required and fulfillment_outcome == "unknown":
            decision = "RECONCILE"
            reason = "fulfillment_unknown_after_commit"
            blockers.append("fulfillment_finality")
        elif required and fulfillment_outcome == "not_delivered":
            decision = "COMPENSATE"
            reason = "committed_payment_not_fulfilled"
            blockers.append("compensation_disposition")
        else:
            decision = "STOP"
            reason = "logical_operation_already_satisfied"
    elif payment_outcome == "failed":
        if retry_status == "unresolved":
            decision = "HOLD"
            reason = "retry_authority_unresolved"
            blockers.append("retry_authority")
        elif retry_status == "documented" and retry_allowed:
            decision = "ALLOW"
            reason = "documented_retry_authority"
        else:
            decision = "STOP"
            reason = "retry_not_authorized"
    else:  # defensive; enum validation above should make this unreachable.
        decision = "HOLD"
        reason = "unclassified_state"
        blockers.append("decision_model")

    if decision not in DECISIONS:  # pragma: no cover
        raise AgentPaymentDecisionError("internal decision is outside the contract")

    monetary_action_allowed = decision == "ALLOW"
    return {
        "schema": RESULT_SCHEMA,
        "gate": GATE_ID,
        "decisionId": decision_id,
        "logicalOperationId": logical_operation_id,
        "decision": decision,
        "reason": reason,
        "monetaryActionAllowed": monetary_action_allowed,
        "blockers": blockers,
        "state": {
            "authority": {"status": authority_status, "evidenceRef": authority_ref},
            "payment": {
                "outcome": payment_outcome,
                "reconciliationStatus": reconciliation_status,
                "evidenceRef": payment_ref,
                "retryAuthorityStatus": retry_status,
                "retryAllowed": retry_allowed,
            },
            "fulfillment": {
                "required": required,
                "outcome": fulfillment_outcome,
                "evidenceRef": fulfillment_ref,
                "recoveryStatus": fulfillment_recovery,
            },
        },
        "invariants": {
            "authorityRequiredForMoney": not monetary_action_allowed
            or authority_status == "authorized",
            "nonfinalPaymentBlocksMoney": not monetary_action_allowed
            or payment_outcome == "not_started"
            or reconciliation_status == "final",
            "retryRequiresExplicitAuthority": not monetary_action_allowed
            or payment_outcome != "failed"
            or (retry_status == "documented" and retry_allowed),
            "committedPaymentRequiresFulfillmentDisposition": not monetary_action_allowed
            or payment_outcome != "committed",
        },
        "authority": {
            "classification": "RESEARCH_ONLY",
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }


def evaluate_agent_payment_decision_file(path: Path) -> dict[str, Any]:
    return evaluate_agent_payment_decision(_load(path))
