from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "scenarios/adversarial-adapter-fixture-before.json"
HEAD = ROOT / "scenarios/adversarial-adapter-fixture.json"


class ReachabilityDeltaCliTest(unittest.TestCase):
    def _run(self, base: Path, head: Path) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "reachability-delta",
                    "--base-model",
                    str(base),
                    "--head-model",
                    str(head),
                ]
            )
        return code, json.loads(stdout.getvalue())

    def test_cli_fails_gate_on_new_forbidden_reachability(self) -> None:
        code, payload = self._run(BASE, HEAD)
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["status"], "risk_increase_detected")
        self.assertEqual(
            payload["newlyReachableForbiddenCapabilities"],
            ["terminal-state-reachable"],
        )

    def test_cli_passes_identical_models(self) -> None:
        code, payload = self._run(HEAD, HEAD)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["status"], "no_material_delta")


if __name__ == "__main__":
    unittest.main()
