from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "unified-decision" / "examples"


class AgentPaymentDecisionCliTest(unittest.TestCase):
    def _run(self, filename: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["agent-payment-decision", "--input", str(BASE / filename)])
        return code, json.loads(stdout.getvalue())

    def test_allow_is_a_valid_decision(self) -> None:
        code, payload = self._run("allow-initial.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["decision"], "ALLOW")
        self.assertTrue(payload["monetaryActionAllowed"])

    def test_reconcile_is_a_valid_fail_closed_decision(self) -> None:
        code, payload = self._run("reconcile-ambiguous.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["decision"], "RECONCILE")
        self.assertFalse(payload["monetaryActionAllowed"])

    def test_malformed_input_returns_validation_exit(self) -> None:
        invalid = BASE / "invalid-unresolved-retry-allowed.json"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["agent-payment-decision", "--input", str(invalid)])
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertIn("unresolved retry authority", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
