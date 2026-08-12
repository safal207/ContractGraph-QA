"""Deterministic mapping from adversarial reachability paths to the shared causal graph vocabulary."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.reachability import ImpactPath

CAUSAL_EDGE_RELATIONS = ("enables", "escalates_to", "requires", "violates")


def path_used_violation_ids(path: ImpactPath) -> tuple[str, ...]:
    """Return only assumption violations actually required by the selected path."""

    return tuple(
        sorted(
            {
                violation
                for transition in path.transitions
                for violation in transition.requires_violations
            }
        )
    )


def first_invariant_violation(path: ImpactPath) -> dict[str, object] | None:
    """Locate the first selected transition that makes an invariant violation explicit."""

    for index, transition in enumerate(path.transitions, start=1):
        if transition.invariant_id is not None:
            return {
                "pathIndex": index,
                "transitionId": transition.id,
                "invariantId": transition.invariant_id,
                "sourceCapability": transition.source,
                "targetCapability": transition.target,
            }
    return None


def build_causal_graph(path: ImpactPath) -> dict[str, Any]:
    """Map one deterministic impact path into the common causal edge vocabulary.

    The mapping is intentionally derived from the already-selected reachability
    path. It does not invent extra edges or widen the search surface.
    """

    nodes: dict[str, dict[str, object]] = {}
    edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, **fields: object) -> None:
        candidate = {"id": node_id, **fields}
        previous = nodes.get(node_id)
        if previous is not None and previous != candidate:
            raise ValueError(f"causal graph node collision: {node_id}")
        nodes[node_id] = candidate

    def add_edge(source: str, relation: str, target: str) -> None:
        if relation not in CAUSAL_EDGE_RELATIONS:
            raise ValueError(f"unsupported causal relation: {relation}")
        edges.add((source, relation, target))

    add_node(
        f"capability:{path.initial_capability}",
        nodeType="capability",
        capabilityId=path.initial_capability,
        role="initial",
    )

    for index, transition in enumerate(path.transitions, start=1):
        source_node = f"capability:{transition.source}"
        target_node = f"capability:{transition.target}"
        transition_node = f"transition:{transition.id}"

        add_node(
            source_node,
            nodeType="capability",
            capabilityId=transition.source,
            role="initial" if transition.source == path.initial_capability else "intermediate",
        )
        add_node(
            target_node,
            nodeType="capability",
            capabilityId=transition.target,
            role="target" if transition.target == path.target_capability else "intermediate",
        )
        add_node(
            transition_node,
            nodeType="capability_transition",
            transitionId=transition.id,
            pathIndex=index,
            boundary=transition.boundary,
            impact=transition.impact,
        )

        add_edge(source_node, "enables", transition_node)
        add_edge(transition_node, "escalates_to", target_node)

        for violation in sorted(transition.requires_violations):
            assumption_node = f"assumption-violation:{violation}"
            add_node(
                assumption_node,
                nodeType="assumption_violation",
                assumptionId=violation,
            )
            add_edge(transition_node, "requires", assumption_node)

        if transition.invariant_id is not None:
            invariant_node = f"invariant:{transition.invariant_id}"
            add_node(
                invariant_node,
                nodeType="invariant",
                invariantId=transition.invariant_id,
            )
            add_edge(transition_node, "violates", invariant_node)

    if not path.transitions:
        initial = nodes[f"capability:{path.initial_capability}"]
        initial["role"] = "target"

    return {
        "relationVocabulary": list(CAUSAL_EDGE_RELATIONS),
        "usedAssumptionViolations": list(path_used_violation_ids(path)),
        "firstInvariantViolation": first_invariant_violation(path),
        "nodes": [nodes[node_id] for node_id in sorted(nodes)],
        "edges": [
            {"source": source, "relation": relation, "target": target}
            for source, relation, target in sorted(edges)
        ],
    }
