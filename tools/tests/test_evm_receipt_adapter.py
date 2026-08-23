from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.evm_receipt_adapter import adapt_receipt, profile_from_dict  # noqa: E402
from contractgraph_qa.execution_trace import execution_trace_from_dict, run_execution_trace  # noqa: E402

RECEIPT = ROOT / "scenarios" / "evm-receipt-double-settlement.json"
PROFILE = ROOT / "scenarios" / "evm-receipt-double-settlement-profile.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class EvmReceiptAdapterTest(unittest.TestCase):
    def test_raw_receipt_projects_to_existing_runtime_invariants(self) -> None:
        result = adapt_receipt(_load(RECEIPT), _load(PROFILE))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["matchedEventCount"], 2)

        trace = execution_trace_from_dict(result["executionTrace"])
        verification = run_execution_trace(trace)
        self.assertEqual(verification["status"], "fail")
        self.assertEqual(verification["economicCardinality"]["status"], "fail")
        self.assertEqual(verification["successorConsistency"]["status"], "fail")

        commits = [event.state_commit for event in trace.events]
        self.assertEqual(commits[0]["conflictKey"], "escrow:42")
        self.assertEqual(commits[0]["parentState"], "Funded")
        self.assertEqual(commits[0]["parentVersion"], 7)
        self.assertEqual(commits[0]["successorState"], "Released")
        self.assertEqual(commits[1]["successorState"], "Disputed")
        self.assertEqual(commits[1]["successorVersion"], 8)

    def test_reverted_receipt_is_inconclusive_and_emits_no_events(self) -> None:
        receipt = _load(RECEIPT)
        receipt["result"]["status"] = "0x0"
        result = adapt_receipt(receipt, _load(PROFILE))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["receiptStatus"], "reverted")
        self.assertEqual(result["executionTrace"]["events"], [])

    def test_unmatched_topic_is_inconclusive_not_pass(self) -> None:
        receipt = _load(RECEIPT)
        receipt["result"]["logs"][0]["topics"][0] = "0x" + "ff" * 32
        receipt["result"]["logs"] = [receipt["result"]["logs"][0]]
        result = adapt_receipt(receipt, _load(PROFILE))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["matchedEventCount"], 0)
        self.assertEqual(result["unmatchedLogCount"], 1)

    def test_removed_log_is_ignored(self) -> None:
        receipt = _load(RECEIPT)
        receipt["result"]["logs"][0]["removed"] = True
        receipt["result"]["logs"] = [receipt["result"]["logs"][0]]
        result = adapt_receipt(receipt, _load(PROFILE))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["removedLogCount"], 1)
        self.assertEqual(result["matchedEventCount"], 0)

    def test_profile_rejects_duplicate_topic0(self) -> None:
        profile = _load(PROFILE)
        profile["events"][1]["topic0"] = profile["events"][0]["topic0"]
        with self.assertRaisesRegex(ValueError, "duplicate topic0"):
            profile_from_dict(profile)

    def test_missing_data_word_fails_closed(self) -> None:
        receipt = _load(RECEIPT)
        receipt["result"]["logs"][0]["data"] = "0x" + "00" * 32
        receipt["result"]["logs"] = [receipt["result"]["logs"][0]]
        with self.assertRaisesRegex(ValueError, "does not contain dataWord"):
            adapt_receipt(receipt, _load(PROFILE))

    def test_contract_address_filter_does_not_cross_bind_other_contracts(self) -> None:
        receipt = _load(RECEIPT)
        receipt["result"]["logs"][0]["address"] = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        receipt["result"]["logs"] = [receipt["result"]["logs"][0]]
        result = adapt_receipt(receipt, _load(PROFILE))
        self.assertEqual(result["filteredAddressLogCount"], 1)
        self.assertEqual(result["matchedEventCount"], 0)


if __name__ == "__main__":
    unittest.main()
