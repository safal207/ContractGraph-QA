from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.rpc_capture import capture_transaction  # noqa: E402

TX = "0x" + "aa" * 32
BLOCK = "0x" + "bb" * 32
PARENT = "0x" + "cc" * 32
RPC = "https://rpc.example.invalid/secret-key"


def _responses(*, receipt: object | None = "default", block_hash: str = BLOCK) -> dict[str, object]:
    if receipt == "default":
        receipt = {
            "transactionHash": TX,
            "blockHash": BLOCK,
            "blockNumber": "0x64",
            "status": "0x1",
            "logs": [],
        }
    return {
        "eth_chainId": "0x1",
        "eth_getTransactionReceipt": receipt,
        "eth_getBlockByHash": {
            "hash": block_hash,
            "number": "0x64",
            "parentHash": PARENT,
            "timestamp": "0x1234",
        },
        "eth_blockNumber": "0x66",
    }


def _caller(responses: dict[str, object]):
    def call(_url: str, method: str, _params: list[object]) -> object:
        return responses[method]

    return call


class RpcCaptureTest(unittest.TestCase):
    def test_capture_binds_receipt_block_and_head_without_persisting_endpoint(self) -> None:
        result = capture_transaction(RPC, TX, caller=_caller(_responses()))
        self.assertEqual(result["status"], "pass")
        capture = result["capture"]
        self.assertEqual(capture["chainId"], 1)
        self.assertEqual(capture["transactionHash"], TX)
        self.assertEqual(capture["blockWitness"]["blockHash"], BLOCK)
        self.assertEqual(capture["blockWitness"]["observedConfirmationCount"], 3)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn("rpc.example.invalid", serialized)
        self.assertNotIn("secret-key", serialized)

    def test_missing_receipt_is_inconclusive(self) -> None:
        result = capture_transaction(RPC, TX, caller=_caller(_responses(receipt=None)))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["reason"], "transaction_receipt_not_observed")

    def test_receipt_transaction_mismatch_fails_closed(self) -> None:
        responses = _responses()
        responses["eth_getTransactionReceipt"]["transactionHash"] = "0x" + "dd" * 32
        with self.assertRaisesRegex(ValueError, "does not match requested transaction"):
            capture_transaction(RPC, TX, caller=_caller(responses))

    def test_block_hash_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "block.hash does not match"):
            capture_transaction(
                RPC,
                TX,
                caller=_caller(_responses(block_hash="0x" + "dd" * 32)),
            )

    def test_head_behind_receipt_block_fails_closed(self) -> None:
        responses = _responses()
        responses["eth_blockNumber"] = "0x63"
        with self.assertRaisesRegex(ValueError, "observed head is behind"):
            capture_transaction(RPC, TX, caller=_caller(responses))


if __name__ == "__main__":
    unittest.main()
