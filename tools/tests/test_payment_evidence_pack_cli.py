from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from contractgraph_qa.cli import main

ROOT = Path(__file__).resolve().parents[2]
DEMO = (
    ROOT
    / "benchmarks"
    / "agent-payment-recovery-v0.1"
    / "customer-evidence-pack"
    / "demo-timeout-settled-fulfillment-unknown.json"
)


class PaymentEvidencePackCliTest(unittest.TestCase):
    def test_build_and_verify_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "customer-pack.zip"
            stdout = StringIO()
            with redirect_stdout(stdout):
                build_exit = main(
                    [
                        "agent-payment-evidence-pack",
                        "--input",
                        str(DEMO),
                        "--output",
                        str(pack),
                    ]
                )
            self.assertEqual(build_exit, 0)
            built = json.loads(stdout.getvalue())
            self.assertEqual(built["decision"], "RECONCILE")
            self.assertFalse(built["monetaryActionAllowed"])
            self.assertTrue(pack.exists())

            stdout = StringIO()
            with redirect_stdout(stdout):
                verify_exit = main(["verify-agent-payment-evidence-pack", str(pack)])
            self.assertEqual(verify_exit, 0)
            verified = json.loads(stdout.getvalue())
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["decision"], "RECONCILE")

    def test_missing_pack_fails_closed(self) -> None:
        stderr = StringIO()
        with redirect_stderr(stderr):
            exit_code = main(
                ["verify-agent-payment-evidence-pack", "/definitely/missing/customer-pack.zip"]
            )
        self.assertEqual(exit_code, 10)
        self.assertIn("unable to read evidence pack", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
