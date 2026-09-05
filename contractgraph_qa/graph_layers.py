"""Strict idea/plan/fact graph comparison.

The three layers are deliberately kept separate.  ``idea`` describes the
desired transition, ``plan`` declares what will be checked, and ``fact`` is
limited to observed or explicitly blocked edges.  The comparator reports
drift; it never upgrades a missing fact into a security verdict.
"""

from __future__ import annotations

from typing import Any


SCHEMA = "cgqa/graph-layers/v0.1"
DIFF_SCHEMA = "cgqa/graph-layer-diff/v0.1"
DIMENSIONS = frozenset(
    {"time", "space", "state", "environment", "actor", "authority", "value"}
)
ROOT_KEYS = {"schema", "graphId", "idea", "plan", "fact"}
LAYER_KEYS = {"edges"}
EDGE_KEYS = {"id", "from", "to", "dimensions", "status", "evidence"}
EDGE_STATUSES = frozenset({"desired", "planned", "observed", "blocked", "static-gap"})
LAYER_STATUSES = {
    "idea": frozenset({"desired"}),
    "plan": frozenset({"planned"}),
    "fact": frozenset({"observed", "blocked", "static-gap"}),
}


def _fail(message: str) -> None:
    raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value.strip()


def _object(value: Any, field: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{field} must be an object")
    extras = sorted(set(value) - keys)
    if extras:
        _fail(f"{field} contains unexpected fields: {', '.join(extras)}")
    missing = sorted(keys - set(value))
    if missing:
        _fail(f"{field} missing fields: {', '.join(missing)}")
    return value


def _dimensions(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        _fail(f"{field} must be a non-empty array")
    result: list[str] = []
    for index, item in enumerate(value):
        dimension = _text(item, f"{field}[{index}]")
        if dimension not in DIMENSIONS:
            _fail(f"{field}[{index}] has unsupported dimension {dimension!r}")
        if dimension in result:
            _fail(f"{field} contains duplicate dimension {dimension!r}")
        result.append(dimension)
    return tuple(sorted(result))


def _edge(value: Any, field: str) -> dict[str, object]:
    raw = _object(value, field, EDGE_KEYS)
    status = _text(raw["status"], f"{field}.status")
    if status not in EDGE_STATUSES:
        _fail(f"{field}.status has unsupported value {status!r}")
    evidence = _text(raw["evidence"], f"{field}.evidence")
    return {
        "id": _text(raw["id"], f"{field}.id"),
        "from": _text(raw["from"], f"{field}.from"),
        "to": _text(raw["to"], f"{field}.to"),
        "dimensions": list(_dimensions(raw["dimensions"], f"{field}.dimensions")),
        "status": status,
        "evidence": evidence,
    }


def _layer(
    value: Any,
    field: str,
    *,
    allowed_statuses: frozenset[str],
) -> list[dict[str, object]]:
    raw = _object(value, field, LAYER_KEYS)
    edges = raw["edges"]
    if not isinstance(edges, list):
        _fail(f"{field}.edges must be an array")
    parsed = [_edge(item, f"{field}.edges[{index}]") for index, item in enumerate(edges)]
    invalid_statuses = sorted(
        {
            str(item["status"])
            for item in parsed
            if item["status"] not in allowed_statuses
        }
    )
    if invalid_statuses:
        _fail(
            f"{field}.edges contains statuses invalid for this layer: "
            + ", ".join(invalid_statuses)
        )
    ids = [str(item["id"]) for item in parsed]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        _fail(f"{field}.edges contains duplicate ids: {', '.join(duplicates)}")
    return parsed


def graph_layers_from_dict(value: Any) -> dict[str, object]:
    """Validate and normalize a graph-layer document."""

    raw = _object(value, "graph layers", ROOT_KEYS)
    schema = _text(raw["schema"], "graph layers.schema")
    if schema != SCHEMA:
        _fail(f"graph layers.schema must equal {SCHEMA!r}")
    return {
        "schema": schema,
        "graphId": _text(raw["graphId"], "graph layers.graphId"),
        "idea": {
            "edges": _layer(
                raw["idea"],
                "graph layers.idea",
                allowed_statuses=LAYER_STATUSES["idea"],
            )
        },
        "plan": {
            "edges": _layer(
                raw["plan"],
                "graph layers.plan",
                allowed_statuses=LAYER_STATUSES["plan"],
            )
        },
        "fact": {
            "edges": _layer(
                raw["fact"],
                "graph layers.fact",
                allowed_statuses=LAYER_STATUSES["fact"],
            )
        },
    }


def _edge_signature(edge: dict[str, object]) -> tuple[object, ...]:
    return (
        edge["from"],
        edge["to"],
        tuple(edge["dimensions"]),
    )


def compare_graph_layers(value: Any) -> dict[str, object]:
    """Compare declared idea/plan edges with observed fact edges.

    ``drift_detected`` means the declared idea is not faithfully represented
    by the plan, the plan is not fully represented by fact evidence, or the
    fact edge disagrees with planned geometry. It is a review signal only,
    not a vulnerability classification.
    """

    graph = graph_layers_from_dict(value)
    idea = {str(edge["id"]): edge for edge in graph["idea"]["edges"]}  # type: ignore[index]
    plan = {str(edge["id"]): edge for edge in graph["plan"]["edges"]}  # type: ignore[index]
    fact = {str(edge["id"]): edge for edge in graph["fact"]["edges"]}  # type: ignore[index]

    unplanned_ideas = sorted(set(idea) - set(plan))
    missing_fact = sorted(set(plan) - set(fact))
    unexpected_fact = sorted(set(fact) - set(plan))
    unevidenced_fact = sorted(
        edge_id
        for edge_id, edge in fact.items()
        if edge["status"] in {"blocked", "static-gap"}
    )
    mismatches: list[dict[str, object]] = []
    for edge_id in sorted(set(idea) & set(plan)):
        desired = idea[edge_id]
        planned = plan[edge_id]
        if _edge_signature(desired) != _edge_signature(planned):
            mismatches.append(
                {
                    "edgeId": edge_id,
                    "boundary": "idea-plan",
                    "expected": _edge_signature(desired),
                    "actual": _edge_signature(planned),
                }
            )
    for edge_id in sorted(set(plan) & set(fact)):
        planned = plan[edge_id]
        observed = fact[edge_id]
        if _edge_signature(planned) != _edge_signature(observed):
            mismatches.append(
                {
                    "edgeId": edge_id,
                    "boundary": "plan-fact",
                    "expected": _edge_signature(planned),
                    "actual": _edge_signature(observed),
                }
            )

    drift = bool(
        unplanned_ideas
        or missing_fact
        or unexpected_fact
        or unevidenced_fact
        or mismatches
    )
    return {
        "schema": DIFF_SCHEMA,
        "graphId": graph["graphId"],
        "status": "drift_detected" if drift else "aligned",
        "ideaEdgeCount": len(idea),
        "plannedEdgeCount": len(plan),
        "factEdgeCount": len(fact),
        "unplannedIdeaEdgeIds": unplanned_ideas,
        "missingFactEdgeIds": missing_fact,
        "unexpectedFactEdgeIds": unexpected_fact,
        "unevidencedFactEdgeIds": unevidenced_fact,
        "geometryMismatches": mismatches,
        "claimBoundary": "A graph-layer diff is a coverage and specification-drift signal; it is not a security verdict.",
    }


__all__ = [
    "SCHEMA",
    "DIFF_SCHEMA",
    "DIMENSIONS",
    "EDGE_KEYS",
    "EDGE_STATUSES",
    "LAYER_KEYS",
    "LAYER_STATUSES",
    "ROOT_KEYS",
    "compare_graph_layers",
    "graph_layers_from_dict",
]
