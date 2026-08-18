import json
import unittest
from pathlib import Path

from contractgraph_qa.astra_queue import compare_queue_ordering


ROOT = Path(__file__).resolve().parents[2]


class AstraGonkaQueueBenchmarkTests(unittest.TestCase):
    def _load(self, name: str):
        path = ROOT / "benchmarks" / "astra-v0.1" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_gonka_001_finds_same_verified_target_with_lower_discovery_cost(self):
        result = compare_queue_ordering(self._load("GONKA-001-queue.json"))
        self.assertEqual(result["verdict"], "ASTRA_EARLIER_SAME_TARGET")
        self.assertTrue(result["comparison"]["same_target_result"])
        self.assertTrue(result["comparison"]["same_path"])
        self.assertEqual(result["baseline"]["expanded_node_count"], 9)
        self.assertEqual(result["astra_pressure_queue"]["expanded_node_count"], 7)
        self.assertEqual(result["comparison"]["expanded_nodes_saved"], 2)
        self.assertEqual(result["comparison"]["expanded_node_reduction"], 0.222222)

    def test_gonka_002_finds_same_verified_target_with_lower_discovery_cost(self):
        result = compare_queue_ordering(self._load("GONKA-002-queue.json"))
        self.assertEqual(result["verdict"], "ASTRA_EARLIER_SAME_TARGET")
        self.assertTrue(result["comparison"]["same_target_result"])
        self.assertTrue(result["comparison"]["same_path"])
        self.assertEqual(result["baseline"]["expanded_node_count"], 7)
        self.assertEqual(result["astra_pressure_queue"]["expanded_node_count"], 5)
        self.assertEqual(result["comparison"]["expanded_nodes_saved"], 2)
        self.assertEqual(result["comparison"]["expanded_node_reduction"], 0.285714)


if __name__ == "__main__":
    unittest.main()
