"""Deterministic lifecycle liveness analysis for value-holding state machines.

This module answers a different question from adversarial capability reachability:
for every *reachable* state that still holds locked economic value, does the
model contain a path to at least one declared safe economic terminal?

The analysis is exact over the declared finite graph. It does not infer that the
model itself is complete with respect to an external contract or application.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

MODEL_KEYS = {"states", "transitions", "initialState", "invariantId"}
STATE_KEYS = {"id", "description", "holdsValue", "safeTerminal"}
TRANSITION_KEYS = {"id", "source", "target"}


@dataclass(frozen=True, slots=True)
class LifecycleState:
    id: str
    description: str
    holds_value: bool
    safe_terminal: bool


@dataclass(frozen=True, slots=True)
class LifecycleTransition:
    id: str
    source: str
    target: str


@dataclass(frozen=True, slots=True)
class LifecycleLivenessModel:
    states: tuple[LifecycleState, ...]
    transitions: tuple[LifecycleTransition, ...]
    initial_state: str
    invariant_id: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(data: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def validate_lifecycle_liveness_model(model: LifecycleLivenessModel) -> None:
    _require(bool(model.states), "lifecycle liveness model.states must be non-empty")

    state_ids: set[str] = set()
    safe_terminals: list[str] = []
    for state in model.states:
        _text(state.id, "state.id")
        _text(state.description, "state.description")
        if state.id in state_ids:
            raise ValueError(f"duplicate state id: {state.id}")
        state_ids.add(state.id)
        if state.safe_terminal:
            _require(
                not state.holds_value,
                f"safe terminal state must not hold locked value: {state.id}",
            )
            safe_terminals.append(state.id)

    _require(bool(safe_terminals), "at least one safe terminal state is required")
    _require(model.initial_state in state_ids, f"unknown initial state: {model.initial_state}")
    _text(model.invariant_id, "invariantId")

    transition_ids: set[str] = set()
    for edge in model.transitions:
        _text(edge.id, "transition.id")
        if edge.id in transition_ids:
            raise ValueError(f"duplicate transition id: {edge.id}")
        transition_ids.add(edge.id)
        _require(edge.source in state_ids, f"unknown transition source state: {edge.source}")
        _require(edge.target in state_ids, f"unknown transition target state: {edge.target}")


def lifecycle_liveness_model_from_dict(data: dict[str, Any]) -> LifecycleLivenessModel:
    _require(isinstance(data, dict), "lifecycle liveness model must be a JSON object")
    _reject_extra_keys(data, MODEL_KEYS, "lifecycle liveness model")
    _require_keys(data, MODEL_KEYS, "lifecycle liveness model")

    states_raw = data["states"]
    _require(
        isinstance(states_raw, list) and bool(states_raw),
        "lifecycle liveness model.states must be a non-empty array",
    )
    states: list[LifecycleState] = []
    for index, item in enumerate(states_raw):
        field = f"lifecycle liveness model.states[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, STATE_KEYS, field)
        _require_keys(item, STATE_KEYS, field)
        holds_value = item["holdsValue"]
        safe_terminal = item["safeTerminal"]
        _require(isinstance(holds_value, bool), f"{field}.holdsValue must be a boolean")
        _require(isinstance(safe_terminal, bool), f"{field}.safeTerminal must be a boolean")
        states.append(
            LifecycleState(
                id=_text(item["id"], f"{field}.id"),
                description=_text(item["description"], f"{field}.description"),
                holds_value=holds_value,
                safe_terminal=safe_terminal,
            )
        )

    transitions_raw = data["transitions"]
    _require(
        isinstance(transitions_raw, list),
        "lifecycle liveness model.transitions must be an array",
    )
    transitions: list[LifecycleTransition] = []
    for index, item in enumerate(transitions_raw):
        field = f"lifecycle liveness model.transitions[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, TRANSITION_KEYS, field)
        _require_keys(item, TRANSITION_KEYS, field)
        transitions.append(
            LifecycleTransition(
                id=_text(item["id"], f"{field}.id"),
                source=_text(item["source"], f"{field}.source"),
                target=_text(item["target"], f"{field}.target"),
            )
        )

    model = LifecycleLivenessModel(
        states=tuple(states),
        transitions=tuple(transitions),
        initial_state=_text(data["initialState"], "lifecycle liveness model.initialState"),
        invariant_id=_text(data["invariantId"], "lifecycle liveness model.invariantId"),
    )
    validate_lifecycle_liveness_model(model)
    return model


def load_lifecycle_liveness_model(path: Path) -> LifecycleLivenessModel:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return lifecycle_liveness_model_from_dict(data)


def lifecycle_liveness_model_to_dict(model: LifecycleLivenessModel) -> dict[str, object]:
    return {
        "states": [
            {
                "id": state.id,
                "description": state.description,
                "holdsValue": state.holds_value,
                "safeTerminal": state.safe_terminal,
            }
            for state in model.states
        ],
        "transitions": [
            {"id": edge.id, "source": edge.source, "target": edge.target}
            for edge in model.transitions
        ],
        "initialState": model.initial_state,
        "invariantId": model.invariant_id,
    }


def lifecycle_liveness_model_sha256(model: LifecycleLivenessModel) -> str:
    canonical = json.dumps(
        lifecycle_liveness_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reachable_with_predecessors(
    model: LifecycleLivenessModel,
) -> tuple[set[str], dict[str, tuple[str, LifecycleTransition]]]:
    adjacency: dict[str, list[LifecycleTransition]] = defaultdict(list)
    for edge in model.transitions:
        adjacency[edge.source].append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: (edge.target, edge.id))

    reachable = {model.initial_state}
    predecessor: dict[str, tuple[str, LifecycleTransition]] = {}
    queue: deque[str] = deque([model.initial_state])
    while queue:
        current = queue.popleft()
        for edge in adjacency.get(current, ()):
            if edge.target in reachable:
                continue
            reachable.add(edge.target)
            predecessor[edge.target] = (current, edge)
            queue.append(edge.target)
    return reachable, predecessor


def _states_that_can_reach_safe_terminal(model: LifecycleLivenessModel) -> set[str]:
    reverse: dict[str, list[str]] = defaultdict(list)
    for edge in model.transitions:
        reverse[edge.target].append(edge.source)
    for sources in reverse.values():
        sources.sort()

    safe = sorted(state.id for state in model.states if state.safe_terminal)
    can_reach = set(safe)
    queue: deque[str] = deque(safe)
    while queue:
        current = queue.popleft()
        for source in reverse.get(current, ()):
            if source in can_reach:
                continue
            can_reach.add(source)
            queue.append(source)
    return can_reach


def _counterexample_path(
    state_id: str,
    initial_state: str,
    predecessor: Mapping[str, tuple[str, LifecycleTransition]],
) -> tuple[list[str], list[str]]:
    states = [state_id]
    transitions: list[str] = []
    current = state_id
    while current != initial_state:
        previous, edge = predecessor[current]
        transitions.append(edge.id)
        states.append(previous)
        current = previous
    states.reverse()
    transitions.reverse()
    return states, transitions


def run_lifecycle_liveness_model(model: LifecycleLivenessModel) -> dict[str, object]:
    """Evaluate CGQ-style economic liveness over the declared finite graph."""

    validate_lifecycle_liveness_model(model)
    state_by_id = {state.id: state for state in model.states}
    reachable, predecessor = _reachable_with_predecessors(model)
    can_reach_terminal = _states_that_can_reach_safe_terminal(model)

    outgoing: dict[str, list[LifecycleTransition]] = defaultdict(list)
    for edge in model.transitions:
        outgoing[edge.source].append(edge)
    for edges in outgoing.values():
        edges.sort(key=lambda edge: (edge.target, edge.id))

    value_holding_reachable = sorted(
        state_id
        for state_id in reachable
        if state_by_id[state_id].holds_value
    )

    violations: list[dict[str, object]] = []
    for state_id in value_holding_reachable:
        if state_id in can_reach_terminal:
            continue
        path_states, path_transitions = _counterexample_path(
            state_id,
            model.initial_state,
            predecessor,
        )
        outgoing_ids = [edge.id for edge in outgoing.get(state_id, ())]
        violations.append(
            {
                "state": state_id,
                "reason": (
                    "reachable_value_holding_dead_end"
                    if not outgoing_ids
                    else "reachable_value_holding_trap"
                ),
                "counterexampleStates": path_states,
                "counterexampleTransitions": path_transitions,
                "outgoingTransitions": outgoing_ids,
            }
        )

    safe_terminals = sorted(state.id for state in model.states if state.safe_terminal)
    return {
        "schemaVersion": "lifecycle-liveness-result-v0.1",
        "status": "fail" if violations else "pass",
        "invariantId": model.invariant_id,
        "modelSha256": lifecycle_liveness_model_sha256(model),
        "initialState": model.initial_state,
        "safeEconomicTerminals": safe_terminals,
        "reachableStates": sorted(reachable),
        "reachableValueHoldingStates": value_holding_reachable,
        "violations": violations,
        "scopeNote": "Exact over the declared finite graph; model completeness is a separate evidence claim.",
    }
