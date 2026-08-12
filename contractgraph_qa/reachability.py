from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


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


def _require_non_empty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


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

    capability_by_id: Mapping[str, Capability] = {item.id: item for item in capabilities}
    starts = tuple(sorted(set(initial_capabilities)))
    targets = set(target_capabilities)
    violations = frozenset(violated_assumptions)

    if not starts:
        raise ValueError("at least one initial capability is required")
    if not targets:
        raise ValueError("at least one target capability is required")

    unknown_starts = sorted(set(starts) - capability_by_id.keys())
    if unknown_starts:
        raise ValueError("unknown initial capabilities: " + ", ".join(unknown_starts))

    unknown_targets = sorted(targets - capability_by_id.keys())
    if unknown_targets:
        raise ValueError("unknown target capabilities: " + ", ".join(unknown_targets))

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
                violated_assumptions=tuple(sorted(violations)),
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
                    violated_assumptions=tuple(sorted(violations)),
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
