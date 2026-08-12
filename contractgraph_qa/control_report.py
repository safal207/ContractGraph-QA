"""Human-readable deterministic rendering for post-impact control evidence."""

from __future__ import annotations

from typing import Any


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def render_control_report(post_impact: dict[str, object]) -> str:
    """Render the verified post-impact graph without inventing semantics."""

    status = _text(post_impact.get("status"), "postImpact.status")
    target = _text(post_impact.get("boundTargetCapability"), "postImpact.boundTargetCapability")
    reachability_hash = _text(
        post_impact.get("boundReachabilityModelSha256"),
        "postImpact.boundReachabilityModelSha256",
    )
    model_hash = _text(post_impact.get("postImpactModelSha256"), "postImpact.postImpactModelSha256")
    graph = post_impact.get("controlGraph")
    _require(isinstance(graph, dict), "postImpact.controlGraph must be an object")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    _require(isinstance(nodes, list), "postImpact.controlGraph.nodes must be an array")
    _require(isinstance(edges, list), "postImpact.controlGraph.edges must be an array")

    node_by_id: dict[str, dict[str, object]] = {}
    for index, node in enumerate(nodes):
        _require(isinstance(node, dict), f"postImpact.controlGraph.nodes[{index}] must be an object")
        node_id = _text(node.get("id"), f"postImpact.controlGraph.nodes[{index}].id")
        _require(node_id not in node_by_id, "postImpact control node ids must be unique")
        node_by_id[node_id] = node

    lines = [
        "# Post-impact control report",
        "",
        f"**Status:** `{status}`  ",
        f"**Forbidden capability:** `{target}`  ",
        f"**Reachability model SHA-256:** `{reachability_hash}`  ",
        f"**Post-impact model SHA-256:** `{model_hash}`",
        "",
        "## Control path",
        "",
        "| Relation | Source | Target | Outcome | Evidence |",
        "|---|---|---|---|---|",
    ]

    for index, edge in enumerate(edges):
        _require(isinstance(edge, dict), f"postImpact.controlGraph.edges[{index}] must be an object")
        source = _text(edge.get("source"), f"postImpact.controlGraph.edges[{index}].source")
        relation = _text(edge.get("relation"), f"postImpact.controlGraph.edges[{index}].relation")
        target_id = _text(edge.get("target"), f"postImpact.controlGraph.edges[{index}].target")
        _require(source in node_by_id, f"postImpact edge references unknown source: {source}")
        _require(target_id in node_by_id, f"postImpact edge references unknown target: {target_id}")
        target_node = node_by_id[target_id]
        outcome = target_node.get("outcome", "-")
        evidence = target_node.get("evidence", "-")
        if outcome != "-":
            outcome = _text(outcome, f"postImpact node {target_id}.outcome")
        if evidence != "-":
            evidence = _text(evidence, f"postImpact node {target_id}.evidence")
        safe_evidence = str(evidence).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{relation}` | `{source}` | `{target_id}` | `{outcome}` | {safe_evidence} |"
        )

    lines.extend(
        [
            "",
            "## Verification note",
            "",
            "This report is generated only from the deterministic post-impact artifact. In a control evidence bundle, an independent verifier re-runs the reachability and post-impact models and requires this report to match the recomputed graph exactly.",
            "",
            "This is evidence about the explicitly modeled and authorized scope; it is not a claim of exhaustive production recovery or security verification.",
            "",
        ]
    )
    return "\n".join(lines)
