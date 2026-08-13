from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REACHABILITY_MODEL_KEYS = {
    "assumptions",
    "capabilities",
    "transitions",
    "initialCapabilities",
    "targetCapabilities",
    "violatedAssumptions",
    "maxDepth",
}
REACHABILITY_REQUIRED_KEYS = REACHABILITY_MODEL_KEYS - {"maxDepth"}
ASSUMPTION_KEYS = {"id", "description"}
CAPABILITY_KEYS = {"id", "description", "forbidden"}
CAPABILITY_REQUIRED_KEYS = CAPABILITY_KEYS - {"forbidden"}
TRANSITION_KEYS = {
    "id",
    "source",
    "target",
    "requiresViolations",
    "invariantId",
    "boundary",
    "impact",
}
TRANSITION_REQUIRED_KEYS = {"id", "source", "target"}


@dataclass(frozen=True, slots=True)
class Assumption:
    """An explicit condition the modeled system relies on."""

    id: str
    description: str


@dataclass(frozen=True, slots=True)
class AssumptionViolation:
    """Observed or hypothesized evidence that an assumption does not hold."""

    assumption_id: str
    evidence: str | None = None


@dataclass(frozen=True, slots=True)
class Capability:
    """A system or actor capability that can become reachable."""

    id: str
    description: str
    forbidden: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityTransition:
    """A directed capability edge guarded by explicit assumption violations."""

    id: str
    source: str
    target: str
    requires_violations: tuple[str, ...] = ()
    invariant_id: str | None = None
    boundary: str | None = None
    impact: str | None = None


@dataclass(frozen=True, slots=True)
class ImpactPath:
    """Shortest deterministic path from an initial capability to a target impact."""

    initial_capability: str
    target_capability: str
    transitions: tuple[CapabilityTransition, ...]
    violated_assumptions: tuple[str, ...]

    @property
    def invariant_ids(self) -> tuple[str, ...]:
        return tuple(
            edge.invariant_id
            for edge in self.transitions
            if edge.invariant_id is not None
        )

    @property
    def crossed_boundaries(self) -> tuple[str, ...]:
        return tuple(
            edge.boundary for edge in self.transitions if edge.boundary is not None
        )

    @property
    def impact(self) -> str | None:
        for edge in reversed(self.transitions):
            if edge.impact is not None:
                return edge.impact
        return None


