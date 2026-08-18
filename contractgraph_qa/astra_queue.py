"""ASTRA pressure-guided queue experiment for bounded causal QA.

This module compares deterministic breadth-first discovery against a second,
pressure-guided exploration order over the exact same reviewed graph. It never
changes the authoritative bounded search space, never prunes baseline paths,
and never treats earlier discovery as proof of a target defect.
"""

from __future__ import annotations

from collections import deque
from heapq import heappop, heappush
from typing import Any


class AstraQueueError(ValueError):
    """Raised when ASTRA queue comparison input is malformed."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AstraQueueError(f"{name} must be a non-empty string")
    return value


def _unit(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AstraQueueError(f"{name} must be a number in [0, 1]")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise AstraQueueError(f"{name} must be in [0, 1]")
    return number


def _parse(payload: dict[str, Any]) -> tuple[str, str, dict[str, list[dict[str, Any]]]]:
    if not isinstance(payload, dict):
        raise AstraQueueError("input must be an object")

    start = _text("start", payload.get("start"))
    target = _text("target", payload.get("target"))
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise AstraQueueError("nodes must be a non-empty array")

    nodes: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_nodes):
        node = _text(f"nodes[{index}]", raw)
        if node in seen:
            raise AstraQueueError(f"duplicate node: {node}")
        seen.add(node)
        nodes.append(node)
    if start not in seen or target not in seen:
        raise AstraQueueError("start and target must reference declared nodes")

    raw_edges = payload.get("edges")
    if not isinstance(raw_edges, list) or not raw_edges:
        raise AstraQueueError("edges must be a non-empty array")

    adjacency: dict[str, list[dict[str, Any]]] = {node: [] for node in nodes}
    transition_ids: set[str] = set()
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            raise AstraQueueError(f"edges[{index}] must be an object")
        src = _text(f"edges[{index}].from", raw.get("from"))
        dst = _text(f"edges[{index}].to", raw.get("to"))
        transition_id = _text(
            f"edges[{index}].transition_id", raw.get("transition_id")
        )
        if src not in seen or dst not in seen:
            raise AstraQueueError(f"edges[{index}] references an undeclared node")
        if transition_id in transition_ids:
            raise AstraQueueError(f"duplicate transition id: {transition_id}")
        transition_ids.add(transition_id)
        tps = _unit(f"edges[{index}].tps", raw.get("tps"))
        adjacency[src].append(
            {
                "from": src,
                "to": dst,
                "transition_id": transition_id,
                "tps": tps,
            }
        )

    for node in adjacency:
        adjacency[node].sort(key=lambda edge: edge["transition_id"])
    return start, target, adjacency


def _bfs(start: str, target: str, adjacency: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    queue: deque[tuple[str, list[str], list[str]]] = deque([(start, [start], [])])
    visited: set[str] = {start}
    expanded_nodes: list[str] = []
    examined_transitions = 0

    while queue:
        node, path_nodes, path_edges = queue.popleft()
        expanded_nodes.append(node)
        if node == target:
            return {
                "found": True,
                "path_nodes": path_nodes,
                "path_transition_ids": path_edges,
                "expanded_nodes": expanded_nodes,
                "expanded_node_count": len(expanded_nodes),
                "examined_transition_count": examined_transitions,
            }
        for edge in adjacency[node]:
            examined_transitions += 1
            nxt = edge["to"]
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append(
                (nxt, [*path_nodes, nxt], [*path_edges, edge["transition_id"]])
            )

    return {
        "found": False,
        "path_nodes": [],
        "path_transition_ids": [],
        "expanded_nodes": expanded_nodes,
        "expanded_node_count": len(expanded_nodes),
        "examined_transition_count": examined_transitions,
    }


def _pressure(start: str, target: str, adjacency: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    # Max-pressure best-first ordering. The queue key is deterministic:
    # highest cumulative mean TPS first, then shortest depth, then path identity.
    heap: list[tuple[float, int, tuple[str, ...], str, list[str], list[str], float]] = []
    heappush(heap, (-0.0, 0, (start,), start, [start], [], 0.0))
    best_seen: dict[str, float] = {start: 0.0}
    expanded_nodes: list[str] = []
    examined_transitions = 0

    while heap:
        neg_priority, depth, _, node, path_nodes, path_edges, tps_sum = heappop(heap)
        priority = -neg_priority
        if priority + 1e-12 < best_seen.get(node, -1.0):
            continue
        expanded_nodes.append(node)
        if node == target:
            return {
                "found": True,
                "path_nodes": path_nodes,
                "path_transition_ids": path_edges,
                "expanded_nodes": expanded_nodes,
                "expanded_node_count": len(expanded_nodes),
                "examined_transition_count": examined_transitions,
                "arrival_pressure": round(priority, 6),
            }

        for edge in adjacency[node]:
            examined_transitions += 1
            nxt = edge["to"]
            new_depth = depth + 1
            new_sum = tps_sum + edge["tps"]
            new_priority = new_sum / new_depth
            if new_priority <= best_seen.get(nxt, -1.0) + 1e-12:
                continue
            best_seen[nxt] = new_priority
            new_nodes = [*path_nodes, nxt]
            new_edges = [*path_edges, edge["transition_id"]]
            heappush(
                heap,
                (
                    -new_priority,
                    new_depth,
                    tuple(new_edges),
                    nxt,
                    new_nodes,
                    new_edges,
                    new_sum,
                ),
            )

    return {
        "found": False,
        "path_nodes": [],
        "path_transition_ids": [],
        "expanded_nodes": expanded_nodes,
        "expanded_node_count": len(expanded_nodes),
        "examined_transition_count": examined_transitions,
        "arrival_pressure": None,
    }


def compare_queue_ordering(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare BFS and ASTRA pressure ordering on the same reviewed graph."""
    start, target, adjacency = _parse(payload)
    bfs = _bfs(start, target, adjacency)
    astra = _pressure(start, target, adjacency)

    same_target_result = bfs["found"] == astra["found"]
    if bfs["found"] and astra["found"]:
        baseline_count = bfs["expanded_node_count"]
        astra_count = astra["expanded_node_count"]
        saved = baseline_count - astra_count
        reduction = saved / baseline_count if baseline_count else 0.0
    else:
        saved = 0
        reduction = 0.0

    if not same_target_result:
        verdict = "EXPERIMENT_DIVERGED"
    elif not bfs["found"]:
        verdict = "TARGET_NOT_FOUND_BY_BASELINE"
    elif astra["expanded_node_count"] < bfs["expanded_node_count"]:
        verdict = "ASTRA_EARLIER_SAME_TARGET"
    elif astra["expanded_node_count"] == bfs["expanded_node_count"]:
        verdict = "SAME_DISCOVERY_COST"
    else:
        verdict = "ASTRA_LATER_SAME_TARGET"

    return {
        "schema_version": "astra-queue-v0.1",
        "strategy": "parallel_queue_comparison",
        "authoritative_baseline": "deterministic_bfs",
        "baseline_preserved": True,
        "pruning_allowed": False,
        "same_reviewed_graph": True,
        "start": start,
        "target": target,
        "baseline": bfs,
        "astra_pressure_queue": astra,
        "comparison": {
            "same_target_result": same_target_result,
            "expanded_nodes_saved": saved,
            "expanded_node_reduction": round(reduction, 6),
            "same_path": bfs["path_transition_ids"] == astra["path_transition_ids"]
            if bfs["found"] and astra["found"]
            else None,
        },
        "safety": {
            "earlier_discovery_is_not_a_finding": True,
            "baseline_result_remains_authoritative": True,
            "pressure_queue_may_reorder_but_not_prune": True,
            "different_path_requires_normal_replay_and_invariant_evidence": True,
        },
        "verdict": verdict,
    }
