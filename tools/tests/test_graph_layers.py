from __future__ import annotations

import unittest

from contractgraph_qa.graph_layers import compare_graph_layers, graph_layers_from_dict


def edge(edge_id: str, source: str, target: str, status: str) -> dict[str, object]:
    return {
        "id": edge_id,
        "from": source,
        "to": target,
        "dimensions": ["state", "authority"],
        "status": status,
        "evidence": f"evidence:{edge_id}",
    }


def document(*, fact: list[dict[str, object]], plan: list[dict[str, object]] | None = None):
    planned = plan if plan is not None else [edge("e1", "a", "b", "planned")]
    return {
        "schema": "cgqa/graph-layers/v0.1",
        "graphId": "test-graph",
        "idea": {"edges": [edge("e1", "a", "b", "desired")]},
        "plan": {"edges": planned},
        "fact": {"edges": fact},
    }


def _aligned_layers_have_no_drift() -> None:
    result = compare_graph_layers(document(fact=[edge("e1", "a", "b", "observed")]))
    assert result["status"] == "aligned"
    assert result["missingFactEdgeIds"] == []


def _missing_fact_is_drift_not_a_verdict() -> None:
    result = compare_graph_layers(document(fact=[]))
    assert result["status"] == "drift_detected"
    assert result["missingFactEdgeIds"] == ["e1"]
    assert "security verdict" in str(result["claimBoundary"])


def _blocked_and_static_gap_facts_are_not_treated_as_observed() -> None:
    result = compare_graph_layers(
        document(fact=[edge("e1", "a", "b", "static-gap")])
    )
    assert result["status"] == "drift_detected"
    assert result["unevidencedFactEdgeIds"] == ["e1"]


def _geometry_mismatch_is_reported() -> None:
    result = compare_graph_layers(document(fact=[edge("e1", "a", "c", "observed")]))
    assert result["geometryMismatches"]
    assert result["geometryMismatches"][0]["boundary"] == "plan-fact"


def _idea_plan_geometry_mismatch_is_reported_even_when_fact_matches_plan() -> None:
    result = compare_graph_layers(
        document(
            plan=[edge("e1", "x", "y", "planned")],
            fact=[edge("e1", "x", "y", "observed")],
        )
    )
    assert result["status"] == "drift_detected"
    assert result["geometryMismatches"] == [
        {
            "edgeId": "e1",
            "boundary": "idea-plan",
            "expected": ("a", "b", ("authority", "state")),
            "actual": ("x", "y", ("authority", "state")),
        }
    ]


def _unplanned_idea_and_unexpected_fact_are_visible() -> None:
    result = compare_graph_layers(
        document(
            plan=[edge("e2", "a", "b", "planned")],
            fact=[edge("e3", "x", "y", "observed")],
        )
    )
    assert result["unplannedIdeaEdgeIds"] == ["e1"]
    assert result["missingFactEdgeIds"] == ["e2"]
    assert result["unexpectedFactEdgeIds"] == ["e3"]


def _extra_keys_and_unknown_dimensions_fail_closed() -> None:
    raw = document(fact=[])
    raw["idea"]["edges"][0]["extra"] = True  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ValueError, "unexpected fields"):
        graph_layers_from_dict(raw)

    raw = document(fact=[])
    raw["idea"]["edges"][0]["dimensions"] = ["quantum"]  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ValueError, "unsupported dimension"):
        graph_layers_from_dict(raw)


def _layer_specific_statuses_fail_closed() -> None:
    raw = document(fact=[edge("e1", "a", "b", "observed")])
    raw["idea"]["edges"][0]["status"] = "observed"  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ValueError, "invalid for this layer"):
        graph_layers_from_dict(raw)


class GraphLayersTests(unittest.TestCase):
    """Expose every graph-layer case to the repository's unittest runner."""

    test_aligned_layers_have_no_drift = staticmethod(_aligned_layers_have_no_drift)
    test_missing_fact_is_drift_not_a_verdict = staticmethod(
        _missing_fact_is_drift_not_a_verdict
    )
    test_blocked_and_static_gap_facts_are_not_treated_as_observed = staticmethod(
        _blocked_and_static_gap_facts_are_not_treated_as_observed
    )
    test_geometry_mismatch_is_reported = staticmethod(_geometry_mismatch_is_reported)
    test_idea_plan_geometry_mismatch_is_reported_even_when_fact_matches_plan = (
        staticmethod(_idea_plan_geometry_mismatch_is_reported_even_when_fact_matches_plan)
    )
    test_unplanned_idea_and_unexpected_fact_are_visible = staticmethod(
        _unplanned_idea_and_unexpected_fact_are_visible
    )
    test_extra_keys_and_unknown_dimensions_fail_closed = staticmethod(
        _extra_keys_and_unknown_dimensions_fail_closed
    )
    test_layer_specific_statuses_fail_closed = staticmethod(
        _layer_specific_statuses_fail_closed
    )


if __name__ == "__main__":
    unittest.main()