@dataclass(frozen=True, slots=True)
class ReachabilityModel:
    """Validated, deterministic input to adversarial capability reachability."""

    assumptions: tuple[Assumption, ...]
    capabilities: tuple[Capability, ...]
    transitions: tuple[CapabilityTransition, ...]
    initial_capabilities: tuple[str, ...]
    target_capabilities: tuple[str, ...]
    violated_assumptions: tuple[str, ...]
    max_depth: int = 8


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(data: dict[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def _string_tuple(value: Any, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    if non_empty:
        _require(bool(value), f"{field} must be non-empty")
    items = tuple(
        _require_non_empty(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty(value, field)


def validate_model(
    *,
    capabilities: Sequence[Capability],
    transitions: Sequence[CapabilityTransition],
    assumptions: Sequence[Assumption] = (),
) -> None:
    """Fail closed on malformed or ambiguous reachability models."""

    capability_ids: set[str] = set()
    for capability in capabilities:
        _require_non_empty(capability.id, "capability.id")
        _require_non_empty(capability.description, "capability.description")
        if capability.id in capability_ids:
            raise ValueError(f"duplicate capability id: {capability.id}")
        capability_ids.add(capability.id)

    assumption_ids: set[str] = set()
    for assumption in assumptions:
        _require_non_empty(assumption.id, "assumption.id")
        _require_non_empty(assumption.description, "assumption.description")
        if assumption.id in assumption_ids:
            raise ValueError(f"duplicate assumption id: {assumption.id}")
        assumption_ids.add(assumption.id)

    transition_ids: set[str] = set()
    for edge in transitions:
        _require_non_empty(edge.id, "transition.id")
        _require_non_empty(edge.source, "transition.source")
        _require_non_empty(edge.target, "transition.target")
        if edge.id in transition_ids:
            raise ValueError(f"duplicate transition id: {edge.id}")
        transition_ids.add(edge.id)

        if edge.source not in capability_ids:
            raise ValueError(f"unknown source capability: {edge.source}")
        if edge.target not in capability_ids:
            raise ValueError(f"unknown target capability: {edge.target}")

        if assumptions:
            unknown = sorted(set(edge.requires_violations) - assumption_ids)
            if unknown:
                raise ValueError(
                    "transition requires unknown assumption violations: "
                    + ", ".join(unknown)
                )


def reachability_model_from_dict(data: dict[str, Any]) -> ReachabilityModel:
    """Parse and validate the strict JSON representation of a reachability model."""

    _require(isinstance(data, dict), "reachability model must be a JSON object")
    _reject_extra_keys(data, REACHABILITY_MODEL_KEYS, "reachability model")
    _require_keys(data, REACHABILITY_REQUIRED_KEYS, "reachability model")

    assumptions_raw = data["assumptions"]
    _require(
        isinstance(assumptions_raw, list),
        "reachability model.assumptions must be an array",
    )
    assumptions: list[Assumption] = []
    for index, item in enumerate(assumptions_raw):
        field = f"reachability model.assumptions[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, ASSUMPTION_KEYS, field)
        _require_keys(item, ASSUMPTION_KEYS, field)
        assumptions.append(
            Assumption(
                id=_require_non_empty(item["id"], f"{field}.id"),
                description=_require_non_empty(
                    item["description"], f"{field}.description"
                ),
            )
        )

    capabilities_raw = data["capabilities"]
    _require(
        isinstance(capabilities_raw, list) and bool(capabilities_raw),
        "reachability model.capabilities must be a non-empty array",
    )
    capabilities: list[Capability] = []
    for index, item in enumerate(capabilities_raw):
        field = f"reachability model.capabilities[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, CAPABILITY_KEYS, field)
        _require_keys(item, CAPABILITY_REQUIRED_KEYS, field)
        forbidden = item.get("forbidden", False)
        _require(isinstance(forbidden, bool), f"{field}.forbidden must be a boolean")
        capabilities.append(
            Capability(
                id=_require_non_empty(item["id"], f"{field}.id"),
                description=_require_non_empty(
                    item["description"], f"{field}.description"
                ),
                forbidden=forbidden,
            )
        )

    transitions_raw = data["transitions"]
    _require(
        isinstance(transitions_raw, list),
        "reachability model.transitions must be an array",
    )
    transitions: list[CapabilityTransition] = []
    for index, item in enumerate(transitions_raw):
        field = f"reachability model.transitions[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, TRANSITION_KEYS, field)
        _require_keys(item, TRANSITION_REQUIRED_KEYS, field)
        requires_violations = _string_tuple(
            item.get("requiresViolations", []),
            f"{field}.requiresViolations",
        )
        transitions.append(
            CapabilityTransition(
                id=_require_non_empty(item["id"], f"{field}.id"),
                source=_require_non_empty(item["source"], f"{field}.source"),
                target=_require_non_empty(item["target"], f"{field}.target"),
                requires_violations=requires_violations,
                invariant_id=_optional_text(
                    item.get("invariantId"), f"{field}.invariantId"
                ),
                boundary=_optional_text(item.get("boundary"), f"{field}.boundary"),
                impact=_optional_text(item.get("impact"), f"{field}.impact"),
            )
        )

    initial_capabilities = _string_tuple(
        data["initialCapabilities"],
        "reachability model.initialCapabilities",
        non_empty=True,
    )
    target_capabilities = _string_tuple(
        data["targetCapabilities"],
        "reachability model.targetCapabilities",
        non_empty=True,
    )
    violated_assumptions = _string_tuple(
        data["violatedAssumptions"],
        "reachability model.violatedAssumptions",
    )

    max_depth = data.get("maxDepth", 8)
    _require(
        isinstance(max_depth, int)
        and not isinstance(max_depth, bool)
        and max_depth >= 0,
        "reachability model.maxDepth must be a non-negative integer",
    )

    validate_model(
        capabilities=capabilities,
        transitions=transitions,
        assumptions=assumptions,
    )
    capability_ids = {item.id for item in capabilities}
    assumption_ids = {item.id for item in assumptions}
    unknown_starts = sorted(set(initial_capabilities) - capability_ids)
    unknown_targets = sorted(set(target_capabilities) - capability_ids)
    unknown_violations = sorted(set(violated_assumptions) - assumption_ids)
    _require(
        not unknown_starts,
        "unknown initial capabilities: " + ", ".join(unknown_starts),
    )
    _require(
        not unknown_targets,
        "unknown target capabilities: " + ", ".join(unknown_targets),
    )
    _require(
        not unknown_violations,
        "unknown violated assumptions: " + ", ".join(unknown_violations),
    )

    return ReachabilityModel(
        assumptions=tuple(assumptions),
        capabilities=tuple(capabilities),
        transitions=tuple(transitions),
        initial_capabilities=initial_capabilities,
        target_capabilities=target_capabilities,
        violated_assumptions=violated_assumptions,
        max_depth=max_depth,
    )


def load_reachability_model(path: Path) -> ReachabilityModel:
    """Load a strict reachability model from disk without external dependencies."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return reachability_model_from_dict(data)


def reachability_model_to_dict(model: ReachabilityModel) -> dict[str, object]:
    """Serialize the semantic model deterministically for hashing and evidence."""

    return {
        "assumptions": [
            {"id": item.id, "description": item.description}
            for item in model.assumptions
        ],
        "capabilities": [
            {
                "id": item.id,
                "description": item.description,
                "forbidden": item.forbidden,
            }
            for item in model.capabilities
        ],
        "transitions": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "requiresViolations": list(edge.requires_violations),
                "invariantId": edge.invariant_id,
                "boundary": edge.boundary,
                "impact": edge.impact,
            }
            for edge in model.transitions
        ],
        "initialCapabilities": list(model.initial_capabilities),
        "targetCapabilities": list(model.target_capabilities),
        "violatedAssumptions": list(model.violated_assumptions),
        "maxDepth": model.max_depth,
    }


def reachability_model_sha256(model: ReachabilityModel) -> str:
    canonical = json.dumps(
        reachability_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _path_violation_ids(
    transitions: Sequence[CapabilityTransition],
) -> tuple[str, ...]:
    """Return only assumption violations actually required by a selected path."""

    return tuple(
        sorted(
            {
                violation
                for edge in transitions
                for violation in edge.requires_violations
            }
        )
    )


def find_shortest_impact_path(
    *,
    initial_capabilities: Iterable[str],
    target_capabilities: Iterable[str],
    capabilities: Sequence[Capability],
    transitions: Sequence[CapabilityTransition],
    violated_assumptions: Iterable[str] = (),
    assumptions: Sequence[Assumption] = (),
    max_depth: int = 8,
) -> ImpactPath | None:
    """Return the shortest reachable target path using deterministic BFS.

    A transition is traversable only when every id in ``requires_violations`` is
    present in ``violated_assumptions``. Search is bounded and returns ``None``
    when no target is reachable within ``max_depth``.
    """

    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")

    validate_model(
        capabilities=capabilities,
        transitions=transitions,
        assumptions=assumptions,
    )

    capability_by_id: Mapping[str, Capability] = {
        item.id: item for item in capabilities
    }
    starts = tuple(sorted(set(initial_capabilities)))
    targets = set(target_capabilities)
    violations = frozenset(violated_assumptions)

    if not starts:
        raise ValueError("at least one initial capability is required")
    if not targets:
        raise ValueError("at least one target capability is required")

    unknown_starts = sorted(set(starts) - capability_by_id.keys())
    if unknown_starts:
        raise ValueError(
            "unknown initial capabilities: " + ", ".join(unknown_starts)
        )

    unknown_targets = sorted(targets - capability_by_id.keys())
    if unknown_targets:
        raise ValueError(
            "unknown target capabilities: " + ", ".join(unknown_targets)
        )

    if assumptions:
        known_assumptions = {item.id for item in assumptions}
        unknown_violations = sorted(violations - known_assumptions)
        if unknown_violations:
            raise ValueError(
                "unknown violated assumptions: " + ", ".join(unknown_violations)
            )

    adjacency: dict[str, list[CapabilityTransition]] = defaultdict(list)
    for edge in transitions:
        adjacency[edge.source].append(edge)
    for edges in adjacency.values():
        edges.sort(key=lambda edge: (edge.target, edge.id))

    queue: deque[tuple[str, str, tuple[CapabilityTransition, ...]]] = deque()
    visited: dict[str, int] = {}

    for start in starts:
        if start in targets:
            return ImpactPath(
                initial_capability=start,
                target_capability=start,
                transitions=(),
                violated_assumptions=(),
            )
        queue.append((start, start, ()))
        visited[start] = 0

    while queue:
        initial, current, path = queue.popleft()
        depth = len(path)
        if depth >= max_depth:
            continue

        for edge in adjacency.get(current, ()):
            if not set(edge.requires_violations).issubset(violations):
                continue

            next_path = (*path, edge)
            next_depth = len(next_path)
            if edge.target in targets:
                return ImpactPath(
                    initial_capability=initial,
                    target_capability=edge.target,
                    transitions=next_path,
                    violated_assumptions=_path_violation_ids(next_path),
                )

            previous_depth = visited.get(edge.target)
            if previous_depth is not None and previous_depth <= next_depth:
                continue
            visited[edge.target] = next_depth
            queue.append((initial, edge.target, next_path))

    return None


def impact_path_to_dict(path: ImpactPath) -> dict[str, object]:
    """Serialize the stable semantic core for evidence/report integration."""

    return {
        "initialCapability": path.initial_capability,
        "targetCapability": path.target_capability,
        "violatedAssumptions": list(path.violated_assumptions),
        "invariantIds": list(path.invariant_ids),
        "crossedBoundaries": list(path.crossed_boundaries),
        "impact": path.impact,
        "transitions": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "requiresViolations": list(edge.requires_violations),
                "invariantId": edge.invariant_id,
                "boundary": edge.boundary,
                "impact": edge.impact,
            }
            for edge in path.transitions
        ],
    }


def run_reachability_model(model: ReachabilityModel) -> dict[str, object]:
    """Run the bounded model and emit a stable evidence-oriented result."""

    path = find_shortest_impact_path(
        initial_capabilities=model.initial_capabilities,
        target_capabilities=model.target_capabilities,
        capabilities=model.capabilities,
        transitions=model.transitions,
        violated_assumptions=model.violated_assumptions,
        assumptions=model.assumptions,
        max_depth=model.max_depth,
    )
    return {
        "status": "reachable" if path is not None else "not_found_within_bound",
        "modelSha256": reachability_model_sha256(model),
        "maxDepth": model.max_depth,
        "violatedAssumptions": sorted(model.violated_assumptions),
        "targetCapabilities": sorted(model.target_capabilities),
        "path": impact_path_to_dict(path) if path is not None else None,
    }
