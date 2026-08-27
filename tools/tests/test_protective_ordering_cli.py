from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.protective_ordering_cli import main  # noqa: E402


class ProtectiveOrderingCliTest(unittest.TestCase):
    def test_mp05_returns_validation_exit_and_counterexample(self) -> None:
        output = io.StringIO()
        model = ROOT / "scenarios" / "milepact-protective-ordering-race.json"
        with contextlib.redirect_stdout(output):
            code = main(["--model", str(model)])
        self.assertNotEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["counterexample"]["sequence"], ["autoRelease", "raiseDispute"])


if __name__ == "__main__":
    unittest.main()
