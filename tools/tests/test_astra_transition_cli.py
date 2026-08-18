import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.cli import main


class AstraTransitionCliTests(unittest.TestCase):
    def test_cli_emits_analysis(self):
        payload = {
            "transitions": [
                {
                    "id": "timeout-retry",
                    "stimulus": 1.0,
                    "state_complexity": 1.0,
                    "future_pressure": 1.0,
                    "witness_gap": 1.0,
                    "divergence": 1.0,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "astra.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                code = main(["astra-transition", "--input", str(path)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["schema_version"], "astra-transition-v0.1")
        self.assertEqual(result["verdict"], "TARGET_CANDIDATE")

    def test_cli_fails_closed_on_invalid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "astra.json"
            path.write_text('{"transitions": []}', encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                code = main(["astra-transition", "--input", str(path)])
        self.assertNotEqual(code, 0)
        self.assertIn("transitions must be a non-empty array", error.getvalue())


if __name__ == "__main__":
    unittest.main()
