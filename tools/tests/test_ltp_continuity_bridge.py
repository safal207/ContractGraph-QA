from __future__ import annotations

import copy
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.ltp_continuity_bridge import (  # noqa: E402
    ContinuityBridgeError,
    build_ltp_continuity_export,
    canonical_json_bytes,
    validate_external_observation,
    validate_smart_contract_intent,
)
from contractgraph_qa.ltp_continuity_bridge_cli import main as bridge_cli_main  # noqa: E402
from contractgraph_qa.cli import main as unified_cli_main  # noqa: E402


CHAIN_ID = 8453
CONTRACT = "0x" + "11" * 20
SENDER = "0x" + "22" * 20
TX_HASH = "0x" + "33" * 32
BLOCK_HASH = "0x" + "44" * 32
PARENT_HASH = "0x" + "55" * 32
ARGS_DIGEST = "sha256:" + "66" * 32
PAYLOAD_DIGEST = "sha256:" + "77" * 32
PROFILE_DIGEST = "88" * 32


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _intent(
    *,
    request_id: str = "release-escrow-42",
    attempt_id: str = "attempt-1",
    occurred_at: str = "2026-08-27T10:00:00Z",
    retry_of: str | None = None,
) -> dict[str, object]:
    return {
        "schemaVersion": "cgqa-smart-contract-intent-v0.1",
        "requestId": request_id,
        "traceId": "escrow-42-lifecycle",
        "attemptId": attempt_id,
        "occurredAt": occurred_at,
        "deadlineAt": "2026-08-27T10:05:00Z",
        "state": "PENDING",
        "chainFamily": "evm",
        "chainId": CHAIN_ID,
        "contractAddress": CONTRACT,
        "functionSelector": "0x12345678",
        "functionName": "releasePayment",
        "argsDigest": ARGS_DIGEST,
        "sender": SENDER,
        "nonce": 42,
        "payloadDigest": PAYLOAD_DIGEST,
        "retryOfAttemptId": retry_of,
        "parentRequestId": None,
    }


def _capture() -> dict[str, object]:
    receipt = {
        "transactionHash": TX_HASH,
        "blockHash": BLOCK_HASH,
        "blockNumber": "0x64",
        "status": "0x1",
        "logs": [
            {
                "address": CONTRACT,
                "logIndex": "0x0",
                "removed": False,
                "topics": ["0x" + "99" * 32],
                "data": "0x",
            }
        ],
    }
    capture = {
        "schemaVersion": "rpc-capture-v0.1",
        "chainId": CHAIN_ID,
        "transactionHash": TX_HASH,
        "receipt": receipt,
        "blockWitness": {
            "blockHash": BLOCK_HASH,
            "blockNumber": 100,
            "parentHash": PARENT_HASH,
            "blockTimestamp": 1787824860,
            "observedHeadNumber": 103,
            "observedConfirmationCount": 4,
        },
        "rpcResponseDigests": {
            "chainIdResponseSha256": "aa" * 32,
            "receiptResponseSha256": "bb" * 32,
            "blockResponseSha256": "cc" * 32,
            "headResponseSha256": "dd" * 32,
        },
    }
    return {
        "schemaVersion": "rpc-capture-result-v0.1",
        "status": "pass",
        "capture": capture,
        "captureSha256": _sha256(capture),
        "claimBoundary": "One RPC observation; no canonical finality claim.",
    }


def _receipt_trace() -> dict[str, object]:
    capture = _capture()["capture"]
    receipt = capture["receipt"]
    event_id = f"{TX_HASH}:0"
    return {
        "schemaVersion": "evm-receipt-adapter-result-v0.1",
        "status": "pass",
        "receiptStatus": "success",
        "transactionHash": TX_HASH,
        "chainId": CHAIN_ID,
        "matchedEventCount": 1,
        "unmatchedLogCount": 0,
        "removedLogCount": 0,
        "filteredAddressLogCount": 0,
        "receiptSha256": _sha256(receipt),
        "profileSha256": PROFILE_DIGEST,
        "executionTrace": {
            "schemaVersion": "execution-trace-v0.1",
            "traceId": f"evm-receipt:{TX_HASH}",
            "events": [
                {
                    "eventId": event_id,
                    "sourceRef": f"evm:{CHAIN_ID}:{TX_HASH}:log:0",
                    "economicEffect": {
                        "actionId": "release-escrow-42",
                        "effectKey": "escrow-42:payout",
                        "occurrenceId": event_id,
                        "applied": True,
                    },
                    "stateCommit": {
                        "commitId": event_id,
                        "conflictKey": "escrow:42",
                        "parentState": "DeliveryAccepted",
                        "parentVersion": 7,
                        "operation": "releasePayment",
                        "successorState": "Released",
                        "successorVersion": 8,
                        "committed": True,
                    },
                }
            ],
        },
        "claimBoundary": "Exact only for the reviewed event mapping.",
    }


