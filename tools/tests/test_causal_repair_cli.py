from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios" / "milepact-causal-repair-dispute-cutoff.json"


class CausalRepairCliTest(unittest.TestCase):
    def test_cli_emits_partial_repair_for_milepact_fixture(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "contractgraph_qa.causal_repair_cli", "--model", str(SCENARIO)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["classification"], "partial_repair")
        self.assertIn("CGQ-RACE-001", result["repairedTargetInvariantIds"])
        self.assertIn("CGQ-LIVE-001", result["preExistingFailureInvariantIds"])


if __name__ == "__main__":
    unittest.main()
