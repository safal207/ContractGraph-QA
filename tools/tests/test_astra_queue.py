import unittest

from contractgraph_qa.astra_queue import AstraQueueError, compare_queue_ordering


class AstraQueueTests(unittest.TestCase):
    def test_pressure_queue_finds_same_target_earlier(self):
        result = compare_queue_ordering(
            {
                "start": "s0",
                "target": "bad",
                "nodes": ["s0", "low-a", "low-b", "hot", "bad"],
                "edges": [
                    {"from": "s0", "to": "low-a", "transition_id": "a-low", "tps": 0.1},
                    {"from": "s0", "to": "low-b", "transition_id": "b-low", "tps": 0.2},
                    {"from": "s0", "to": "hot", "transition_id": "z-hot", "tps": 0.95},
                    {"from": "hot", "to": "bad", "transition_id": "hot-bad", "tps": 1.0},
                ],
            }
        )
        self.assertEqual(result["verdict"], "ASTRA_EARLIER_SAME_TARGET")
        self.assertTrue(result["comparison"]["same_target_result"])
        self.assertGreater(result["comparison"]["expanded_nodes_saved"], 0)
        self.assertTrue(result["baseline_preserved"])
        self.assertFalse(result["pruning_allowed"])

    def test_pressure_queue_can_find_different_path_without_changing_target_result(self):
        result = compare_queue_ordering(
            {
                "start": "s0",
                "target": "bad",
                "nodes": ["s0", "short", "hot", "mid", "bad"],
                "edges": [
                    {"from": "s0", "to": "short", "transition_id": "a-short", "tps": 0.1},
                    {"from": "short", "to": "bad", "transition_id": "short-bad", "tps": 0.1},
                    {"from": "s0", "to": "hot", "transition_id": "z-hot", "tps": 1.0},
                    {"from": "hot", "to": "mid", "transition_id": "hot-mid", "tps": 1.0},
                    {"from": "mid", "to": "bad", "transition_id": "mid-bad", "tps": 1.0},
                ],
            }
        )
        self.assertTrue(result["comparison"]["same_target_result"])
        self.assertFalse(result["comparison"]["same_path"])
        self.assertTrue(result["safety"]["different_path_requires_normal_replay_and_invariant_evidence"])

    def test_missing_target_fails_closed(self):
        with self.assertRaises(AstraQueueError):
            compare_queue_ordering(
                {
                    "start": "s0",
                    "target": "missing",
                    "nodes": ["s0", "s1"],
                    "edges": [
                        {"from": "s0", "to": "s1", "transition_id": "go", "tps": 0.5}
                    ],
                }
            )

    def test_duplicate_transition_id_fails_closed(self):
        with self.assertRaises(AstraQueueError):
            compare_queue_ordering(
                {
                    "start": "s0",
                    "target": "s2",
                    "nodes": ["s0", "s1", "s2"],
                    "edges": [
                        {"from": "s0", "to": "s1", "transition_id": "dup", "tps": 0.5},
                        {"from": "s1", "to": "s2", "transition_id": "dup", "tps": 0.8},
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