def _receipt_observation(**binding_overrides: object) -> dict[str, object]:
    capture_digest = _capture()["captureSha256"]
    binding = {
        "chainId": CHAIN_ID,
        "transactionHash": TX_HASH,
        "contractAddress": CONTRACT,
        "functionSelector": "0x12345678",
        "functionName": "releasePayment",
        "argsDigest": ARGS_DIGEST,
        "sender": SENDER,
        "nonce": 42,
        "payloadDigest": PAYLOAD_DIGEST,
        "mappedEventIds": [f"{TX_HASH}:0"],
    }
    binding.update(binding_overrides)
    return {
        "schemaVersion": "cgqa-external-observation-v0.1",
        "observationId": "receipt-release-42",
        "requestId": "release-escrow-42",
        "traceId": "escrow-42-lifecycle",
        "attemptId": "attempt-1",
        "occurredAt": "2026-08-27T10:01:00Z",
        "sourceKind": "CONTRACT_RECEIPT",
        "subjectDigest": PAYLOAD_DIGEST,
        "resultDigest": f"sha256:{capture_digest}",
        "parentObservationId": None,
        "reviewStatus": "REVIEWED",
        "ltpProjection": {
            "recordType": "OUTCOME",
            "terminalStatus": "COMPLETED",
            "replayOfOutcomeId": None,
        },
        "evmBinding": binding,
        "metadata": {
            "rpcEndpointProbe": "SYNTHETIC_RPC_ENDPOINT_MARKER",
            "localPathProbe": "SYNTHETIC_LOCAL_PATH_MARKER",
            "credentialProbe": "SYNTHETIC_CREDENTIAL_MARKER",
        },
        "claimBoundary": "Reviewed binding; not independent canonical-chain proof.",
    }


def _downstream_request() -> dict[str, object]:
    return {
        "schemaVersion": "cgqa-external-observation-v0.1",
        "observationId": "indexer-request-42",
        "requestId": "release-escrow-42:indexer",
        "traceId": "escrow-42-lifecycle",
        "attemptId": "indexer-attempt-1",
        "occurredAt": "2026-08-27T10:01:01Z",
        "sourceKind": "CONTRACT_EVENT",
        "subjectDigest": "sha256:" + "aa" * 32,
        "resultDigest": "sha256:" + "bb" * 32,
        "parentObservationId": "receipt-release-42",
        "reviewStatus": "REVIEWED",
        "ltpProjection": {
            "recordType": "REQUEST",
            "state": "PENDING",
            "deadlineAt": "2026-08-27T10:02:00Z",
            "parentRequestId": "release-escrow-42",
            "retryOfAttemptId": None,
            "continuationId": None,
            "payloadDigest": "sha256:" + "aa" * 32,
        },
        "metadata": {},
        "claimBoundary": "Reviewed expectation that this event schedules indexer work.",
    }


