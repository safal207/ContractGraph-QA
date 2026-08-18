"""ASTRA causal-locality prioritization for bounded causal QA.

The deterministic ContractGraph-QA explorer remains authoritative. This module
accepts an already-reviewed causal graph plus explicit transition pressure and
returns a bounded focus neighborhood after the first meaningful divergence.
It never removes transitions from the baseline search space.
"""

from __future__ import annotations

from collections import deque
from typing import Any


class AstraCausalLocalityError(ValueError):
    """Raised when ASTRA causal-locality input is malformed."""


def _non_empty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AstraCausalLocalityError(f"{name} must be a non-empty string")
    return value


def _unit_interval(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AstraCausalLocalityError(f"{name} must be a number in [0, 1]")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise AstraCausalLocalityError(f"{name} must be in [0, 1]")
    return number


def analyze_causal_locality(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic focus neighborhood without pruning baseline paths.

    Input shape::

        {
          "first_meaningful_divergence": "accounting",
          "max_hops": 1,
          "nodes": ["request", "accounting", "settlement"],
          "edges": [
            {"from": "request", "to": "accounting", "transition_id": "retry", "tps": 0.8},
            {"from": "accounting", "to": "settlement", "transition_id": "settle", "tps": 0.9}
          ]
        }

    `tps` is normalized to [0, 1] for this locality layer. The output ranking is
    a focus hint only; no edge is removed from the deterministic baseline.
    """
    if not isinstance(payload, dict):
        raise AstraCausalLocalityError("input must be an object")

    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise AstraCausalLocalityError("nodes must be a non-empty array")
    nodes: list[str] = []
    seen_nodes: set[str] = set()
    for index, raw in enumerate(raw_nodes):
        node = _non_empty_string(f"nodes[{index}]", raw)
        if node in seen_nodes:
            raise AstraCausalLocalityError(f"duplicate node: {node}")
        seen_nodes.add(node)
        nodes.append(node)

    source = _non_empty_string(
        "first_meaningful_divergence", payload.get("first_meaningful_divergence")
    )
    if source not in seen_nodes:
        raise AstraCausalLocalityError(
            "first_meaningful_divergence must reference a declared node"
        )

    max_hops_raw = payload.get("max_hops", 1)
    if isinstance(max_hops_raw, bool) or not isinstance(max_hops_raw, int):
        raise AstraCausalLocalityError("max_hops must be an integer >= 0")
    if max_hops_raw < 0:
        raise AstraCausalLocalityError("max_hops must be an integer >= 0")
    max_hops = max_hops_raw

    raw_edges = payload.get("edges")
    if not isinstance(raw_edges, list) or not raw_edges:
        raise AstraCausalLocalityError("edges must be a non-empty array")

    edges: list[dict[str, Any]] = []
    transition_ids: set[str] = set()
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise AstraCausalLocalityError(f"edges[{index}] must be an object")
        src = _non_empty_string(f"edges[{index}].from", raw.get("from"))
        dst = _non_empty_string(f"edges[{index}].to", raw.get("to"))
        transition_id = _non_empty_string(
            f"edges[{index}].transition_id", raw.get("transition_id")
        )
        if src not in seen_nodes or dst not in seen_nodes:
            raise AstraCausalLocalityError(
                f"edges[{index}] references an undeclared node"
            )
        if transition_id in transition_ids:
            raise AstraCausalLocalityError(f"duplicate transition id: {transition_id}")
        transition_ids.add(transition_id)
        tps = _unit_interval(f"edges[{index}].tps", raw.get("tps", 0.0))
        adjacency[src].append(dst)
        adjacency[dst].append(src)
        edges.append(
            {
                "from": src,
                "to": dst,
                "transition_id": transition_id,
                "tps": tps,
            }
        )

    # Undirected causal neighborhood for review focus: both immediate causes and
    # immediate effects remain visible around the first divergence.
    distance: dict[str, int] = {source: 0}
    queue: deque[str] = deque([source])
    while queue:
        current = queue.popleft()
        if distance[current] >= max_hops:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)

    focused_nodes = sorted(distance, key=lambda node: (distance[node], node))
    focused_set = set(focused_nodes)

    ranked: list[dict[str, Any]] = []
    outside: list[str] = []
    for edge in edges:
        touches_focus = edge["from"] in focused_set or edge["to"] in focused_set
        if touches_focus:
            endpoint_distances = [
                distance[node]
                for node in (edge["from"], edge["to"])
                if node in distance
            ]
            causal_distance = min(endpoint_distances)
            locality_weight = 1.0 / (1.0 + causal_distance)
            priority = round(edge["tps"] * locality_weight, 6)
            ranked.append(
                {
                    **edge,
                    "causal_distance": causal_distance,
                    "locality_weight": round(locality_weight, 6),
                    "focus_priority": priority,
                }
            )
        else:
            outside.append(edge["transition_id"])

    ranked.sort(
        key=lambda item: (
            -item["focus_priority"],
            item["causal_distance"],
            item["transition_id"],
        )
    )

    coverage = len(ranked) / len(edges)
    return {
        "schema_version": "astra-causal-locality-v0.1",
        "strategy": "focus_hint_only",
        "baseline_preserved": True,
        "pruning_allowed": False,
        "first_meaningful_divergence": source,
        "max_hops": max_hops,
        "focused_nodes": [
            {"node": node, "distance": distance[node]} for node in focused_nodes
        ],
        "ranked_focus_transitions": ranked,
        "outside_focus_transition_ids": sorted(outside),
        "focus_coverage": round(coverage, 6),
        "safety": {
            "outside_focus_still_in_baseline": True,
            "locality_may_prioritize_but_not_certify": True,
            "empty_focus_is_error": len(ranked) == 0,
        },
        "verdict": "FOCUS_READY" if ranked else "LOCALITY_INCONCLUSIVE",
    }
