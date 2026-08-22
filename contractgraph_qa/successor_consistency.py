from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

MODEL_KEYS = {"schemaVersion", "modelId", "invariantId", "commits", "scope"}
MODEL_REQUIRED_KEYS = {"schemaVersion", "modelId", "invariantId", "commits"}
COMMIT_KEYS = {
    "eventId",
    "commitId",
    "conflictKey",
    "parentState",
    "parentVersion",
    "operation",
    "successorState",
    "successorVersion",
    "committed",
}
COMMIT_REQUIRED_KEYS = COMMIT_KEYS


@dataclass(frozen=True, slots=True)
class SuccessorCommitEvent:
    event_id: str
    commit_id: str
    conflict_key: str
    parent_state: str
    parent_version: int
    operation: str
    successor_state: str
    successor_version: int
    committed: bool


@dataclass(frozen=True, slots=True)
class SuccessorConsistencyModel:
    schema_version: str
    model_id: str
    invariant_id: str
    commits: tuple[SuccessorCommitEvent, ...]
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


def successor_consistency_model_from_dict(data: dict[str, Any]) -> SuccessorConsistencyModel:
    _require(isinstance(data, dict), "successor consistency model must be a JSON object")
    _reject_extra_keys(data, MODEL_KEYS, "successor consistency model")
    _require_keys(data, MODEL_REQUIRED_KEYS, "successor consistency model")

    commits_raw = data["commits"]
    _require(isinstance(commits_raw, list), "successor consistency model.commits must be an array")

    commits: list[SuccessorCommitEvent] = []
    event_ids: set[str] = set()
    static_by_commit_id: dict[str, tuple[object, ...]] = {}

    for index, item in enumerate(commits_raw):
        field = f"successor consistency model.commits[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, COMMIT_KEYS, field)
        _require_keys(item, COMMIT_REQUIRED_KEYS, field)

        event_id = _text(item["eventId"], f"{field}.eventId")
        if event_id in event_ids:
            raise ValueError(f"duplicate eventId: {event_id}")
        event_ids.add(event_id)

        committed = item["committed"]
        _require(isinstance(committed, bool), f"{field}.committed must be a boolean")

        event = SuccessorCommitEvent(
            event_id=event_id,
            commit_id=_text(item["commitId"], f"{field}.commitId"),
            conflict_key=_text(item["conflictKey"], f"{field}.conflictKey"),
            parent_state=_text(item["parentState"], f"{field}.parentState"),
            parent_version=_version(item["parentVersion"], f"{field}.parentVersion"),
            operation=_text(item["operation"], f"{field}.operation"),
            successor_state=_text(item["successorState"], f"{field}.successorState"),
            successor_version=_version(item["successorVersion"], f"{field}.successorVersion"),
            committed=committed,
        )

        static = (
            event.conflict_key,
            event.parent_state,
            event.parent_version,
            event.operation,
            event.successor_state,
            event.successor_version,
        )
        previous = static_by_commit_id.get(event.commit_id)
        if previous is not None and previous != static:
            raise ValueError(f"commitId has inconsistent static semantics: {event.commit_id}")
        static_by_commit_id[event.commit_id] = static
        commits.append(event)

    scope_raw = data.get("scope")
    scope = None if scope_raw is None else _text(scope_raw, "successor consistency model.scope")

    return SuccessorConsistencyModel(
        schema_version=_text(data["schemaVersion"], "successor consistency model.schemaVersion"),
        model_id=_text(data["modelId"], "successor consistency model.modelId"),
        invariant_id=_text(data["invariantId"], "successor consistency model.invariantId"),
        commits=tuple(commits),
        scope=scope,
    )


def load_successor_consistency_model(path: Path) -> SuccessorConsistencyModel:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return successor_consistency_model_from_dict(data)


def successor_consistency_model_to_dict(model: SuccessorConsistencyModel) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": model.schema_version,
        "modelId": model.model_id,
        "invariantId": model.invariant_id,
        "commits": [
            {
                "eventId": event.event_id,
                "commitId": event.commit_id,
                "conflictKey": event.conflict_key,
                "parentState": event.parent_state,
                "parentVersion": event.parent_version,
                "operation": event.operation,
                "successorState": event.successor_state,
                "successorVersion": event.successor_version,
                "committed": event.committed,
            }
            for event in model.commits
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def successor_consistency_model_sha256(model: SuccessorConsistencyModel) -> str:
    canonical = json.dumps(
        successor_consistency_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_successor_consistency_model(model: SuccessorConsistencyModel) -> dict[str, object]:
    """Enforce one committed child commit per conflict-domain parent state version."""

    committed_by_id: dict[str, SuccessorCommitEvent] = {}
    observation_count = 0
    for event in model.commits:
        if not event.committed:
            continue
        observation_count += 1
        current = committed_by_id.get(event.commit_id)
        if current is None or event.event_id < current.event_id:
            committed_by_id[event.commit_id] = event

    groups: dict[tuple[str, str, int], list[SuccessorCommitEvent]] = {}
    for event in committed_by_id.values():
        key = (event.conflict_key, event.parent_state, event.parent_version)
        groups.setdefault(key, []).append(event)

    violations: list[dict[str, object]] = []
    for (conflict_key, parent_state, parent_version), commits in sorted(groups.items()):
        ordered = sorted(commits, key=lambda item: item.commit_id)
        if len(ordered) <= 1:
            continue
        violations.append(
            {
                "conflictKey": conflict_key,
                "parentState": parent_state,
                "parentVersion": parent_version,
                "distinctCommittedChildCount": len(ordered),
                "commitIds": [item.commit_id for item in ordered],
                "successors": [
                    {
                        "commitId": item.commit_id,
                        "eventId": item.event_id,
                        "operation": item.operation,
                        "successorState": item.successor_state,
                        "successorVersion": item.successor_version,
                    }
                    for item in ordered
                ],
                "minimalCounterexampleEventIds": [item.event_id for item in ordered[:2]],
            }
        )

    return {
        "schemaVersion": model.schema_version,
        "modelId": model.model_id,
        "invariantId": model.invariant_id,
        "status": "fail" if violations else "pass",
        "modelSha256": successor_consistency_model_sha256(model),
        "committedObservationCount": observation_count,
        "distinctCommittedChildCount": len(committed_by_id),
        "checkedParentVersionDomains": len(groups),
        "violations": violations,
        "semantics": {
            "uniquenessKey": "(conflictKey, parentState, parentVersion)",
            "countingUnit": "distinct committed commitId",
            "duplicateObservationPolicy": "repeated observations of one commitId are deduplicated",
            "claimBoundary": "exact over declared normalized commit evidence; authorization/extraction completeness is external",
        },
    }