class LtpContinuityBridgeTest(unittest.TestCase):
    def test_intent_exports_request_but_not_a_continuity_verdict(self) -> None:
        ltp_input, report = build_ltp_continuity_export(
            intents=[_intent()],
            captures=[],
            receipt_traces=[],
            observations=[],
            as_of="2026-08-27T10:03:00Z",
        )

        self.assertEqual(len(ltp_input["requests"]), 1)
        self.assertEqual(ltp_input["outcomes"], [])
        self.assertEqual(ltp_input["requests"][0]["request_id"], "release-escrow-42")
        self.assertNotIn("continuityVerdict", report)
        self.assertNotIn("overall_status", report)
        self.assertEqual(report["bridgeStatus"], "BRIDGE_READY_WITH_LIMITATIONS")

    def test_reviewed_receipt_event_binding_exports_completed_outcome(self) -> None:
        ltp_input, report = build_ltp_continuity_export(
            intents=[_intent()],
            captures=[_capture()],
            receipt_traces=[_receipt_trace()],
            observations=[_receipt_observation()],
            as_of="2026-08-27T10:03:00Z",
        )

        self.assertEqual(len(ltp_input["outcomes"]), 1)
        outcome = ltp_input["outcomes"][0]
        self.assertEqual(outcome["outcome_id"], "receipt-release-42")
        self.assertEqual(outcome["terminal_status"], "COMPLETED")
        self.assertEqual(outcome["occurred_at"], "2026-08-27T10:01:00Z")
        self.assertFalse(outcome["metadata"]["canonical_finality_established"])
        self.assertEqual(report["bridgeStatus"], "BRIDGE_READY")

    def test_receipt_without_reviewed_binding_fails_closed_to_no_outcome(self) -> None:
        ltp_input, report = build_ltp_continuity_export(
            intents=[_intent()],
            captures=[_capture()],
            receipt_traces=[_receipt_trace()],
            observations=[],
            as_of="2026-08-27T10:06:00Z",
        )

        self.assertEqual(ltp_input["outcomes"], [])
        reasons = {
            reason
            for mapping in report["mappingDecisions"]
            for reason in mapping["reasons"]
        }
        self.assertIn("MISSING_REVIEWED_RECEIPT_BINDING", reasons)

    def test_retry_attempts_keep_one_logical_request(self) -> None:
        first = _intent()
        second = _intent(
            attempt_id="attempt-2",
            occurred_at="2026-08-27T10:00:30Z",
            retry_of="attempt-1",
        )
        ltp_input, _ = build_ltp_continuity_export(
            intents=[second, first],
            captures=[],
            receipt_traces=[],
            observations=[],
            as_of="2026-08-27T10:03:00Z",
        )

        self.assertEqual(
            [row["attempt_id"] for row in ltp_input["requests"]],
            ["attempt-1", "attempt-2"],
        )
        self.assertEqual(
            {row["request_id"] for row in ltp_input["requests"]},
            {"release-escrow-42"},
        )
        self.assertEqual(ltp_input["requests"][1]["retry_of_attempt_id"], "attempt-1")

    def test_downstream_request_is_separate_and_can_remain_missing(self) -> None:
        ltp_input, _ = build_ltp_continuity_export(
            intents=[_intent()],
            captures=[_capture()],
            receipt_traces=[_receipt_trace()],
            observations=[_receipt_observation(), _downstream_request()],
            as_of="2026-08-27T10:03:00Z",
        )

        self.assertEqual(
            [row["request_id"] for row in ltp_input["requests"]],
            ["release-escrow-42", "release-escrow-42:indexer"],
        )
        self.assertEqual(len(ltp_input["outcomes"]), 1)

    def test_binding_mismatches_fail_before_outcome_fabrication(self) -> None:
        for field, value in (
            ("chainId", 1),
            ("contractAddress", "0x" + "ff" * 20),
            ("argsDigest", "sha256:" + "ee" * 32),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ContinuityBridgeError, field):
                    build_ltp_continuity_export(
                        intents=[_intent()],
                        captures=[_capture()],
                        receipt_traces=[_receipt_trace()],
                        observations=[_receipt_observation(**{field: value})],
                        as_of="2026-08-27T10:03:00Z",
                    )

    def test_api_success_cannot_complete_the_onchain_request(self) -> None:
        observation = _receipt_observation()
        observation["sourceKind"] = "API_RESPONSE"
        observation.pop("evmBinding")

        with self.assertRaisesRegex(ContinuityBridgeError, "API_RESPONSE.*on-chain"):
            build_ltp_continuity_export(
                intents=[_intent()],
                captures=[_capture()],
                receipt_traces=[_receipt_trace()],
                observations=[observation],
                as_of="2026-08-27T10:03:00Z",
            )

    def test_tx_hash_is_not_accepted_as_logical_request_id(self) -> None:
        intent = _intent(request_id=TX_HASH)
        with self.assertRaisesRegex(ContinuityBridgeError, "requestId.*transaction hash"):
            validate_smart_contract_intent(intent)

    def test_attempt_id_cannot_be_reused_by_two_logical_requests(self) -> None:
        other = _intent(request_id="other-request")
        with self.assertRaisesRegex(ContinuityBridgeError, "attemptId.*multiple"):
            build_ltp_continuity_export(
                intents=[_intent(), other],
                captures=[],
                receipt_traces=[],
                observations=[],
                as_of="2026-08-27T10:03:00Z",
            )

    def test_deterministic_order_input_independence_and_metadata_redaction(self) -> None:
        intents = [_intent()]
        observations = [_receipt_observation(), _downstream_request()]
        before_intents = copy.deepcopy(intents)
        before_observations = copy.deepcopy(observations)

        first = build_ltp_continuity_export(
            intents=intents,
            captures=[_capture()],
            receipt_traces=[_receipt_trace()],
            observations=observations,
            as_of="2026-08-27T10:03:00Z",
        )
        second = build_ltp_continuity_export(
            intents=list(reversed(intents)),
            captures=[copy.deepcopy(_capture())],
            receipt_traces=[copy.deepcopy(_receipt_trace())],
            observations=list(reversed(copy.deepcopy(observations))),
            as_of="2026-08-27T10:03:00Z",
        )

        self.assertEqual(canonical_json_bytes(first[0]), canonical_json_bytes(second[0]))
        self.assertEqual(canonical_json_bytes(first[1]), canonical_json_bytes(second[1]))
        self.assertEqual(intents, before_intents)
        self.assertEqual(observations, before_observations)
        serialized = canonical_json_bytes(first).decode("utf-8")
        self.assertNotIn("SYNTHETIC_RPC_ENDPOINT_MARKER", serialized)
        self.assertNotIn("SYNTHETIC_CREDENTIAL_MARKER", serialized)
        self.assertNotIn("SYNTHETIC_LOCAL_PATH_MARKER", serialized)

    def test_schema_validators_reject_unknown_fields(self) -> None:
        intent = _intent()
        intent["guessedAddress"] = CONTRACT
        with self.assertRaisesRegex(ContinuityBridgeError, "unexpected fields"):
            validate_smart_contract_intent(intent)

        observation = _receipt_observation()
        observation["fabricatedFinality"] = True
        with self.assertRaisesRegex(ContinuityBridgeError, "unexpected fields"):
            validate_external_observation(observation)


