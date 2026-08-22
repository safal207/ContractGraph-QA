"""Normalize one execution evidence stream into reusable ContractGraph-QA checks.

The bridge deliberately does not infer raw EVM semantics. Adapters are expected to
produce reviewed normalized events. One event may carry an economic-effect
observation, a state-commit observation, or both. The same canonical trace bytes
then feed independent economic-cardinality and successor-consistency engines.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from contractgraph_qa.economic_cardinality import (
    economic_cardinality_model_from_dict,
    run_economic_cardinality_model,
)
from contractgraph_qa.successor_consistency import (
    run_successor_consistency_model,
    successor_consistency_model_from_dict,
)

TRACE_KEYS = {"schemaVersion", "traceId", "events", "scope"}
TRACE_REQUIRED_KEYS = {"schemaVersion", "traceId", "events"}
EVENT_KEYS = {"eventId", "economicEffect", "stateCommit", "sourceRef"}
EVENT_REQUIRED_KEYS = {"eventId"}
ECONOMIC_KEYS = {"actionId", "effectKey", "occurrenceId", "applied"}
COMMIT_KEYS = {
    "commitId",
    "conflictKey",
    "parentState",
    "parentVersion",
    "operation",
    "successorState",
    "successorVersion",
    "committed",
}

ECONOMIC_INVARIANT_ID = "CGQ-SAFE-001"
SUCCESSOR_INVARIANT_ID = "CGQ-CONS-001"


@dataclass(frozen=True, slots=True)
class NormalizedTraceEvent:
    event_id: str
    economic_effect: dict[str, object] | None
    state_commit: dict[str, object] | None
    source_ref: str | None


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    schema_version: str
    trace_id: str
    events: tuple[NormalizedTraceEvent, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _version(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(data: dict[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def _economic_effect_from_dict(data: dict[str, Any], field: str) -> dict[str, object]:
    _reject_extra_keys(data, ECONOMIC_KEYS, field)
    _require_keys(data, ECONOMIC_KEYS, field)
    applied = data["applied"]
    _require(isinstance(applied, bool), f"{field}.applied must be a boolean")
    return {
        "actionId": _text(data["actionId"], f"{field}.actionId"),
        "effectKey": _text(data["effectKey"], f"{field}.effectKey"),
        "occurrenceId": _text(data["occurrenceId"], f"{field}.occurrenceId"),
        "applied": applied,
    }


def _state_commit_from_dict(data: dict[str, Any], field: str) -> dict[str, object]:
    _reject_extra_keys(data, COMMIT_KEYS, field)
    _require_keys(data, COMMIT_KEYS, field)
    committed = data["committed"]
    _require(isinstance(committed, bool), f"{field}.committed must be a boolean")
    return {
        "commitId": _text(data["commitId"], f"{field}.commitId"),
        "conflictKey": _text(data["conflictKey"], f"{field}.conflictKey"),
        "parentState": _text(data["parentState"], f"{field}.parentState"),
        "parentVersion": _version(data["parentVersion"], f"{field}.parentVersion"),
        "operation": _text(data["operation"], f"{field}.operation"),
        "successorState": _text(data["successorState"], f"{field}.successorState"),
        "successorVersion": _version(data["successorVersion"], f"{field}.successorVersion"),
        "committed": committed,
    }


def execution_trace_from_dict(data: dict[str, Any]) -> ExecutionTrace:
    _require(isinstance(data, dict), "execution trace must be a JSON object")
    _reject_extra_keys(data, TRACE_KEYS, "execution trace")
    _require_keys(data, TRACE_REQUIRED_KEYS, "execution trace")

    events_raw = data["events"]
    _require(isinstance(events_raw, list), "execution trace.events must be an array")
    event_ids: set[str] = set()
    events: list[NormalizedTraceEvent] = []

    for index, item in enumerate(events_raw):
        field = f"execution trace.events[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, EVENT_KEYS, field)
        _require_keys(item, EVENT_REQUIRED_KEYS, field)
        event_id = _text(item["eventId"], f"{field}.eventId")
        if event_id in event_ids:
            raise ValueError(f"duplicate eventId: {event_id}")
        event_ids.add(event_id)

        economic_raw = item.get("economicEffect")
        commit_raw = item.get("stateCommit")
        _require(
            economic_raw is not None or commit_raw is not None,
            f"{field} must contain economicEffect and/or stateCommit",
        )
        if economic_raw is not None:
            _require(isinstance(economic_raw, dict), f"{field}.economicEffect must be an object")
        if commit_raw is not None:
            _require(isinstance(commit_raw, dict), f"{field}.stateCommit must be an object")

        source_raw = item.get("sourceRef")
        source_ref = None if source_raw is None else _text(source_raw, f"{field}.sourceRef")
        events.append(
            NormalizedTraceEvent(
                event_id=event_id,
                economic_effect=(
                    None
                    if economic_raw is None
                    else _economic_effect_from_dict(economic_raw, f"{field}.economicEffect")
                ),
                state_commit=(
                    None
                    if commit_raw is None
                    else _state_commit_from_dict(commit_raw, f"{field}.stateCommit")
                ),
                source_ref=source_ref,
            )
        )

    scope_raw = data.get("scope")
    scope = None if scope_raw is None else _text(scope_raw, "execution trace.scope")
    return ExecutionTrace(
        schema_version=_text(data["schemaVersion"], "execution trace.schemaVersion"),
        trace_id=_text(data["traceId"], "execution trace.traceId"),
        events=tuple(events),
        scope=scope,
    )


def load_execution_trace(path: Path) -> ExecutionTrace:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return execution_trace_from_dict(data)


def execution_trace_to_dict(trace: ExecutionTrace) -> dict[str, object]:
    events: list[dict[str, object]] = []
    for event in trace.events:
        item: dict[str, object] = {"eventId": event.event_id}
        if event.economic_effect is not None:
            item["economicEffect"] = dict(event.economic_effect)
        if event.state_commit is not None:
            item["stateCommit"] = dict(event.state_commit)
        if event.source_ref is not None:
            item["sourceRef"] = event.source_ref
        events.append(item)

    document: dict[str, object] = {
        "schemaVersion": trace.schema_version,
        "traceId": trace.trace_id,
        "events": events,
    }
    if trace.scope is not None:
        document["scope"] = trace.scope
    return document


def execution_trace_sha256(trace: ExecutionTrace) -> str:
    canonical = json.dumps(
        execution_trace_to_dict(trace),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _economic_projection(trace: ExecutionTrace) -> dict[str, object] | None:
    events: list[dict[str, object]] = []
    for event in trace.events:
        if event.economic_effect is None:
            continue
        events.append({"eventId": event.event_id, **event.economic_effect})
    if not events:
        return None
    model = economic_cardinality_model_from_dict(
        {
            "schemaVersion": "economic-cardinality-v0.1",
            "modelId": f"{trace.trace_id}:economic-cardinality",
            "invariantId": ECONOMIC_INVARIANT_ID,
            "events": events,
            **({"scope": trace.scope} if trace.scope is not None else {}),
        }
    )
    return run_economic_cardinality_model(model)


def _successor_projection(trace: ExecutionTrace) -> dict[str, object] | None:
    commits: list[dict[str, object]] = []
    for event in trace.events:
        if event.state_commit is None:
            continue
        commits.append({"eventId": event.event_id, **event.state_commit})
    if not commits:
        return None
    model = successor_consistency_model_from_dict(
        {
            "schemaVersion": "successor-consistency-v0.1",
            "modelId": f"{trace.trace_id}:successor-consistency",
            "invariantId": SUCCESSOR_INVARIANT_ID,
            "commits": commits,
            **({"scope": trace.scope} if trace.scope is not None else {}),
        }
    )
    return run_successor_consistency_model(model)


def run_execution_trace(trace: ExecutionTrace) -> dict[str, object]:
    """Run every applicable deterministic verification projection over one trace."""

    economic = _economic_projection(trace)
    successor = _successor_projection(trace)
    applicable = [item for item in (economic, successor) if item is not None]

    if not applicable:
        status = "inconclusive"
    elif any(item["status"] == "fail" for item in applicable):
        status = "fail"
    else:
        status = "pass"

    return {
        "schemaVersion": "execution-trace-result-v0.1",
        "traceId": trace.trace_id,
        "traceSha256": execution_trace_sha256(trace),
        "status": status,
        "eventCount": len(trace.events),
        "economicCardinality": economic or {"status": "not_applicable"},
        "successorConsistency": successor or {"status": "not_applicable"},
        "sourceRefs": sorted(
            {event.source_ref for event in trace.events if event.source_ref is not None}
        ),
        "claimBoundary": (
            "Exact over declared normalized execution evidence. Raw EVM/provider trace "
            "capture completeness and semantic normalization remain adapter/provenance claims."
        ),
    }
