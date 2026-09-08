"""Replay-only recovery cardinality and retry-idempotence verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.economic_cardinality import (
    economic_cardinality_model_from_dict,
    run_economic_cardinality_model,
)
from contractgraph_qa.payment_recovery import evaluate_payment_recovery_scenario

SCENARIO_SCHEMA = "cgqa.replay-recovery-scenario.v0.1"
RESULT_SCHEMA = "cgqa.replay-recovery-result.v0.1"
BENCHMARK_ID = "replay-recovery-idempotence-v0.1"


class ReplayRecoveryError(ValueError):
    """Raised when a replay-recovery scenario is structurally invalid."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayRecoveryError(f"{field} must be a non-empty string")
    return value.strip()


def load_replay_recovery_scenario(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReplayRecoveryError(f"unable to read scenario: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReplayRecoveryError(f"invalid scenario JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayRecoveryError("scenario root must be an object")
    return payload


def _retry_identity_result(retry: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    prior_logical = _text(
        retry.get("priorLogicalOperationId"), "retry.priorLogicalOperationId"
    )
    proposed_logical = _text(
        retry.get("proposedLogicalOperationId"), "retry.proposedLogicalOperationId"
    )
    prior_execution = _text(retry.get("priorExecutionId"), "retry.priorExecutionId")
    proposed_execution = _text(
        retry.get("proposedExecutionId"), "retry.proposedExecutionId"
    )
    prior_key = _text(retry.get("priorIdempotencyKey"), "retry.priorIdempotencyKey")
    proposed_key = _text(
        retry.get("proposedIdempotencyKey"), "retry.proposedIdempotencyKey"
    )

    events: list[dict[str, Any]] = [
        {"seq": 1, "type": "authorize", "logicalOperationId": prior_logical},
        {
            "seq": 2,
            "type": "submit",
            "logicalOperationId": prior_logical,
            "executionId": prior_execution,
            "idempotencyKey": prior_key,
        },
        {
            "seq": 3,
            "type": "ambiguous",
            "logicalOperationId": prior_logical,
            "executionId": prior_execution,
        },
        {
            "seq": 4,
            "type": "reconcile",
            "logicalOperationId": prior_logical,
            "evidenceKind": "replay-cardinality",
            "evidenceRef": f"{scenario_id}:zero-confirmed",
            "outcome": "failed",
        },
    ]

    if proposed_logical != prior_logical:
        events.append(
            {
                "seq": len(events) + 1,
                "type": "authorize",
                "logicalOperationId": proposed_logical,
            }
        )

    events.append(
        {
            "seq": len(events) + 1,
            "type": "retry",
            "logicalOperationId": proposed_logical,
            "executionId": proposed_execution,
            "idempotencyKey": proposed_key,
            "retryOfExecutionId": prior_execution,
        }
    )

    result = evaluate_payment_recovery_scenario(
        {
            "schema": "cgqa.agent-payment-recovery-scenario.v0.1",
            "scenarioId": f"{scenario_id}:retry-identity",
            "events": events,
        }
    )
    return {
        "status": result["status"],
        "invariants": {
            "logicalOperationContinuity": result["invariants"][
                "logicalOperationContinuity"
            ],
            "idempotencyContinuity": result["invariants"]["idempotencyContinuity"],
        },
        "violationCodes": [item["code"] for item in result["violations"]],
    }


def evaluate_replay_recovery_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify declared replay evidence and return a fail-closed retry verdict."""
    if not isinstance(payload, dict):
        raise ReplayRecoveryError("scenario root must be an object")
    if payload.get("schema") != SCENARIO_SCHEMA:
        raise ReplayRecoveryError(f"schema must be {SCENARIO_SCHEMA}")

    scenario_id = _text(payload.get("scenarioId"), "scenarioId")
    action_id = _text(payload.get("actionId"), "actionId")
    effect_key = _text(payload.get("effectKey"), "effectKey")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ReplayRecoveryError("evidence must be a non-empty array")

    source_ids: set[str] = set()
    normalized_sources: list[dict[str, Any]] = []
    economic_events: list[dict[str, Any]] = []
    all_occurrences: set[str] = set()
    complete_sets: list[set[str]] = []

    for index, item in enumerate(evidence):
        field = f"evidence[{index}]"
        if not isinstance(item, dict):
            raise ReplayRecoveryError(f"{field} must be an object")

        source_id = _text(item.get("sourceId"), f"{field}.sourceId")
        if source_id in source_ids:
            raise ReplayRecoveryError(f"duplicate evidence sourceId: {source_id}")
        source_ids.add(source_id)

        complete = item.get("complete")
        if not isinstance(complete, bool):
            raise ReplayRecoveryError(f"{field}.complete must be boolean")

        occurrences_raw = item.get("occurrenceIds")
        if not isinstance(occurrences_raw, list):
            raise ReplayRecoveryError(f"{field}.occurrenceIds must be an array")

        occurrences = [
            _text(value, f"{field}.occurrenceIds[{occurrence_index}]")
            for occurrence_index, value in enumerate(occurrences_raw)
        ]
        occurrence_set = set(occurrences)
        if len(occurrence_set) != len(occurrences):
            raise ReplayRecoveryError(
                f"{field}.occurrenceIds must not contain duplicates"
            )

        normalized_sources.append(
            {
                "sourceId": source_id,
                "complete": complete,
                "occurrenceIds": sorted(occurrence_set),
            }
        )
        if complete:
            complete_sets.append(occurrence_set)

        all_occurrences.update(occurrence_set)
        for occurrence_id in sorted(occurrence_set):
            economic_events.append(
                {
                    "eventId": f"{source_id}:{occurrence_id}",
                    "actionId": action_id,
                    "effectKey": effect_key,
                    "occurrenceId": occurrence_id,
                    "applied": True,
                }
            )

    economic = run_economic_cardinality_model(
        economic_cardinality_model_from_dict(
            {
                "schemaVersion": "0.1",
                "modelId": f"{scenario_id}:economic-cardinality",
                "invariantId": "at-most-once-economic-effect",
                "events": economic_events,
                "scope": "replay-only normalized evidence",
            }
        )
    )

    evidence_conflict = False
    if complete_sets:
        canonical_complete = complete_sets[0]
        evidence_conflict = any(
            candidate != canonical_complete for candidate in complete_sets[1:]
        )
        if not all_occurrences.issubset(canonical_complete):
            evidence_conflict = True

    retry_check: dict[str, Any] | None = None

    if evidence_conflict:
        cardinality = "UNKNOWN"
        verdict = "HOLD_EVIDENCE_CONFLICT"
        reason_codes = ["RR-002_EVIDENCE_CONFLICT"]
    elif economic["status"] == "fail":
        cardinality = "MULTIPLE"
        verdict = "BLOCK_DUPLICATE_EFFECT"
        reason_codes = ["RR-004_DUPLICATE_EFFECT"]
    elif not complete_sets:
        cardinality = "UNKNOWN"
        verdict = "HOLD_UNRESOLVED"
        reason_codes = ["RR-001_EVIDENCE_INCOMPLETE"]
    else:
        confirmed = len(complete_sets[0])
        if confirmed == 0:
            cardinality = "ZERO"
            retry_raw = payload.get("retry")
            if not isinstance(retry_raw, dict):
                raise ReplayRecoveryError(
                    "retry must be an object when cardinality is ZERO"
                )
            retry_check = _retry_identity_result(retry_raw, scenario_id)
            if retry_check["status"] == "pass":
                verdict = "RETRY_ALLOWED"
                reason_codes = ["RR-000_ZERO_CONFIRMED"]
            else:
                verdict = "BLOCK_RETRY_IDENTITY"
                reason_codes = ["RR-005_RETRY_IDENTITY_INVALID"]
        elif confirmed == 1:
            cardinality = "ONE"
            verdict = "BLOCK_ALREADY_APPLIED"
            reason_codes = ["RR-003_ALREADY_APPLIED"]
        else:  # defensive; economic cardinality should already detect this
            cardinality = "MULTIPLE"
            verdict = "BLOCK_DUPLICATE_EFFECT"
            reason_codes = ["RR-004_DUPLICATE_EFFECT"]

    return {
        "schema": RESULT_SCHEMA,
        "benchmark": BENCHMARK_ID,
        "scenarioId": scenario_id,
        "cardinality": cardinality,
        "verdict": verdict,
        "reasonCodes": reason_codes,
        "observed": {
            "sourceCount": len(normalized_sources),
            "completeSourceCount": sum(
                1 for item in normalized_sources if item["complete"]
            ),
            "distinctConfirmedOccurrenceCount": len(all_occurrences),
            "sources": normalized_sources,
        },
        "economicCardinality": {
            "status": economic["status"],
            "violations": economic["violations"],
            "semantics": economic["semantics"],
        },
        "retryIdentity": retry_check,
        "authority": {
            "classification": "RESEARCH_ONLY",
            "executionAuthorized": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
        "semantics": {
            "retryAllowedMeaning": (
                "policy verdict only; this evaluator never submits or resubmits an action"
            ),
            "unknownPolicy": "fail closed",
            "claimBoundary": (
                "exact over declared evidence; source completeness and source "
                "truthfulness are external"
            ),
        },
    }


def evaluate_replay_recovery_file(path: Path) -> dict[str, Any]:
    return evaluate_replay_recovery_scenario(load_replay_recovery_scenario(path))
