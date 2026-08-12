from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "cases"


class PaymentRecoveryCliTest(unittest.TestCase):
    def _run(self, case_name: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "payment-recovery-evaluate",
                    "--scenario",
                    str(CASES / case_name),
                ]
            )
        return code, json.loads(stdout.getvalue())

    def test_cli_returns_zero_for_pass(self) -> None:
        code, payload = self._run("pass_committed_stop.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["benchmark"], "agent-payment-recovery-v0.1")

    def test_cli_returns_validation_exit_for_invariant_failure(self) -> None:
        code, payload = self._run("fail_retry_before_reconcile.json")
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(payload["criticalFailure"])


if __name__ == "__main__":
    unittest.main()
