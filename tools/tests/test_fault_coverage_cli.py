from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.fault_coverage_cli import EXIT_OK, main  # noqa: E402


class FaultCoverageCliTest(unittest.TestCase):
    def test_cli_writes_json_and_markdown_for_pass_matrix(self) -> None:
        matrix = {
            "schemaVersion": "fault-coverage-matrix-v0.1",
            "status": "pass",
            "classification": "all_reviewed_mutations_detected",
            "matrix": [],
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="cgqa-fault-coverage-") as temp_name:
            root = Path(temp_name)
            json_out = root / "matrix.json"
            markdown_out = root / "matrix.md"
            with (
                patch("contractgraph_qa.fault_coverage_cli.load_json_object", side_effect=[{"g": 1}, {"e": 1}]),
                patch("contractgraph_qa.fault_coverage_cli.build_fault_coverage_matrix", return_value=matrix) as build,
                patch("contractgraph_qa.fault_coverage_cli.render_fault_coverage_markdown", return_value="# matrix\n"),
                redirect_stdout(output),
            ):
                code = main(
                    [
                        "--generation",
                        str(root / "generation.json"),
                        "--execution",
                        str(root / "execution.json"),
                        "--output",
                        str(json_out),
                        "--markdown",
                        str(markdown_out),
                    ]
                )
            self.assertEqual(code, EXIT_OK)
            build.assert_called_once_with({"g": 1}, {"e": 1})
            self.assertEqual(json.loads(output.getvalue())["status"], "pass")
            self.assertEqual(json.loads(json_out.read_text(encoding="utf-8"))["status"], "pass")
            self.assertEqual(markdown_out.read_text(encoding="utf-8"), "# matrix\n")


if __name__ == "__main__":
    unittest.main()
