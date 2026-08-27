from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.evm_receipt_cli import main  # noqa: E402
from contractgraph_qa.execution_trace import execution_trace_from_dict, run_execution_trace  # noqa: E402

RECEIPT = ROOT / "scenarios" / "evm-receipt-double-settlement.json"
PROFILE = ROOT / "scenarios" / "evm-receipt-double-settlement-profile.json"


class EvmReceiptCliTest(unittest.TestCase):
    def test_cli_writes_normalized_trace_for_downstream_verifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main(
                    [
                        "--receipt",
                        str(RECEIPT),
                        "--profile",
                        str(PROFILE),
                        "--trace-out",
                        str(trace_path),
                    ]
                )
            self.assertEqual(code, 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["status"], "pass")
            trace = execution_trace_from_dict(json.loads(trace_path.read_text(encoding="utf-8")))
            verification = run_execution_trace(trace)
            self.assertEqual(verification["economicCardinality"]["status"], "fail")
            self.assertEqual(verification["successorConsistency"]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
