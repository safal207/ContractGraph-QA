import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.cli import main


class AstraQueueCliTests(unittest.TestCase):
    def test_cli_compares_bfs_and_pressure_queue(self):
        payload = {
            "start": "s0",
            "target": "bad",
            "nodes": ["s0", "low", "hot", "bad"],
            "edges": [
                {"from": "s0", "to": "low", "transition_id": "a-low", "tps": 0.1},
                {"from": "s0", "to": "hot", "transition_id": "z-hot", "tps": 1.0},
                {"from": "hot", "to": "bad", "transition_id": "hot-bad", "tps": 1.0},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["astra-queue", "--input", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["schema_version"], "astra-queue-v0.1")
        self.assertTrue(result["comparison"]["same_target_result"])
        self.assertTrue(result["baseline_preserved"])

    def test_cli_fails_closed_on_bad_graph(self):
        payload = {
            "start": "s0",
            "target": "missing",
            "nodes": ["s0", "s1"],
            "edges": [
                {"from": "s0", "to": "s1", "transition_id": "go", "tps": 0.5}
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                code = main(["astra-queue", "--input", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("start and target must reference declared nodes", error.getvalue())


if __name__ == "__main__":
    unittest.main()
