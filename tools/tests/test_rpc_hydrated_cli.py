from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.rpc_hydrated_cli import main  # noqa: E402

HAS_FORGE = shutil.which("forge") is not None
RECEIPT = ROOT / "scenarios" / "evm-receipt-double-settlement.json"
TX = "0x" + "ab" * 32


class RpcHydratedCliTest(unittest.TestCase):
    @unittest.skipUnless(HAS_FORGE, "forge is required for static lattice integration")
    def test_tx_hash_runs_full_rpc_to_hydrated_pipeline(self) -> None:
        receipt_wrapper = json.loads(RECEIPT.read_text(encoding="utf-8"))
        receipt = receipt_wrapper["result"]
        fake_capture = {
            "schemaVersion": "rpc-capture-result-v0.1",
            "status": "pass",
            "captureSha256": "fixture-sha",
            "capture": {
                "schemaVersion": "rpc-capture-v0.1",
                "chainId": 31337,
                "transactionHash": TX,
                "receipt": receipt,
                "blockWitness": {
                    "blockHash": "0x" + "bb" * 32,
                    "blockNumber": 100,
                    "parentHash": "0x" + "cc" * 32,
                    "blockTimestamp": 1,
                    "observedHeadNumber": 102,
                    "observedConfirmationCount": 3,
                },
                "rpcResponseDigests": {},
            },
            "claimBoundary": "fixture",
        }
        argv = [
            "--tx-hash", TX,
            "--rpc-url", "https://rpc.example.invalid/key",
            "--target", "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
            "--profile", str(ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"),
            "--receipt-profile", str(ROOT / "scenarios" / "evm-receipt-double-settlement-profile.json"),
            "--bindings", str(ROOT / "scenarios" / "hydration-bindings-evm-receipt-race.json"),
            "--root", str(ROOT),
        ]
        output = io.StringIO()
        with patch("contractgraph_qa.rpc_hydrated_cli.capture_transaction", return_value=fake_capture):
            with contextlib.redirect_stdout(output):
                code = main(argv)
        self.assertNotEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["rpcCapture"]["status"], "pass")
        self.assertEqual(result["receiptAdapter"]["status"], "pass")
        self.assertEqual(result["hydratedAssessment"]["runtimeVerification"]["economicCardinality"]["status"], "fail")
        self.assertEqual(result["hydratedAssessment"]["runtimeVerification"]["successorConsistency"]["status"], "fail")
        self.assertNotIn("rpc.example.invalid", output.getvalue())


if __name__ == "__main__":
    unittest.main()