class LtpContinuityBridgeCliTest(unittest.TestCase):
    @staticmethod
    def _write(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_cli_writes_deterministic_outputs_and_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intent = root / "intent.json"
            capture = root / "capture.json"
            trace = root / "trace.json"
            observations = root / "observations.json"
            output = root / "continuity-input.json"
            report = root / "bridge-report.json"
            self._write(intent, _intent())
            self._write(capture, _capture())
            self._write(trace, _receipt_trace())
            self._write(observations, [_receipt_observation(), _downstream_request()])
            argv = [
                "--intent",
                str(intent),
                "--capture",
                str(capture),
                "--receipt-trace",
                str(trace),
                "--observations",
                str(observations),
                "--as-of",
                "2026-08-27T10:03:00Z",
                "--out",
                str(output),
                "--bridge-report-out",
                str(report),
            ]

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli_main(argv), 0)
            input_before = output.read_bytes()
            report_before = report.read_bytes()

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(bridge_cli_main(argv), 10)
            self.assertIn("use --force", stderr.getvalue())
            self.assertEqual(output.read_bytes(), input_before)
            self.assertEqual(report.read_bytes(), report_before)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge_cli_main([*argv, "--force"]), 0)
            self.assertEqual(output.read_bytes(), input_before)
            self.assertEqual(report.read_bytes(), report_before)
            self.assertTrue(output.read_bytes().endswith(b"\n"))

    def test_cli_refuses_input_aliases_for_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intent = root / "intent.json"
            self._write(intent, _intent())
            base = [
                "--intent",
                str(intent),
                "--as-of",
                "2026-08-27T10:03:00Z",
            ]

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(
                    bridge_cli_main([*base, "--out", str(intent), "--force"]),
                    10,
                )
            self.assertIn("distinct from every input", stderr.getvalue())

            hard_link = root / "intent-hard-link.json"
            os.link(intent, hard_link)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(
                    bridge_cli_main([*base, "--out", str(hard_link), "--force"]),
                    10,
                )

            symlink = root / "intent-symbolic-link.json"
            symlink.symlink_to(intent)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(
                    bridge_cli_main([*base, "--out", str(symlink), "--force"]),
                    10,
                )

    def test_cli_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intent = root / "intent.json"
            raw = json.dumps(_intent(), sort_keys=True)
            intent.write_text(raw[:-1] + ',"requestId":"shadow"}\n', encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = bridge_cli_main(
                    [
                        "--intent",
                        str(intent),
                        "--as-of",
                        "2026-08-27T10:03:00Z",
                        "--out",
                        str(root / "out.json"),
                    ]
                )
            self.assertEqual(code, 10)
            self.assertIn("duplicate JSON object key", stderr.getvalue())

    def test_cli_rejects_non_finite_json_numbers_as_validation_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            intent = root / "intent.json"
            raw = json.dumps(_intent(), sort_keys=True)
            intent.write_text(
                raw.replace('"nonce": 42', '"nonce": NaN') + "\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = bridge_cli_main(
                    [
                        "--intent",
                        str(intent),
                        "--as-of",
                        "2026-08-27T10:03:00Z",
                        "--out",
                        str(root / "out.json"),
                    ]
                )
            self.assertEqual(code, 10)
            self.assertIn("non-finite JSON number", stderr.getvalue())

    def test_cli_rejects_parent_directory_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = root / "child"
            child.mkdir()
            intent = root / "intent.json"
            self._write(intent, _intent())
            traversing_intent = child / ".." / "intent.json"

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = bridge_cli_main(
                    [
                        "--intent",
                        str(traversing_intent),
                        "--as-of",
                        "2026-08-27T10:03:00Z",
                        "--out",
                        str(root / "out.json"),
                    ]
                )
            self.assertEqual(code, 10)
            self.assertIn("parent-directory traversal", stderr.getvalue())

    def test_unified_help_and_command_help_are_registered(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(unified_cli_main(["--help"]), 0)
        self.assertIn("continuity-export", stdout.getvalue())

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(unified_cli_main(["continuity-export", "--help"]), 0)


if __name__ == "__main__":
    unittest.main()
