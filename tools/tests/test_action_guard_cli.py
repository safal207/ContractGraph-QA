from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.action_guard_cli import EXIT_PASS, EXIT_VALIDATION, main


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scenarios" / "action-guard" / "soroban-five-preflight.json"


class ActionGuardCliTest(unittest.TestCase):
    def test_writes_deterministic_result_and_refuses_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            first = StringIO()
            with redirect_stdout(first):
                code = main(["--input", str(FIXTURE), "--output", str(output)])
            self.assertEqual(code, EXIT_PASS)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "pass")
            self.assertIn("resultHash", result)

            second = StringIO()
            with redirect_stdout(second):
                code = main(["--input", str(FIXTURE), "--output", str(output)])
            self.assertEqual(code, EXIT_VALIDATION)
            self.assertEqual(second.getvalue(), "")

    def test_force_replaces_existing_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            output.write_text("old\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = main(
                    ["--input", str(FIXTURE), "--output", str(output), "--force"]
                )
            self.assertEqual(code, EXIT_PASS)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "pass")

    def test_input_cannot_be_overwritten(self) -> None:
        with redirect_stdout(StringIO()):
            code = main(["--input", str(FIXTURE), "--output", str(FIXTURE)])
        self.assertEqual(code, EXIT_VALIDATION)


if __name__ == "__main__":
    unittest.main()
