from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "payment-fulfillment"
CONTRACT = BASE / "x402-v2-http-public-contract.v0.1.json"


class PaymentFulfillmentCliTest(unittest.TestCase):
    def _run(self, scenario_name: str) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(
                [
                    "payment-fulfillment-evaluate",
                    "--contract",
                    str(CONTRACT),
                    "--scenario",
                    str(BASE / scenario_name),
                ]
            )
        return code, json.loads(stdout.getvalue())

    def test_cli_returns_zero_for_contained_unknown_fulfillment(self) -> None:
        code, payload = self._run("x402-committed-unknown-hold.json")
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(payload["status"], "pass")
        self.assertFalse(payload["safeToSpendAgain"])

    def test_cli_blocks_repurchase_when_delivery_is_unknown(self) -> None:
        code, payload = self._run("x402-committed-unknown-repurchase.json")
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(payload["criticalFailure"])
        self.assertIn(
            "PFC-001_COMMITTED_PAYMENT_UNKNOWN_FULFILLMENT_NEW_PAYMENT",
            {item["code"] for item in payload["violations"]},
        )


if __name__ == "__main__":
    unittest.main()
