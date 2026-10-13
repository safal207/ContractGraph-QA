"""Replay-only retry safety adapter for ambiguous trading operations.

This module composes the existing payment-recovery and economic-cardinality
engines. It does not place orders, call exchanges, or authorize execution.
"""

from __future__ import annotations

from typing import Any

from contractgraph_qa.economic_cardinality import (
    economic_cardinality_model_from_dict,
    run_economic_cardinality_model,
)
from contractgraph_qa.payment_recovery import evaluate_payment_recovery_scenario

SCENARIO_SCHEMA = "cgqa.trading-recovery-replay.v0.1"
RESULT_SCHEMA = "cgqa.trading-recovery-replay-result.v0.1"

_RETRY_ALLOWED = "RETRY_ALLOWED"
_BLOCK_ALREADY_APPLIED = "BLOCK_ALREADY_APPLIED"
_BLOCK_DUPLICATE_EFFECT = "BLOCK_DUPLICATE_EFFECT"
_BLOCK_RECOVERY_INVARIANT = "BLOCK_RECOVERY_INVARIANT"
_HOLD_UNRESOLVED = "HOLD_UNRESOLVED"
_HOLD_NON_AUTHORITATIVE = "HOLD_NON_AUTHORITATIVE_RECONCILIATION"
_HOLD_INCOMPLETE = "HOLD_EFFECT_EVIDENCE_INCOMPLETE"
_HOLD_CONFLICT = "HOLD_EVIDENCE_CONFLICT"


class TradingRecoveryError(ValueError):
    """Raised when a trading recovery replay input is structurally invalid."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TradingRecoveryError(f"{field} must be a non-empty string")
    return value.strip()


def _required_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise TradingRecoveryError(f"{field} must be boolean")
    return value


def _last_reconcile_outcome(
    recovery_scenario: dict[str, Any], logical_operation_id: str
) -> str | None:
    outcome: str | None = None
    events = recovery_scenario.get("events", [])
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "reconcile":
            continue
        if event.get("logicalOperationId") != logical_operation_id:
            continue
        raw = event.get("outcome")
        if isinstance(raw, str):
            outcome = raw.strip().lower()
    return outcome


def evaluate_trading_recovery_replay(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify retry safety from declared replay evidence, fail-closed.

    ``RETRY_ALLOWED`` is only a policy verdict over the supplied normalized
    evidence. It never means that execution is authorized.
    """
    if not isinstance(payload, dict):
        raise TradingRecoveryError("scenario root must be an object")
    if payload.get("schema") != SCENARIO_SCHEMA:
        raise TradingRecoveryError(f"schema must be {SCENARIO_SCHEMA}")

    scenario_id = _required_text(payload.get("scenarioId"), "scenarioId")
    logical_operation_id = _required_text(
        payload.get("logicalOperationId"), "logicalOperationId"
    )

    effect = payload.get("effect")
    if not isinstance(effect, dict):
        raise TradingRecoveryError("effect must be an object")
    action_id = _required_text(effect.get("actionId"), "effect.actionId")
    effect_key = _required_text(effect.get("effectKey"), "effect.effectKey")

    evidence_policy = payload.get("evidencePolicy")
    if not isinstance(evidence_policy, dict):
        raise TradingRecoveryError("evidencePolicy must be an object")
    reconciliation_authoritative = _required_bool(
        evidence_policy.get("reconciliationAuthoritative"),
        "evidencePolicy.reconciliationAuthoritative",
    )
    effect_evidence_complete = _required_bool(
        evidence_policy.get("effectEvidenceComplete"),
        "evidencePolicy.effectEvidenceComplete",
    )

    recovery_scenario = payload.get("recoveryScenario")
    if not isinstance(recovery_scenario, dict):
        raise TradingRecoveryError("recoveryScenario must be an object")
    cardinality_payload = payload.get("cardinalityModel")
    if not isinstance(cardinality_payload, dict):
        raise TradingRecoveryError("cardinalityModel must be an object")

    recovery_result = evaluate_payment_recovery_scenario(recovery_scenario)
    cardinality_model = economic_cardinality_model_from_dict(cardinality_payload)
    cardinality_result = run_economic_cardinality_model(cardinality_model)

    occurrence_ids = sorted(
        {
            event.occurrence_id
            for event in cardinality_model.events
            if event.applied
            and event.action_id == action_id
            and event.effect_key == effect_key
        }
    )
    occurrence_count = len(occurrence_ids)
    reconcile_outcome = _last_reconcile_outcome(
        recovery_scenario, logical_operation_id
    )
    unresolved = logical_operation_id in set(
        recovery_result["observed"]["unresolvedLogicalOperations"]
    )
    violation_codes = sorted(
        {str(item["code"]) for item in recovery_result["violations"]}
    )
    substantive_recovery_violations = [
        code for code in violation_codes if code != "APR-009_TRACE_ENDS_UNRESOLVED"
    ]

    if occurrence_count > 1:
        state = "MULTIPLE"
        retry_verdict = _BLOCK_DUPLICATE_EFFECT
        reason = "more than one distinct applied occurrence is declared for the target effect"
    elif substantive_recovery_violations:
        state = "UNKNOWN"
        retry_verdict = _BLOCK_RECOVERY_INVARIANT
        reason = "the recovery trace violates one or more fail-closed recovery invariants"
    elif unresolved or reconcile_outcome not in {"committed", "failed"}:
        state = "UNKNOWN"
        retry_verdict = _HOLD_UNRESOLVED
        reason = "the target logical operation does not have a final reconciliation outcome"
    elif not reconciliation_authoritative:
        state = "UNKNOWN"
        retry_verdict = _HOLD_NON_AUTHORITATIVE
        reason = "the final reconciliation evidence is not declared authoritative"
    elif not effect_evidence_complete:
        state = "UNKNOWN"
        retry_verdict = _HOLD_INCOMPLETE
        reason = "source-to-normalized-effect completeness is not established"
    elif reconcile_outcome == "failed" and occurrence_count == 0:
        state = "ZERO"
        retry_verdict = _RETRY_ALLOWED
        reason = "authoritative final failure plus complete target-effect evidence establishes zero applied occurrences"
    elif reconcile_outcome == "committed" and occurrence_count == 1:
        state = "ONE"
        retry_verdict = _BLOCK_ALREADY_APPLIED
        reason = "authoritative commit plus one applied target occurrence establishes that the effect already happened"
    else:
        state = "UNKNOWN"
        retry_verdict = _HOLD_CONFLICT
        reason = "reconciliation outcome and declared applied-effect cardinality are inconsistent"

    return {
        "schema": RESULT_SCHEMA,
        "scenarioId": scenario_id,
        "logicalOperationId": logical_operation_id,
        "stateCardinality": state,
        "retryVerdict": retry_verdict,
        "executionAuthorized": False,
        "reason": reason,
        "observed": {
            "reconcileOutcome": reconcile_outcome,
            "appliedOccurrenceCount": occurrence_count,
            "appliedOccurrenceIds": occurrence_ids,
            "recoveryStatus": recovery_result["status"],
            "recoveryViolationCodes": violation_codes,
            "cardinalityStatus": cardinality_result["status"],
        },
        "evidencePolicy": {
            "reconciliationAuthoritative": reconciliation_authoritative,
            "effectEvidenceComplete": effect_evidence_complete,
        },
        "authority": {
            "classification": "REPLAY_ONLY",
            "productionAuthorization": False,
            "financialAuthorization": False,
            "liveExecution": False,
            "claimBoundary": (
                "exact over supplied normalized replay inputs; source authenticity, "
                "source-to-event completeness, and production applicability remain external"
            ),
        },
    }
