from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "provider-adapters"
ADAPTER = BASE / "example-public-contract.json"
NONFINAL = BASE / "example-observations-nonfinal.json"
FINAL = BASE / "example-observations-final.json"


class ProviderAdapterCliTest(unittest.TestCase):
    def test_validate_example_adapter(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(["provider-adapter-validate", "--adapter", str(ADAPTER)])

        self.assertEqual(code, EXIT_OK)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "valid")

    def test_nonfinal_reconciliation_blocks_pipeline(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(
                [
                    "provider-adapter-reconcile",
                    "--adapter",
                    str(ADAPTER),
                    "--observations",
                    str(NONFINAL),
                ]
            )

        self.assertEqual(code, EXIT_VALIDATION)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "nonfinal")
        self.assertFalse(payload["retryAllowed"])

    def test_final_reconciliation_allows_pipeline_to_continue(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(
                [
                    "provider-adapter-reconcile",
                    "--adapter",
                    str(ADAPTER),
                    "--observations",
                    str(FINAL),
                ]
            )

        self.assertEqual(code, EXIT_OK)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "final")
        self.assertEqual(payload["outcome"], "committed")

    def test_missing_adapter_is_validation_error(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                [
                    "provider-adapter-validate",
                    "--adapter",
                    str(BASE / "missing.json"),
                ]
            )

        self.assertEqual(code, EXIT_VALIDATION)
        self.assertIn("unable to read adapter", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
