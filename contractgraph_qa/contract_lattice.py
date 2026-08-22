"""Contract Lattice Model v0.1.

A contract lattice point binds business state to explicit causal coordinates:
state, version, economic value, authority, evidence, and time witnesses.

The verifier is deterministic and fail-closed over the declared model. It checks:
- version causality across every transition;
- authority/evidence/time-witness binding at the source point;
- economic liveness for every reachable point holding locked value.

Runtime duplicate effects and competing commits remain independent verification
concerns handled by economic-cardinality and successor-consistency.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "contract-lattice-v0.1"
VERSION_INVARIANT = "CGQ-LATTICE-VER-001"
BINDING_INVARIANT = "CGQ-LATTICE-BIND-001"
TIME_INVARIANT = "CGQ-LATTICE-TIME-001"
LIVENESS_INVARIANT = "CGQ-LIVE-001"

MODEL_KEYS = {
    "schemaVersion",
    "modelId",
    "initialPoint",
    "safeTerminals",
    "points",
    "transitions",
    "scope",
}
POINT_KEYS = {
    "id",
    "state",
    "version",
    "lockedValue",
    "authorityRefs",
    "evidenceRefs",
    "timeWitnessRefs",
}
TRANSITION_KEYS = {
    "id",
    "source",
    "target",
    "action",
    "authorityRef",
    "evidenceRefs",
    "timeSensitive",
    "timeWitnessRefs",
}


@dataclass(frozen=True, slots=True)
class LatticePoint:
    id: str
    state: str
    version: int
    locked_value: int
    authority_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    time_witness_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LatticeTransition:
    id: str
    source: str
    target: str
    action: str
    authority_ref: str | None
    evidence_refs: tuple[str, ...]
    time_sensitive: bool
    time_witness_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContractLattice:
    model_id: str
    initial_point: str
    safe_terminals: tuple[str, ...]
    points: tuple[LatticePoint, ...]
    transitions: tuple[LatticeTransition, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _refs(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    refs = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(refs) == len(set(refs)), f"{field} must contain unique values")
    return refs


def _reject_extra(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _point_from_dict(data: dict[str, Any], index: int) -> LatticePoint:
    field = f"points[{index}]"
    _require(isinstance(data, dict), f"{field} must be an object")
    _reject_extra(data, POINT_KEYS, field)
    missing = sorted(POINT_KEYS - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
    version = data["version"]
    locked_value = data["lockedValue"]
    _require(isinstance(version, int) and not isinstance(version, bool) and version >= 0,
             f"{field}.version must be a non-negative integer")
    _require(isinstance(locked_value, int) and not isinstance(locked_value, bool) and locked_value >= 0,
             f"{field}.lockedValue must be a non-negative integer")
    return LatticePoint(
        id=_text(data["id"], f"{field}.id"),
        state=_text(data["state"], f"{field}.state"),
        version=version,
        locked_value=locked_value,
        authority_refs=_refs(data["authorityRefs"], f"{field}.authorityRefs"),
        evidence_refs=_refs(data["evidenceRefs"], f"{field}.evidenceRefs"),
        time_witness_refs=_refs(data["timeWitnessRefs"], f"{field}.timeWitnessRefs"),
    )


def _transition_from_dict(data: dict[str, Any], index: int) -> LatticeTransition:
    field = f"transitions[{index}]"
    _require(isinstance(data, dict), f"{field} must be an object")
    _reject_extra(data, TRANSITION_KEYS, field)
    missing = sorted(TRANSITION_KEYS - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
    authority_raw = data["authorityRef"]
    _require(authority_raw is None or isinstance(authority_raw, str),
             f"{field}.authorityRef must be string or null")
    authority_ref = None if authority_raw is None else _text(authority_raw, f"{field}.authorityRef")
    time_sensitive = data["timeSensitive"]
    _require(isinstance(time_sensitive, bool), f"{field}.timeSensitive must be a boolean")
    return LatticeTransition(
        id=_text(data["id"], f"{field}.id"),
        source=_text(data["source"], f"{field}.source"),
        target=_text(data["target"], f"{field}.target"),
        action=_text(data["action"], f"{field}.action"),
        authority_ref=authority_ref,
        evidence_refs=_refs(data["evidenceRefs"], f"{field}.evidenceRefs"),
        time_sensitive=time_sensitive,
        time_witness_refs=_refs(data["timeWitnessRefs"], f"{field}.timeWitnessRefs"),
    )


def contract_lattice_from_dict(data: dict[str, Any]) -> ContractLattice:
    _require(isinstance(data, dict), "contract lattice must be a JSON object")
    _reject_extra(data, MODEL_KEYS, "contract lattice")
    required = MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "contract lattice missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")

    points_raw = data["points"]
    transitions_raw = data["transitions"]
    _require(isinstance(points_raw, list) and points_raw, "points must be a non-empty array")
    _require(isinstance(transitions_raw, list), "transitions must be an array")

    points = tuple(_point_from_dict(item, index) for index, item in enumerate(points_raw))
    transitions = tuple(_transition_from_dict(item, index) for index, item in enumerate(transitions_raw))
    point_ids = [point.id for point in points]
    transition_ids = [transition.id for transition in transitions]
    _require(len(point_ids) == len(set(point_ids)), "point ids must be unique")
    _require(len(transition_ids) == len(set(transition_ids)), "transition ids must be unique")

    initial = _text(data["initialPoint"], "initialPoint")
    safe = _refs(data["safeTerminals"], "safeTerminals")
    _require(bool(safe), "safeTerminals must be non-empty")
    known = set(point_ids)
    _require(initial in known, f"initialPoint references unknown point: {initial}")
    unknown_safe = sorted(set(safe) - known)
    _require(not unknown_safe, "safeTerminals reference unknown points: " + ", ".join(unknown_safe))
    for transition in transitions:
        _require(transition.source in known, f"transition {transition.id} has unknown source")
        _require(transition.target in known, f"transition {transition.id} has unknown target")

    point_map = {point.id: point for point in points}
    for terminal in safe:
        _require(point_map[terminal].locked_value == 0,
                 f"safe terminal {terminal} cannot retain lockedValue")

    scope_raw = data.get("scope")
    scope = None if scope_raw is None else _text(scope_raw, "scope")
    return ContractLattice(
        model_id=_text(data["modelId"], "modelId"),
        initial_point=initial,
        safe_terminals=safe,
        points=points,
        transitions=transitions,
        scope=scope,
    )


def load_contract_lattice(path: Path) -> ContractLattice:
    with path.open("r", encoding="utf-8") as handle:
        return contract_lattice_from_dict(json.load(handle))


def contract_lattice_to_dict(model: ContractLattice) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "modelId": model.model_id,
        "initialPoint": model.initial_point,
        "safeTerminals": list(model.safe_terminals),
        "points": [
            {
                "id": point.id,
                "state": point.state,
                "version": point.version,
                "lockedValue": point.locked_value,
                "authorityRefs": list(point.authority_refs),
                "evidenceRefs": list(point.evidence_refs),
                "timeWitnessRefs": list(point.time_witness_refs),
            }
            for point in model.points
        ],
        "transitions": [
            {
                "id": transition.id,
                "source": transition.source,
                "target": transition.target,
                "action": transition.action,
                "authorityRef": transition.authority_ref,
                "evidenceRefs": list(transition.evidence_refs),
                "timeSensitive": transition.time_sensitive,
                "timeWitnessRefs": list(transition.time_witness_refs),
            }
            for transition in model.transitions
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def contract_lattice_sha256(model: ContractLattice) -> str:
    canonical = json.dumps(
        contract_lattice_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reachable_and_parents(model: ContractLattice) -> tuple[set[str], dict[str, str | None]]:
    adjacency: dict[str, list[str]] = {point.id: [] for point in model.points}
    for transition in model.transitions:
        adjacency[transition.source].append(transition.target)
    for targets in adjacency.values():
        targets.sort()

    reachable = {model.initial_point}
    parent: dict[str, str | None] = {model.initial_point: None}
    queue: deque[str] = deque([model.initial_point])
    while queue:
        current = queue.popleft()
        for target in adjacency[current]:
            if target not in reachable:
                reachable.add(target)
                parent[target] = current
                queue.append(target)
    return reachable, parent


def _path_to(point_id: str, parent: dict[str, str | None]) -> list[str]:
    path: list[str] = []
    current: str | None = point_id
    while current is not None:
        path.append(current)
        current = parent[current]
    path.reverse()
    return path


def _can_reach_safe(model: ContractLattice) -> set[str]:
    reverse: dict[str, list[str]] = {point.id: [] for point in model.points}
    for transition in model.transitions:
        reverse[transition.target].append(transition.source)
    can_reach = set(model.safe_terminals)
    queue: deque[str] = deque(sorted(model.safe_terminals))
    while queue:
        current = queue.popleft()
        for source in sorted(reverse[current]):
            if source not in can_reach:
                can_reach.add(source)
                queue.append(source)
    return can_reach


def run_contract_lattice(model: ContractLattice) -> dict[str, object]:
    points = {point.id: point for point in model.points}
    violations: list[dict[str, object]] = []

    for transition in sorted(model.transitions, key=lambda item: item.id):
        source = points[transition.source]
        target = points[transition.target]
        if target.version != source.version + 1:
            violations.append({
                "invariantId": VERSION_INVARIANT,
                "transitionId": transition.id,
                "kind": "non_unit_version_step",
                "sourceVersion": source.version,
                "targetVersion": target.version,
            })

        if transition.authority_ref is not None and transition.authority_ref not in source.authority_refs:
            violations.append({
                "invariantId": BINDING_INVARIANT,
                "transitionId": transition.id,
                "kind": "authority_not_bound_at_source",
                "authorityRef": transition.authority_ref,
            })

        missing_evidence = sorted(set(transition.evidence_refs) - set(source.evidence_refs))
        if missing_evidence:
            violations.append({
                "invariantId": BINDING_INVARIANT,
                "transitionId": transition.id,
                "kind": "evidence_not_bound_at_source",
                "missingRefs": missing_evidence,
            })

        missing_time = sorted(set(transition.time_witness_refs) - set(source.time_witness_refs))
        if missing_time:
            violations.append({
                "invariantId": TIME_INVARIANT,
                "transitionId": transition.id,
                "kind": "time_witness_not_bound_at_source",
                "missingRefs": missing_time,
            })
        if transition.time_sensitive and not transition.time_witness_refs:
            violations.append({
                "invariantId": TIME_INVARIANT,
                "transitionId": transition.id,
                "kind": "time_sensitive_transition_without_witness",
            })

    reachable, parent = _reachable_and_parents(model)
    can_reach_safe = _can_reach_safe(model)
    for point_id in sorted(reachable):
        point = points[point_id]
        if point.locked_value > 0 and point_id not in can_reach_safe:
            violations.append({
                "invariantId": LIVENESS_INVARIANT,
                "pointId": point_id,
                "state": point.state,
                "version": point.version,
                "lockedValue": point.locked_value,
                "kind": "reachable_locked_value_without_safe_exit",
                "counterexamplePath": _path_to(point_id, parent),
            })

    return {
        "schemaVersion": "contract-lattice-result-v0.1",
        "modelId": model.model_id,
        "modelSha256": contract_lattice_sha256(model),
        "status": "fail" if violations else "pass",
        "dimensions": ["state", "version", "value", "authority", "evidence", "timeWitness"],
        "reachablePoints": sorted(reachable),
        "safeTerminals": list(model.safe_terminals),
        "violations": violations,
        "claimBoundary": (
            "Exact over the declared lattice and bound references. Runtime capture completeness, "
            "raw-event normalization, and undeclared contract behavior remain separate evidence claims."
        ),
    }
