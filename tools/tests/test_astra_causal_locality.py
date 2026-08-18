import unittest

from contractgraph_qa.astra_causal_locality import (
    AstraCausalLocalityError,
    analyze_causal_locality,
)


class AstraCausalLocalityTests(unittest.TestCase):
    def test_focus_ranks_local_transitions_without_pruning_baseline(self):
        result = analyze_causal_locality(
            {
                "first_meaningful_divergence": "accounting",
                "max_hops": 1,
                "nodes": [
                    "request",
                    "accounting",
                    "settlement",
                    "unrelated-a",
                    "unrelated-b",
                ],
                "edges": [
                    {
                        "from": "request",
                        "to": "accounting",
                        "transition_id": "retry",
                        "tps": 0.8,
                    },
                    {
                        "from": "accounting",
                        "to": "settlement",
                        "transition_id": "settle",
                        "tps": 0.9,
                    },
                    {
                        "from": "unrelated-a",
                        "to": "unrelated-b",
                        "transition_id": "unrelated-hop",
                        "tps": 1.0,
                    },
                ],
            }
        )
        self.assertEqual(result["verdict"], "FOCUS_READY")
        self.assertTrue(result["baseline_preserved"])
        self.assertFalse(result["pruning_allowed"])
        self.assertIn("unrelated-hop", result["outside_focus_transition_ids"])
        ranked_ids = [item["transition_id"] for item in result["ranked_focus_transitions"]]
        self.assertEqual(ranked_ids[0], "settle")

    def test_zero_hops_keeps_source_incident_edges_visible(self):
        result = analyze_causal_locality(
            {
                "first_meaningful_divergence": "accounting",
                "max_hops": 0,
                "nodes": ["request", "accounting", "settlement"],
                "edges": [
                    {
                        "from": "request",
                        "to": "accounting",
                        "transition_id": "retry",
                        "tps": 0.7,
                    },
                    {
                        "from": "accounting",
                        "to": "settlement",
                        "transition_id": "settle",
                        "tps": 0.8,
                    },
                ],
            }
        )
        self.assertEqual(len(result["focused_nodes"]), 1)
        self.assertEqual(len(result["ranked_focus_transitions"]), 2)

    def test_unknown_divergence_fails_closed(self):
        with self.assertRaises(AstraCausalLocalityError):
            analyze_causal_locality(
                {
                    "first_meaningful_divergence": "missing",
                    "nodes": ["a", "b"],
                    "edges": [
                        {
                            "from": "a",
                            "to": "b",
                            "transition_id": "ab",
                            "tps": 0.5,
                        }
                    ],
                }
            )

    def test_undeclared_edge_node_fails_closed(self):
        with self.assertRaises(AstraCausalLocalityError):
            analyze_causal_locality(
                {
                    "first_meaningful_divergence": "a",
                    "nodes": ["a", "b"],
                    "edges": [
                        {
                            "from": "a",
                            "to": "c",
                            "transition_id": "ac",
                            "tps": 0.5,
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
