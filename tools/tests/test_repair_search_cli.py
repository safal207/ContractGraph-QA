from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.repair_search_cli import main  # noqa: E402

SCENARIO = ROOT / "scenarios" / "milepact-minimal-repair-search.json"


class RepairSearchCliTest(unittest.TestCase):
    def test_cli_returns_success_and_selected_repair(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["--model", str(SCENARIO)])
        self.assertEqual(exit_code, 0)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "minimal_verified_repair")
        self.assertEqual(result["selectedRepair"]["candidateSetId"], "cutoff-plus-resolve")


if __name__ == "__main__":
    unittest.main()
