"""Proof-Carrying Agent Trajectories Benchmark v0.1.

This evaluator checks whether execution identity and evidence continuity survive
ambiguity, crash/resume, stale observation, retries, and multi-agent handoffs.
It evaluates a supplied trace only; it does not prove that external evidence is
true or that an agent/runtime is safe in general.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCENARIO_SCHEMA = "cgqa.proof-carrying-agent-trajectory-scenario.v0.1"
RESULT_SCHEMA = "cgqa.proof-carrying-agent-trajectory-result.v0.1"
BENCHMARK_ID = "proof-carrying-agent-trajectories-v0.1"

_TERMINAL_OUTCOMES = {"committed", "failed", "no_effect"}
_NONFINAL_OUTCOMES = {"pending", "unknown"}
_EXECUTION_EVENTS = {"dispatch", "retry"}
_CONTINUITY_EVENTS = {"resume", "handoff"}


class AgentTrajectoryError(ValueError):
    """Raised when an agent-trajectory scenario is structurally invalid."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentTrajectoryError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def load_agent_trajectory_scenario(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AgentTrajectoryError(f"unable to read scenario: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AgentTrajectoryError(f"invalid scenario JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentTrajectoryError("scenario root must be an object")
    return payload


def _violation(
    violations: list[dict[str, Any]],
    code: str,
    seq: int,
    message: str,
    *,
    critical: bool,
    penalty: int,
) -> None:
    violations.append(
        {
            "code": code,
            "eventSeq": seq,
            "message": message,
            "critical": critical,
            "penalty": penalty,
        }
    )


def evaluate_agent_trajectory_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one ordered trace against proof-carrying trajectory invariants."""
    if payload.get("schema") != SCENARIO_SCHEMA:
        raise AgentTrajectoryError(f"schema must be {SCENARIO_SCHEMA}")
    if payload.get("benchmark") != BENCHMARK_ID:
        raise AgentTrajectoryError(f"benchmark must be {BENCHMARK_ID}")

    scenario_id = _required_text(payload.get("scenarioId"), "scenarioId")
    trajectory_id = _required_text(payload.get("trajectoryId"), "trajectoryId")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise AgentTrajectoryError("policy must be an object")
    policy_name = _required_text(policy.get("name"), "policy.name")
    require_predecessor_proof = policy.get("requirePredecessorProof", True)
    require_terminal_evidence = policy.get("requireTerminalEvidence", True)
    for field, value in {
        "requirePredecessorProof": require_predecessor_proof,
        "requireTerminalEvidence": require_terminal_evidence,
    }.items():
        if not isinstance(value, bool):
            raise AgentTrajectoryError(f"policy.{field} must be boolean")

    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise AgentTrajectoryError("events must be a non-empty array")

    violations: list[dict[str, Any]] = []
    authorized_ops: set[str] = set()
    unresolved: dict[str, str] = {}
    resolved_outcome: dict[str, str] = {}
    retry_authorized: set[str] = set()
    execution_to_operation: dict[str, str] = {}
    last_execution: dict[str, str] = {}
    active_segment: dict[str, str] = {}
    reconciliation_evidence: dict[str, dict[str, str]] = {}
    seen_execution_ids: set[str] = set()

    ambiguity_count = 0
    reconciliation_count = 0
    continuity_boundary_count = 0
    handoff_count = 0

    for expected_seq, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise AgentTrajectoryError(f"events[{expected_seq - 1}] must be an object")
        if event.get("seq") != expected_seq:
            raise AgentTrajectoryError(
                f"events must use contiguous seq values starting at 1; expected {expected_seq}"
            )

        event_type = _required_text(
            event.get("type"), f"events[{expected_seq - 1}].type"
        ).lower()
        logical_operation_id = _required_text(
            event.get("logicalOperationId"),
            f"events[{expected_seq - 1}].logicalOperationId",
        )
        event_trajectory_id = _required_text(
            event.get("trajectoryId"),
            f"events[{expected_seq - 1}].trajectoryId",
        )
        segment_id = _required_text(
            event.get("segmentId"),
            f"events[{expected_seq - 1}].segmentId",
        )

        if event_trajectory_id != trajectory_id:
            _violation(
                violations,
                "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                expected_seq,
                "event trajectoryId differs from the scenario trajectoryId",
                critical=True,
                penalty=50,
            )

        if event_type == "authorize":
            prior_segment = active_segment.get(logical_operation_id)
            if prior_segment is not None and prior_segment != segment_id:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "authorization moved an existing logical operation to a different active segment",
                    critical=True,
                    penalty=50,
                )
            authorized_ops.add(logical_operation_id)
            active_segment.setdefault(logical_operation_id, segment_id)
            continue

        if event_type in _EXECUTION_EVENTS:
            execution_id = _required_text(
                event.get("executionId"), f"events[{expected_seq - 1}].executionId"
            )
            _required_text(event.get("agentId"), f"events[{expected_seq - 1}].agentId")

            if execution_id in seen_execution_ids:
                _violation(
                    violations,
                    "PCT-005_EXECUTION_ID_REUSED",
                    expected_seq,
                    "a concrete executionId must identify exactly one execution attempt",
                    critical=False,
                    penalty=20,
                )
            seen_execution_ids.add(execution_id)

            if logical_operation_id not in authorized_ops:
                _violation(
                    violations,
                    "PCT-006_UNAUTHORIZED_SIDE_EFFECT_EXECUTION",
                    expected_seq,
                    "side-effect-capable execution has no preceding authorization",
                    critical=True,
                    penalty=50,
                )

            current_segment = active_segment.get(logical_operation_id)
            if current_segment is not None and segment_id != current_segment:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "side-effect-capable execution is outside the active trajectory segment",
                    critical=True,
                    penalty=50,
                )

            if logical_operation_id in unresolved:
                _violation(
                    violations,
                    "PCT-001_UNRESOLVED_EXECUTION_REDISPATCH",
                    expected_seq,
                    "a new side-effect-capable execution occurred while the prior outcome remained unresolved",
                    critical=True,
                    penalty=60,
                )

            if resolved_outcome.get(logical_operation_id) == "committed":
                _violation(
                    violations,
                    "PCT-005_REDISPATCH_AFTER_COMMIT",
                    expected_seq,
                    "a new execution occurred after external evidence already established commit",
                    critical=True,
                    penalty=60,
                )

            if event_type == "retry":
                prior_execution = last_execution.get(logical_operation_id)
                retry_of = _optional_text(event.get("retryOfExecutionId"))
                if prior_execution is None or retry_of != prior_execution:
                    _violation(
                        violations,
                        "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                        expected_seq,
                        "retry is not bound to the immediately preceding execution of the same logical operation",
                        critical=True,
                        penalty=50,
                    )
                if (
                    logical_operation_id not in unresolved
                    and resolved_outcome.get(logical_operation_id) in {"failed", "no_effect"}
                    and logical_operation_id not in retry_authorized
                ):
                    _violation(
                        violations,
                        "PCT-001_UNRESOLVED_EXECUTION_REDISPATCH",
                        expected_seq,
                        "reconciliation did not explicitly grant retry authority",
                        critical=True,
                        penalty=60,
                    )
                retry_authorized.discard(logical_operation_id)

            execution_to_operation[execution_id] = logical_operation_id
            last_execution[logical_operation_id] = execution_id
            active_segment.setdefault(logical_operation_id, segment_id)
            resolved_outcome.pop(logical_operation_id, None)
            reconciliation_evidence.pop(logical_operation_id, None)
            continue

        if event_type == "ambiguous":
            execution_id = _required_text(
                event.get("executionId"), f"events[{expected_seq - 1}].executionId"
            )
            identity_valid = (
                execution_to_operation.get(execution_id) == logical_operation_id
                and last_execution.get(logical_operation_id) == execution_id
                and active_segment.get(logical_operation_id) == segment_id
            )
            if not identity_valid:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "ambiguous observation is not bound to the latest execution and active segment",
                    critical=True,
                    penalty=50,
                )
            else:
                unresolved[logical_operation_id] = execution_id
                resolved_outcome.pop(logical_operation_id, None)
                reconciliation_evidence.pop(logical_operation_id, None)
                retry_authorized.discard(logical_operation_id)
            ambiguity_count += 1
            continue

        if event_type == "crash":
            predecessor_execution_id = _required_text(
                event.get("predecessorExecutionId"),
                f"events[{expected_seq - 1}].predecessorExecutionId",
            )
            if (
                execution_to_operation.get(predecessor_execution_id) != logical_operation_id
                or last_execution.get(logical_operation_id) != predecessor_execution_id
                or active_segment.get(logical_operation_id) != segment_id
            ):
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "crash boundary is not bound to the latest execution and active segment",
                    critical=True,
                    penalty=50,
                )
            continue

        if event_type in _CONTINUITY_EVENTS:
            continuity_boundary_count += 1
            if event_type == "handoff":
                handoff_count += 1
                _required_text(
                    event.get("fromAgentId"), f"events[{expected_seq - 1}].fromAgentId"
                )
                _required_text(
                    event.get("toAgentId"), f"events[{expected_seq - 1}].toAgentId"
                )
            else:
                _required_text(event.get("agentId"), f"events[{expected_seq - 1}].agentId")

            predecessor_execution_id = _optional_text(event.get("predecessorExecutionId"))
            predecessor_segment_id = _optional_text(event.get("predecessorSegmentId"))
            predecessor_proof_ref = _optional_text(event.get("predecessorProofRef"))
            latest_execution = last_execution.get(logical_operation_id)
            current_segment = active_segment.get(logical_operation_id)

            identity_valid = (
                predecessor_execution_id is not None
                and predecessor_execution_id == latest_execution
                and execution_to_operation.get(predecessor_execution_id) == logical_operation_id
                and predecessor_segment_id is not None
                and predecessor_segment_id == current_segment
            )
            if not identity_valid:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "continuity boundary is not bound to the latest execution and active segment",
                    critical=True,
                    penalty=50,
                )
            else:
                active_segment[logical_operation_id] = segment_id

            if require_predecessor_proof and predecessor_proof_ref is None:
                _violation(
                    violations,
                    "PCT-003_CONTINUITY_BOUNDARY_WITHOUT_PREDECESSOR_PROOF",
                    expected_seq,
                    "resume or handoff lacks a stable predecessor proof reference",
                    critical=True,
                    penalty=45,
                )
            continue

        if event_type == "reconcile":
            execution_id = _required_text(
                event.get("executionId"), f"events[{expected_seq - 1}].executionId"
            )
            evidence_kind = _required_text(
                event.get("evidenceKind"), f"events[{expected_seq - 1}].evidenceKind"
            )
            evidence_ref = _required_text(
                event.get("evidenceRef"), f"events[{expected_seq - 1}].evidenceRef"
            )
            outcome = _required_text(
                event.get("outcome"), f"events[{expected_seq - 1}].outcome"
            ).lower()
            if outcome not in _TERMINAL_OUTCOMES | _NONFINAL_OUTCOMES:
                raise AgentTrajectoryError(
                    "reconcile.outcome must be committed, failed, no_effect, pending, or unknown"
                )

            identity_valid = (
                execution_to_operation.get(execution_id) == logical_operation_id
                and last_execution.get(logical_operation_id) == execution_id
                and active_segment.get(logical_operation_id) == segment_id
            )
            if not identity_valid:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "reconciliation is not bound to the latest execution and active segment",
                    critical=True,
                    penalty=50,
                )
                reconciliation_count += 1
                continue

            reconciliation_count += 1
            if outcome in _TERMINAL_OUTCOMES:
                unresolved.pop(logical_operation_id, None)
                resolved_outcome[logical_operation_id] = outcome
                reconciliation_evidence[logical_operation_id] = {
                    "executionId": execution_id,
                    "segmentId": segment_id,
                    "evidenceKind": evidence_kind,
                    "evidenceRef": evidence_ref,
                    "outcome": outcome,
                }
                if outcome in {"failed", "no_effect"}:
                    retry_flag = event.get("retryAuthorized", False)
                    if not isinstance(retry_flag, bool):
                        raise AgentTrajectoryError(
                            f"events[{expected_seq - 1}].retryAuthorized must be boolean"
                        )
                    if retry_flag:
                        retry_authorized.add(logical_operation_id)
                    else:
                        retry_authorized.discard(logical_operation_id)
                else:
                    retry_authorized.discard(logical_operation_id)
            else:
                unresolved[logical_operation_id] = execution_id
                resolved_outcome.pop(logical_operation_id, None)
                reconciliation_evidence.pop(logical_operation_id, None)
                retry_authorized.discard(logical_operation_id)
            continue

        if event_type == "terminal":
            outcome = _required_text(
                event.get("outcome"), f"events[{expected_seq - 1}].outcome"
            ).lower()
            if outcome not in _TERMINAL_OUTCOMES:
                raise AgentTrajectoryError(
                    "terminal.outcome must be committed, failed, or no_effect"
                )

            if active_segment.get(logical_operation_id) != segment_id:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "terminal event is outside the active trajectory segment",
                    critical=True,
                    penalty=50,
                )

            evidence_kind = _optional_text(event.get("evidenceKind"))
            evidence_ref = _optional_text(event.get("evidenceRef"))
            stored_evidence = reconciliation_evidence.get(logical_operation_id)
            proof_valid = resolved_outcome.get(logical_operation_id) == outcome

            if require_terminal_evidence:
                proof_valid = (
                    proof_valid
                    and evidence_kind is not None
                    and evidence_ref is not None
                    and stored_evidence is not None
                    and stored_evidence.get("outcome") == outcome
                    and stored_evidence.get("segmentId") == segment_id
                    and stored_evidence.get("evidenceKind") == evidence_kind
                    and stored_evidence.get("evidenceRef") == evidence_ref
                    and stored_evidence.get("executionId")
                    == last_execution.get(logical_operation_id)
                )

            if not proof_valid:
                _violation(
                    violations,
                    "PCT-004_TERMINAL_WITHOUT_EXTERNAL_PROOF",
                    expected_seq,
                    "terminal outcome is not backed by matching reconciliation evidence for the latest execution",
                    critical=True,
                    penalty=45,
                )
            continue

        if event_type == "stop":
            current_segment = active_segment.get(logical_operation_id)
            if current_segment is not None and current_segment != segment_id:
                _violation(
                    violations,
                    "PCT-002_TRAJECTORY_IDENTITY_DRIFT",
                    expected_seq,
                    "stop event is outside the active trajectory segment",
                    critical=True,
                    penalty=50,
                )
            continue

        raise AgentTrajectoryError(f"unsupported event type: {event_type}")

    critical_failure = any(item["critical"] for item in violations)
    score = max(0, 100 - sum(int(item["penalty"]) for item in violations))
    if critical_failure:
        score = min(score, 49)

    codes = {str(item["code"]) for item in violations}
    invariants = {
        "unknownDoesNotAuthorizeRedispatch": (
            "PCT-001_UNRESOLVED_EXECUTION_REDISPATCH" not in codes
        ),
        "trajectoryIdentityContinuous": "PCT-002_TRAJECTORY_IDENTITY_DRIFT" not in codes,
        "proofCarriedAcrossContinuityBoundaries": (
            "PCT-003_CONTINUITY_BOUNDARY_WITHOUT_PREDECESSOR_PROOF" not in codes
        ),
        "terminalOutcomeExternallyBound": (
            "PCT-004_TERMINAL_WITHOUT_EXTERNAL_PROOF" not in codes
        ),
        "committedExecutionNotRepeated": "PCT-005_REDISPATCH_AFTER_COMMIT" not in codes,
    }

    return {
        "schema": RESULT_SCHEMA,
        "benchmark": BENCHMARK_ID,
        "scenarioId": scenario_id,
        "trajectoryId": trajectory_id,
        "policy": policy_name,
        "status": "pass" if not violations else "fail",
        "score": score,
        "criticalFailure": critical_failure,
        "observed": {
            "events": len(events),
            "ambiguousOutcomes": ambiguity_count,
            "reconciliations": reconciliation_count,
            "continuityBoundaries": continuity_boundary_count,
            "handoffs": handoff_count,
            "unresolvedLogicalOperations": sorted(unresolved),
        },
        "invariants": invariants,
        "violations": violations,
        "claimBoundary": (
            "The result evaluates only the supplied ordered trace and evidence references. "
            "It does not establish external evidence truth, runtime completeness, or general agent safety."
        ),
        "authority": {
            "classification": "RESEARCH_ONLY",
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }


def evaluate_agent_trajectory_file(path: Path) -> dict[str, Any]:
    return evaluate_agent_trajectory_scenario(load_agent_trajectory_scenario(path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m contractgraph_qa.agent_trajectory",
        description="Evaluate a Proof-Carrying Agent Trajectory v0.1 scenario.",
    )
    parser.add_argument("--scenario", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_agent_trajectory_file(args.scenario.resolve())
    except (AgentTrajectoryError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.exit(10, f"agent-trajectory: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "pass" else 10


if __name__ == "__main__":
    raise SystemExit(main())
