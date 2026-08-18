import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.cli import main


class AstraCausalLocalityCliTests(unittest.TestCase):
    def test_cli_emits_focus_analysis(self):
        payload = {
            "first_meaningful_divergence": "accounting",
            "max_hops": 1,
            "nodes": ["request", "accounting", "settlement"],
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
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "locality.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["astra-causal-locality", "--input", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["schema_version"], "astra-causal-locality-v0.1")
        self.assertEqual(result["verdict"], "FOCUS_READY")
        self.assertTrue(result["baseline_preserved"])

    def test_cli_fails_closed_on_unknown_source(self):
        payload = {
            "first_meaningful_divergence": "missing",
            "nodes": ["a", "b"],
            "edges": [
                {"from": "a", "to": "b", "transition_id": "ab", "tps": 0.5}
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "locality.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                code = main(["astra-causal-locality", "--input", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("must reference a declared node", error.getvalue())


if __name__ == "__main__":
    unittest.main()
