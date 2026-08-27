"""Fail-closed ContractGraph-QA -> LTP continuity envelope adapter.

This module is intentionally not a continuity verifier.  It validates reviewed
smart-contract evidence, projects it into the existing LTP v0.1 request/outcome
contract, and records the mapping/provenance boundary.  Only LTP may compute a
continuity verdict from the generated document.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

from contractgraph_qa.execution_trace import (
    execution_trace_from_dict,
    execution_trace_sha256,
)

INTENT_SCHEMA_VERSION = "cgqa-smart-contract-intent-v0.1"
OBSERVATION_SCHEMA_VERSION = "cgqa-external-observation-v0.1"
BRIDGE_REPORT_SCHEMA_VERSION = "cgqa-ltp-continuity-bridge-report-v0.1"
BRIDGE_PROFILE = "cgqa-smart-contract-continuity-bridge-v0.1"

REQUEST_PROFILE = "org.ltp.request-envelope.v0.1"
OUTCOME_PROFILE = "org.ltp.outcome-envelope.v0.1"

LTP_SOURCE_COMMIT = "08734d248c24dfb2ee8e4f4a3f689887ead0ea24"
LTP_SOURCE_TREE = "5eb684d990701fa959f0b2a87125ebd765df70cd"
LTP_SCHEMA_CONTRACT = {
    "repository": "safal207/L-THREAD-Liminal-Thread-Secure-Protocol-LTP-",
    "commitSha": LTP_SOURCE_COMMIT,
    "treeSha": LTP_SOURCE_TREE,
    "validationCommand": "pnpm -w ltp:continuity -- <input.json> --out <report.json>",
    "schemas": [
        {
            "path": "docs/contracts/ltp-request-envelope.v0.1.schema.json",
            "sha256": "721d2482c88abf91c7e511614b4c81d39a8b0408ccc2fd41d014d356b3f9a86e",
        },
        {
            "path": "docs/contracts/ltp-outcome-envelope.v0.1.schema.json",
            "sha256": "9a6b2cdb88e8ad82dd71c8a82cb0cea2f68fdc07f3b68ed2b129fd4534f01be7",
        },
        {
            "path": "docs/contracts/ltp-request-outcome-continuity-input.v0.1.schema.json",
            "sha256": "e12b9ed0d5127b45d53e4168fdd9a911c577dad24abdaa0db918b091886045aa",
        },
        {
            "path": "docs/contracts/ltp-request-outcome-continuity-report.v0.1.schema.json",
            "sha256": "f826852ed6170651f66b1e274c8cd8b2632bc84f5ad58d0720fa989a9bb4d4ac",
        },
    ],
}

_INTENT_KEYS = {
    "schemaVersion",
    "requestId",
    "traceId",
    "attemptId",
    "occurredAt",
    "deadlineAt",
    "state",
    "chainFamily",
    "chainId",
    "contractAddress",
    "functionSelector",
    "functionName",
    "argsDigest",
    "sender",
    "nonce",
    "payloadDigest",
    "retryOfAttemptId",
    "parentRequestId",
    "continuationId",
}
_INTENT_REQUIRED = _INTENT_KEYS - {"continuationId"}

_OBSERVATION_KEYS = {
    "schemaVersion",
    "observationId",
    "requestId",
    "traceId",
    "attemptId",
    "occurredAt",
    "sourceKind",
    "subjectDigest",
    "resultDigest",
    "parentObservationId",
    "reviewStatus",
    "ltpProjection",
    "evmBinding",
    "metadata",
    "claimBoundary",
}
_OBSERVATION_REQUIRED = _OBSERVATION_KEYS - {"ltpProjection", "evmBinding"}

_REQUEST_PROJECTION_KEYS = {
    "recordType",
    "state",
    "deadlineAt",
    "parentRequestId",
    "retryOfAttemptId",
    "continuationId",
    "payloadDigest",
}
_OUTCOME_PROJECTION_KEYS = {
    "recordType",
    "terminalStatus",
    "replayOfOutcomeId",
}
_EVM_BINDING_KEYS = {
    "chainId",
    "transactionHash",
    "contractAddress",
    "functionSelector",
    "functionName",
    "argsDigest",
    "sender",
    "nonce",
    "payloadDigest",
    "mappedEventIds",
}

_REQUEST_STATES = {"CREATED", "ACCEPTED", "PENDING", "DEFERRED"}
_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "REJECTED", "CANCELLED", "TIMED_OUT"}
_SOURCE_KINDS = {
    "CONTRACT_RECEIPT",
    "CONTRACT_EVENT",
    "INDEXER_RECORD",
    "BACKEND_STATE",
    "API_RESPONSE",
}

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,255}$")
_TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAW_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_SELECTOR = re.compile(r"^0x[0-9a-fA-F]{8}$")
_FUNCTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$"
)


class ContinuityBridgeError(ValueError):
    """Raised when evidence cannot be safely projected to the LTP contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContinuityBridgeError(message)


def _object(value: Any, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{field} must be an object")
    return dict(value)


def _reject_extra_keys(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(value) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(value: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(value))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{field} must be a non-empty string")
    _require(value == value.strip(), f"{field} must not contain leading or trailing whitespace")
    return value


def _identifier(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_IDENTIFIER.fullmatch(text)), f"{field} contains unsupported identifier characters")
    return text


def _optional_identifier(value: Any, field: str) -> str | None:
    return None if value is None else _identifier(value, field)


def _digest(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_DIGEST.fullmatch(text)), f"{field} must be sha256:<64 lowercase hex>")
    return text


def _raw_digest(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_RAW_DIGEST.fullmatch(text)), f"{field} must be 64 lowercase hex characters")
    return text


def _address(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_ADDRESS.fullmatch(text)), f"{field} must be a 20-byte EVM address")
    return text.lower()


def _selector(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_SELECTOR.fullmatch(text)), f"{field} must be a 4-byte function selector")
    return text.lower()


def _tx_hash(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_TX_HASH.fullmatch(text)), f"{field} must be a 32-byte transaction hash")
    return text.lower()


def _integer(value: Any, field: str, *, positive: bool = False) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{field} must be an integer")
    minimum = 1 if positive else 0
    _require(value >= minimum, f"{field} must be >= {minimum}")
    return value


def _quantity(value: Any, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return _integer(value, field)
    text = _text(value, field).lower()
    _require(text.startswith("0x"), f"{field} must be an integer or hex quantity")
    try:
        parsed = int(text, 16)
    except ValueError as exc:  # pragma: no cover - guarded by int itself
        raise ContinuityBridgeError(f"{field} must be a valid hex quantity") from exc
    _require(parsed >= 0, f"{field} must be non-negative")
    return parsed


def _timestamp_value(value: Any, field: str) -> tuple[str, datetime]:
    text = _text(value, field)
    _require(bool(_TIMESTAMP.fullmatch(text)), f"{field} must have an explicit UTC offset")
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContinuityBridgeError(f"{field} must be a valid timestamp") from exc
    _require(parsed.tzinfo is not None, f"{field} must have an explicit UTC offset")
    return text, parsed.astimezone(UTC)


def _canonical_compact(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_bytes(value: object) -> bytes:
    """Return stable two-space JSON with sorted object keys and a final newline."""

    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_compact(value)).hexdigest()


def validate_smart_contract_intent(data: Mapping[str, Any]) -> dict[str, object]:
    """Validate and normalize one reviewed logical-action/attempt declaration."""

    value = _object(data, "smart contract intent")
    _reject_extra_keys(value, _INTENT_KEYS, "smart contract intent")
    _require_keys(value, _INTENT_REQUIRED, "smart contract intent")
    _require(
        value.get("schemaVersion") == INTENT_SCHEMA_VERSION,
        f"smart contract intent.schemaVersion must be {INTENT_SCHEMA_VERSION}",
    )

    request_id = _identifier(value.get("requestId"), "requestId")
    _require(
        not _TX_HASH.fullmatch(request_id),
        "requestId must be a logical business action, not a transaction hash",
    )
    occurred_text, occurred = _timestamp_value(value.get("occurredAt"), "occurredAt")
    deadline_raw = value.get("deadlineAt")
    deadline_text: str | None = None
    if deadline_raw is not None:
        deadline_text, deadline = _timestamp_value(deadline_raw, "deadlineAt")
        _require(deadline >= occurred, "deadlineAt cannot precede occurredAt")

    state = _text(value.get("state"), "state")
    _require(state in _REQUEST_STATES, f"state is unsupported: {state}")
    continuation = _optional_identifier(value.get("continuationId"), "continuationId")
    if state == "DEFERRED":
        _require(continuation is not None, "continuationId is required for DEFERRED state")

    chain_family = _text(value.get("chainFamily"), "chainFamily")
    _require(chain_family == "evm", "chainFamily must equal evm in bridge v0.1")
    function_name = _text(value.get("functionName"), "functionName")
    _require(bool(_FUNCTION_NAME.fullmatch(function_name)), "functionName is not a valid function identifier")

    normalized: dict[str, object] = {
        "schemaVersion": INTENT_SCHEMA_VERSION,
        "requestId": request_id,
        "traceId": _identifier(value.get("traceId"), "traceId"),
        "attemptId": _identifier(value.get("attemptId"), "attemptId"),
        "occurredAt": occurred_text,
        "deadlineAt": deadline_text,
        "state": state,
        "chainFamily": chain_family,
        "chainId": _integer(value.get("chainId"), "chainId", positive=True),
        "contractAddress": _address(value.get("contractAddress"), "contractAddress"),
        "functionSelector": _selector(value.get("functionSelector"), "functionSelector"),
        "functionName": function_name,
        "argsDigest": _digest(value.get("argsDigest"), "argsDigest"),
        "sender": _address(value.get("sender"), "sender"),
        "nonce": _integer(value.get("nonce"), "nonce"),
        "payloadDigest": _digest(value.get("payloadDigest"), "payloadDigest"),
        "retryOfAttemptId": _optional_identifier(
            value.get("retryOfAttemptId"), "retryOfAttemptId"
        ),
        "parentRequestId": _optional_identifier(
            value.get("parentRequestId"), "parentRequestId"
        ),
        "continuationId": continuation,
    }
    _require(
        normalized["retryOfAttemptId"] != normalized["attemptId"],
        "retryOfAttemptId cannot reference the same attemptId",
    )
    _require(
        normalized["parentRequestId"] != normalized["requestId"],
        "parentRequestId cannot reference the same requestId",
    )
    return normalized


def _validate_projection(value: Any, field: str) -> dict[str, object]:
    projection = _object(value, field)
    record_type = _text(projection.get("recordType"), f"{field}.recordType")
    if record_type == "REQUEST":
        _reject_extra_keys(projection, _REQUEST_PROJECTION_KEYS, field)
        _require_keys(
            projection,
            {"recordType", "state", "deadlineAt", "parentRequestId", "retryOfAttemptId", "continuationId", "payloadDigest"},
            field,
        )
        state = _text(projection.get("state"), f"{field}.state")
        _require(state in _REQUEST_STATES, f"{field}.state is unsupported: {state}")
        deadline = projection.get("deadlineAt")
        deadline_text = None if deadline is None else _timestamp_value(deadline, f"{field}.deadlineAt")[0]
        continuation = _optional_identifier(
            projection.get("continuationId"), f"{field}.continuationId"
        )
        if state == "DEFERRED":
            _require(continuation is not None, f"{field}.continuationId is required for DEFERRED")
        payload = projection.get("payloadDigest")
        return {
            "recordType": "REQUEST",
            "state": state,
            "deadlineAt": deadline_text,
            "parentRequestId": _optional_identifier(
                projection.get("parentRequestId"), f"{field}.parentRequestId"
            ),
            "retryOfAttemptId": _optional_identifier(
                projection.get("retryOfAttemptId"), f"{field}.retryOfAttemptId"
            ),
            "continuationId": continuation,
            "payloadDigest": None if payload is None else _digest(payload, f"{field}.payloadDigest"),
        }
    if record_type == "OUTCOME":
        _reject_extra_keys(projection, _OUTCOME_PROJECTION_KEYS, field)
        _require_keys(projection, _OUTCOME_PROJECTION_KEYS, field)
        terminal = _text(projection.get("terminalStatus"), f"{field}.terminalStatus")
        _require(
            terminal in _TERMINAL_STATUSES,
            f"{field}.terminalStatus is unsupported: {terminal}",
        )
        return {
            "recordType": "OUTCOME",
            "terminalStatus": terminal,
            "replayOfOutcomeId": _optional_identifier(
                projection.get("replayOfOutcomeId"), f"{field}.replayOfOutcomeId"
            ),
        }
    raise ContinuityBridgeError(f"{field}.recordType must be REQUEST or OUTCOME")


def _validate_evm_binding(value: Any, field: str) -> dict[str, object]:
    binding = _object(value, field)
    _reject_extra_keys(binding, _EVM_BINDING_KEYS, field)
    _require_keys(binding, _EVM_BINDING_KEYS, field)
    event_ids = binding.get("mappedEventIds")
    _require(isinstance(event_ids, list), f"{field}.mappedEventIds must be an array")
    normalized_event_ids = [
        _identifier(item, f"{field}.mappedEventIds[{index}]")
        for index, item in enumerate(event_ids)
    ]
    _require(
        len(normalized_event_ids) == len(set(normalized_event_ids)),
        f"{field}.mappedEventIds must be unique",
    )
    function_name = _text(binding.get("functionName"), f"{field}.functionName")
    _require(
        bool(_FUNCTION_NAME.fullmatch(function_name)),
        f"{field}.functionName is not a valid function identifier",
    )
    return {
        "chainId": _integer(binding.get("chainId"), f"{field}.chainId", positive=True),
        "transactionHash": _tx_hash(binding.get("transactionHash"), f"{field}.transactionHash"),
        "contractAddress": _address(binding.get("contractAddress"), f"{field}.contractAddress"),
        "functionSelector": _selector(binding.get("functionSelector"), f"{field}.functionSelector"),
        "functionName": function_name,
        "argsDigest": _digest(binding.get("argsDigest"), f"{field}.argsDigest"),
        "sender": _address(binding.get("sender"), f"{field}.sender"),
        "nonce": _integer(binding.get("nonce"), f"{field}.nonce"),
        "payloadDigest": _digest(binding.get("payloadDigest"), f"{field}.payloadDigest"),
        "mappedEventIds": normalized_event_ids,
    }


def validate_external_observation(data: Mapping[str, Any]) -> dict[str, object]:
    """Validate a reviewed external fact and its optional explicit LTP projection."""

    value = _object(data, "external observation")
    _reject_extra_keys(value, _OBSERVATION_KEYS, "external observation")
    _require_keys(value, _OBSERVATION_REQUIRED, "external observation")
    _require(
        value.get("schemaVersion") == OBSERVATION_SCHEMA_VERSION,
        f"external observation.schemaVersion must be {OBSERVATION_SCHEMA_VERSION}",
    )
    source_kind = _text(value.get("sourceKind"), "sourceKind")
    _require(source_kind in _SOURCE_KINDS, f"sourceKind is unsupported: {source_kind}")
    _require(value.get("reviewStatus") == "REVIEWED", "reviewStatus must equal REVIEWED")
    metadata = value.get("metadata")
    _require(isinstance(metadata, dict), "metadata must be an object")
    projection = (
        None
        if value.get("ltpProjection") is None
        else _validate_projection(value.get("ltpProjection"), "ltpProjection")
    )
    binding = (
        None
        if value.get("evmBinding") is None
        else _validate_evm_binding(value.get("evmBinding"), "evmBinding")
    )
    if binding is not None:
        _require(
            source_kind == "CONTRACT_RECEIPT",
            "evmBinding is allowed only for CONTRACT_RECEIPT observations in v0.1",
        )
    return {
        "schemaVersion": OBSERVATION_SCHEMA_VERSION,
        "observationId": _identifier(value.get("observationId"), "observationId"),
        "requestId": _identifier(value.get("requestId"), "requestId"),
        "traceId": _identifier(value.get("traceId"), "traceId"),
        "attemptId": _identifier(value.get("attemptId"), "attemptId"),
        "occurredAt": _timestamp_value(value.get("occurredAt"), "occurredAt")[0],
        "sourceKind": source_kind,
        "subjectDigest": _digest(value.get("subjectDigest"), "subjectDigest"),
        "resultDigest": _digest(value.get("resultDigest"), "resultDigest"),
        "parentObservationId": _optional_identifier(
            value.get("parentObservationId"), "parentObservationId"
        ),
        "reviewStatus": "REVIEWED",
        "ltpProjection": projection,
        "evmBinding": binding,
        # Metadata is retained only for the input digest.  It is never copied to evidence output.
        "metadata": copy.deepcopy(metadata),
        "claimBoundary": _text(value.get("claimBoundary"), "claimBoundary"),
    }


def _validate_capture_result(data: Mapping[str, Any]) -> dict[str, object]:
    value = _object(data, "RPC capture result")
    _require(value.get("schemaVersion") == "rpc-capture-result-v0.1", "RPC capture schemaVersion mismatch")
    status = _text(value.get("status"), "RPC capture status")
    _require(status in {"pass", "inconclusive"}, "RPC capture status is unsupported")
    capture = _object(value.get("capture"), "RPC capture")
    _require(capture.get("schemaVersion") == "rpc-capture-v0.1", "RPC capture.schemaVersion mismatch")
    chain_id = _integer(capture.get("chainId"), "RPC capture.chainId", positive=True)
    transaction_hash = _tx_hash(capture.get("transactionHash"), "RPC capture.transactionHash")
    claimed_hash = _raw_digest(value.get("captureSha256"), "RPC capture.captureSha256")
    _require(claimed_hash == _canonical_sha256(capture), "RPC capture.captureSha256 mismatch")

    receipt_raw = capture.get("receipt")
    block_raw = capture.get("blockWitness")
    if status == "pass":
        receipt = _object(receipt_raw, "RPC capture.receipt")
        _require(
            _tx_hash(receipt.get("transactionHash"), "RPC capture.receipt.transactionHash")
            == transaction_hash,
            "RPC capture receipt transactionHash mismatch",
        )
        block = _object(block_raw, "RPC capture.blockWitness")
        block_timestamp = _quantity(block.get("blockTimestamp"), "RPC capture.blockWitness.blockTimestamp")
        block_number = _quantity(block.get("blockNumber"), "RPC capture.blockWitness.blockNumber")
        observed_head = _quantity(
            block.get("observedHeadNumber"), "RPC capture.blockWitness.observedHeadNumber"
        )
        confirmations = _quantity(
            block.get("observedConfirmationCount"),
            "RPC capture.blockWitness.observedConfirmationCount",
        )
        _require(observed_head >= block_number, "RPC capture observed head is behind receipt block")
    else:
        _require(receipt_raw is None, "inconclusive RPC capture must not contain a receipt")
        _require(block_raw is None, "inconclusive RPC capture must not contain a block witness")
        receipt = None
        block = None
        block_timestamp = None
        block_number = None
        observed_head = None
        confirmations = None

    return {
        "status": status,
        "chainId": chain_id,
        "transactionHash": transaction_hash,
        "capture": copy.deepcopy(capture),
        "captureSha256": claimed_hash,
        "receipt": copy.deepcopy(receipt),
        "blockWitness": copy.deepcopy(block),
        "blockTimestamp": block_timestamp,
        "blockNumber": block_number,
        "observedHeadNumber": observed_head,
        "observedConfirmationCount": confirmations,
    }


def _validate_receipt_trace(data: Mapping[str, Any]) -> dict[str, object]:
    value = _object(data, "receipt trace result")
    _require(
        value.get("schemaVersion") == "evm-receipt-adapter-result-v0.1",
        "receipt trace must be an evm-receipt-adapter-result-v0.1 document",
    )
    status = _text(value.get("status"), "receipt trace.status")
    _require(status in {"pass", "inconclusive"}, "receipt trace.status is unsupported")
    receipt_status = _text(value.get("receiptStatus"), "receipt trace.receiptStatus")
    _require(receipt_status in {"success", "reverted"}, "receipt trace.receiptStatus is unsupported")
    trace_raw = _object(value.get("executionTrace"), "receipt trace.executionTrace")
    _require(
        trace_raw.get("schemaVersion") == "execution-trace-v0.1",
        "receipt trace executionTrace schemaVersion mismatch",
    )
    trace = execution_trace_from_dict(trace_raw)
    return {
        "status": status,
        "receiptStatus": receipt_status,
        "transactionHash": _tx_hash(value.get("transactionHash"), "receipt trace.transactionHash"),
        "chainId": _integer(value.get("chainId"), "receipt trace.chainId", positive=True),
        "receiptSha256": _raw_digest(value.get("receiptSha256"), "receipt trace.receiptSha256"),
        "profileSha256": _raw_digest(value.get("profileSha256"), "receipt trace.profileSha256"),
        "executionTrace": copy.deepcopy(trace_raw),
        "executionTraceSha256": execution_trace_sha256(trace),
    }


def _unique_by_transaction(
    records: Iterable[dict[str, object]], field: str
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    digests: dict[str, str] = {}
    for record in records:
        transaction_hash = str(record["transactionHash"])
        digest = _canonical_sha256(record)
        if transaction_hash in result:
            _require(
                digests[transaction_hash] == digest,
                f"multiple conflicting {field} records for transactionHash {transaction_hash}; repeated-capture semantics are v0.2",
            )
            continue
        result[transaction_hash] = record
        digests[transaction_hash] = digest
    return result


def _request_envelope_from_intent(intent: Mapping[str, object]) -> dict[str, object]:
    metadata = {
        "producer": "ContractGraph-QA",
        "bridge_profile": BRIDGE_PROFILE,
        "chain_family": intent["chainFamily"],
        "chain_id": intent["chainId"],
        "contract_address": intent["contractAddress"],
        "function_selector": intent["functionSelector"],
        "function_name": intent["functionName"],
        "args_digest": intent["argsDigest"],
        "sender": intent["sender"],
        "nonce": intent["nonce"],
    }
    envelope: dict[str, object] = {
        "schema_version": 1,
        "profile": REQUEST_PROFILE,
        "record_type": "REQUEST",
        "request_id": intent["requestId"],
        "trace_id": intent["traceId"],
        "attempt_id": intent["attemptId"],
        "occurred_at": intent["occurredAt"],
        "state": intent["state"],
        "deadline_at": intent["deadlineAt"],
        "parent_request_id": intent["parentRequestId"],
        "retry_of_attempt_id": intent["retryOfAttemptId"],
        "continuation_id": intent["continuationId"],
        "payload_digest": intent["payloadDigest"],
        "metadata": metadata,
    }
    return envelope


def _safe_observation_metadata(observation: Mapping[str, object]) -> dict[str, object]:
    parent = observation.get("parentObservationId")
    return {
        "producer": "ContractGraph-QA",
        "bridge_profile": BRIDGE_PROFILE,
        "source_kind": observation["sourceKind"],
        "observation_id": observation["observationId"],
        "subject_digest": observation["subjectDigest"],
        "claim_boundary_digest": f"sha256:{hashlib.sha256(str(observation['claimBoundary']).encode('utf-8')).hexdigest()}",
        **({"parent_observation_id": parent} if parent is not None else {}),
    }


def _request_envelope_from_observation(observation: Mapping[str, object]) -> dict[str, object]:
    projection = observation["ltpProjection"]
    assert isinstance(projection, dict) and projection["recordType"] == "REQUEST"
    return {
        "schema_version": 1,
        "profile": REQUEST_PROFILE,
        "record_type": "REQUEST",
        "request_id": observation["requestId"],
        "trace_id": observation["traceId"],
        "attempt_id": observation["attemptId"],
        "occurred_at": observation["occurredAt"],
        "state": projection["state"],
        "deadline_at": projection["deadlineAt"],
        "parent_request_id": projection["parentRequestId"],
        "retry_of_attempt_id": projection["retryOfAttemptId"],
        "continuation_id": projection["continuationId"],
        "payload_digest": projection["payloadDigest"],
        "metadata": _safe_observation_metadata(observation),
    }


def _outcome_envelope_from_observation(observation: Mapping[str, object]) -> dict[str, object]:
    projection = observation["ltpProjection"]
    assert isinstance(projection, dict) and projection["recordType"] == "OUTCOME"
    return {
        "schema_version": 1,
        "profile": OUTCOME_PROFILE,
        "record_type": "OUTCOME",
        "outcome_id": observation["observationId"],
        "request_id": observation["requestId"],
        "trace_id": observation["traceId"],
        "attempt_id": observation["attemptId"],
        "occurred_at": observation["occurredAt"],
        "terminal_status": projection["terminalStatus"],
        "result_digest": observation["resultDigest"],
        "replay_of_outcome_id": projection["replayOfOutcomeId"],
        "metadata": _safe_observation_metadata(observation),
    }


def _find_receipt_log(receipt: Mapping[str, Any], log_index: int) -> dict[str, Any]:
    logs = receipt.get("logs")
    _require(isinstance(logs, list), "RPC capture receipt.logs must be an array")
    matches: list[dict[str, Any]] = []
    for index, raw in enumerate(logs):
        log = _object(raw, f"RPC capture receipt.logs[{index}]")
        if _quantity(log.get("logIndex"), f"RPC capture receipt.logs[{index}].logIndex") == log_index:
            matches.append(log)
    _require(len(matches) == 1, f"mapped event logIndex {log_index} must match exactly one receipt log")
    return matches[0]


def _verify_mapped_events(
    *,
    intent: Mapping[str, object],
    binding: Mapping[str, object],
    capture: Mapping[str, object],
    receipt_trace: Mapping[str, object],
    terminal_status: str,
) -> None:
    trace = receipt_trace["executionTrace"]
    assert isinstance(trace, dict)
    events = trace.get("events")
    _require(isinstance(events, list), "receipt trace.executionTrace.events must be an array")
    by_id = {
        str(event.get("eventId")): event
        for event in events
        if isinstance(event, dict)
    }
    mapped_ids = binding["mappedEventIds"]
    assert isinstance(mapped_ids, list)

    if terminal_status == "FAILED":
        _require(not mapped_ids, "FAILED reverted receipt binding must not invent mappedEventIds")
        return

    _require(
        terminal_status in {"COMPLETED", "CANCELLED"},
        "on-chain receipt may project only COMPLETED, FAILED, or CANCELLED in v0.1",
    )
    _require(bool(mapped_ids), f"{terminal_status} receipt requires at least one reviewed mapped event")
    receipt = capture["receipt"]
    assert isinstance(receipt, dict)
    transaction_hash = str(binding["transactionHash"])
    chain_id = int(binding["chainId"])
    for event_id in mapped_ids:
        _require(event_id in by_id, f"mappedEventIds references unknown execution trace event: {event_id}")
        event = by_id[event_id]
        assert isinstance(event, dict)
        prefix = f"{transaction_hash}:"
        _require(str(event_id).startswith(prefix), f"mapped event {event_id} is not bound to transactionHash")
        try:
            log_index = int(str(event_id)[len(prefix) :])
        except ValueError as exc:
            raise ContinuityBridgeError(f"mapped event {event_id} has invalid log index") from exc
        expected_source = f"evm:{chain_id}:{transaction_hash}:log:{log_index}"
        _require(event.get("sourceRef") == expected_source, f"mapped event {event_id} sourceRef mismatch")
        log = _find_receipt_log(receipt, log_index)
        _require(not bool(log.get("removed", False)), f"mapped event {event_id} is marked removed")
        _require(
            _address(log.get("address"), f"mapped event {event_id} receipt address")
            == intent["contractAddress"],
            f"mapped event {event_id} contractAddress mismatch",
        )
        economic = event.get("economicEffect")
        commit = event.get("stateCommit")
        applied = False
        if isinstance(economic, dict):
            _require(
                economic.get("actionId") == intent["requestId"],
                f"mapped event {event_id} actionId does not bind the logical request",
            )
            _require(
                economic.get("occurrenceId") == event_id,
                f"mapped event {event_id} occurrenceId mismatch",
            )
            applied = economic.get("applied") is True
        if isinstance(commit, dict):
            _require(
                commit.get("operation") == intent["functionName"],
                f"mapped event {event_id} operation does not bind functionName",
            )
            applied = applied or commit.get("committed") is True
        _require(applied, f"mapped event {event_id} is neither applied nor committed")


def _root_outcome(
    *,
    observation: Mapping[str, object],
    intent: Mapping[str, object],
    captures: Mapping[str, dict[str, object]],
    receipt_traces: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    projection = observation["ltpProjection"]
    assert isinstance(projection, dict) and projection["recordType"] == "OUTCOME"
    source_kind = str(observation["sourceKind"])
    terminal_status = str(projection["terminalStatus"])

    if source_kind == "BACKEND_STATE" and terminal_status in {"REJECTED", "TIMED_OUT"}:
        return _outcome_envelope_from_observation(observation)
    if source_kind != "CONTRACT_RECEIPT":
        raise ContinuityBridgeError(
            f"{source_kind} cannot complete an on-chain request; use a separate downstream logical request"
        )

    binding = observation.get("evmBinding")
    _require(isinstance(binding, dict), "CONTRACT_RECEIPT root outcome requires evmBinding")
    for field in (
        "chainId",
        "contractAddress",
        "functionSelector",
        "functionName",
        "argsDigest",
        "sender",
        "nonce",
        "payloadDigest",
    ):
        _require(
            binding[field] == intent[field],
            f"evmBinding.{field} does not match intent.{field}",
        )
    _require(observation["subjectDigest"] == intent["payloadDigest"], "subjectDigest does not match intent.payloadDigest")

    transaction_hash = str(binding["transactionHash"])
    capture = captures.get(transaction_hash)
    _require(capture is not None, f"no RPC capture for evmBinding.transactionHash {transaction_hash}")
    receipt_trace = receipt_traces.get(transaction_hash)
    _require(receipt_trace is not None, f"no reviewed receipt trace for evmBinding.transactionHash {transaction_hash}")
    assert capture is not None and receipt_trace is not None
    _require(capture["status"] == "pass", "receipt was not observed; no terminal outcome may be projected")
    _require(capture["chainId"] == intent["chainId"], "RPC capture chainId does not match intent.chainId")
    _require(receipt_trace["chainId"] == intent["chainId"], "receipt trace chainId does not match intent.chainId")
    _require(
        observation["resultDigest"] == f"sha256:{capture['captureSha256']}",
        "resultDigest does not bind the exact RPC capture",
    )
    receipt = capture["receipt"]
    assert isinstance(receipt, dict)
    _require(
        receipt_trace["receiptSha256"] == _canonical_sha256(receipt),
        "receipt trace receiptSha256 does not match RPC capture receipt",
    )

    receipt_status = _quantity(receipt.get("status"), "RPC capture receipt.status")
    _require(receipt_status in {0, 1}, "RPC capture receipt.status must be 0 or 1")
    if receipt_status == 0:
        _require(terminal_status == "FAILED", "reverted receipt may project only FAILED")
        _require(receipt_trace["receiptStatus"] == "reverted", "receipt trace must classify reverted receipt")
    else:
        _require(terminal_status in {"COMPLETED", "CANCELLED"}, "successful receipt cannot be mapped to this terminalStatus")
        _require(receipt_trace["status"] == "pass", "successful receipt requires a passing reviewed event adapter result")
        _require(receipt_trace["receiptStatus"] == "success", "receipt trace must classify successful receipt")

    _verify_mapped_events(
        intent=intent,
        binding=binding,
        capture=capture,
        receipt_trace=receipt_trace,
        terminal_status=terminal_status,
    )

    outcome = _outcome_envelope_from_observation(observation)
    outcome["metadata"] = {
        **_safe_observation_metadata(observation),
        "mapping": "reviewed_evm_receipt_event",
        "transaction_hash": transaction_hash,
        "receipt_capture_digest": f"sha256:{capture['captureSha256']}",
        "execution_trace_digest": f"sha256:{receipt_trace['executionTraceSha256']}",
        "receipt_profile_digest": f"sha256:{receipt_trace['profileSha256']}",
        "observed_block_number": capture["blockNumber"],
        "observed_head_number": capture["observedHeadNumber"],
        "observed_confirmation_count": capture["observedConfirmationCount"],
        "canonical_finality_established": False,
    }
    return outcome


def _validate_snapshot_time(
    *,
    as_of: str,
    requests: Sequence[Mapping[str, object]],
    outcomes: Sequence[Mapping[str, object]],
) -> None:
    _, as_of_time = _timestamp_value(as_of, "asOf")
    for label, rows in (("request", requests), ("outcome", outcomes)):
        for index, row in enumerate(rows):
            _, occurred = _timestamp_value(row["occurred_at"], f"{label}s[{index}].occurred_at")
            _require(occurred <= as_of_time, f"{label}s[{index}].occurred_at cannot be after asOf")


def _sort_requests(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row["request_id"]),
            _timestamp_value(row["occurred_at"], "request.occurred_at")[1],
            str(row["attempt_id"]),
        ),
    )


def _sort_outcomes(rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row["request_id"]),
            _timestamp_value(row["occurred_at"], "outcome.occurred_at")[1],
            str(row["outcome_id"]),
            _canonical_sha256(row),
        ),
    )


def build_ltp_continuity_export(
    *,
    intents: Sequence[Mapping[str, Any]],
    captures: Sequence[Mapping[str, Any]],
    receipt_traces: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    as_of: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build one deterministic LTP input plus a non-verdict bridge report."""

    as_of_text, _ = _timestamp_value(as_of, "asOf")
    normalized_intents = [validate_smart_contract_intent(item) for item in intents]
    normalized_observations = [validate_external_observation(item) for item in observations]
    normalized_captures = [_validate_capture_result(item) for item in captures]
    normalized_traces = [_validate_receipt_trace(item) for item in receipt_traces]
    _require(
        bool(normalized_intents) or any(item.get("ltpProjection") for item in normalized_observations),
        "at least one intent or projected observation is required",
    )

    intent_by_attempt: dict[str, dict[str, object]] = {}
    for intent in normalized_intents:
        attempt_id = str(intent["attemptId"])
        existing = intent_by_attempt.get(attempt_id)
        if existing is not None:
            _require(
                existing["requestId"] == intent["requestId"],
                f"attemptId {attempt_id} cannot belong to multiple logical requests",
            )
            raise ContinuityBridgeError(f"duplicate smart contract intent attemptId: {attempt_id}")
        intent_by_attempt[attempt_id] = intent

    capture_by_tx = _unique_by_transaction(normalized_captures, "RPC capture")
    trace_by_tx = _unique_by_transaction(normalized_traces, "receipt trace")
    requests = [_request_envelope_from_intent(intent) for intent in normalized_intents]
    outcomes: list[dict[str, object]] = []

    root_request_ids = {str(intent["requestId"]) for intent in normalized_intents}
    exported_root_attempts: set[str] = set()
    for observation in normalized_observations:
        projection = observation.get("ltpProjection")
        if not isinstance(projection, dict):
            continue
        if projection["recordType"] == "REQUEST":
            requests.append(_request_envelope_from_observation(observation))
            continue
        if observation["requestId"] in root_request_ids:
            intent = intent_by_attempt.get(str(observation["attemptId"]))
            _require(
                intent is not None,
                f"root outcome observation attemptId {observation['attemptId']} has no matching intent",
            )
            assert intent is not None
            _require(
                observation["requestId"] == intent["requestId"],
                "root outcome observation requestId does not match its attempt intent",
            )
            _require(
                observation["traceId"] == intent["traceId"],
                "root outcome observation traceId does not match its attempt intent",
            )
            outcomes.append(
                _root_outcome(
                    observation=observation,
                    intent=intent,
                    captures=capture_by_tx,
                    receipt_traces=trace_by_tx,
                )
            )
            exported_root_attempts.add(str(intent["attemptId"]))
        else:
            outcomes.append(_outcome_envelope_from_observation(observation))

    attempt_owners: dict[str, str] = {}
    for request in requests:
        attempt_id = str(request["attempt_id"])
        owner = str(request["request_id"])
        if attempt_id in attempt_owners:
            _require(
                attempt_owners[attempt_id] == owner,
                f"attemptId {attempt_id} cannot belong to multiple logical requests",
            )
            raise ContinuityBridgeError(f"duplicate LTP request attemptId: {attempt_id}")
        attempt_owners[attempt_id] = owner

    requests = _sort_requests(requests)
    outcomes = _sort_outcomes(outcomes)
    _validate_snapshot_time(as_of=as_of_text, requests=requests, outcomes=outcomes)
    ltp_input: dict[str, object] = {
        "as_of": as_of_text,
        "requests": requests,
        "outcomes": outcomes,
    }

    root_requests_with_outcome = {
        str(outcome["request_id"])
        for outcome in outcomes
        if str(outcome["request_id"]) in root_request_ids
    }
    limited_root_requests = sorted(root_request_ids - root_requests_with_outcome)
    decisions = []
    for intent in sorted(
        normalized_intents,
        key=lambda item: (str(item["requestId"]), str(item["attemptId"])),
    ):
        exported = str(intent["attemptId"]) in exported_root_attempts
        decisions.append(
            {
                "requestId": intent["requestId"],
                "attemptId": intent["attemptId"],
                "requestProjection": "EXPORTED",
                "outcomeProjection": "EXPORTED" if exported else "NOT_EXPORTED",
                "reasons": [] if exported else ["MISSING_REVIEWED_RECEIPT_BINDING"],
            }
        )

    input_digests: list[dict[str, str]] = []
    for role, logical_field, values in (
        ("intent", "attemptId", normalized_intents),
        ("rpcCapture", "transactionHash", normalized_captures),
        ("receiptTrace", "transactionHash", normalized_traces),
        ("observation", "observationId", normalized_observations),
    ):
        for value in values:
            input_digests.append(
                {
                    "role": role,
                    "logicalId": str(value[logical_field]),
                    "sha256": _canonical_sha256(value),
                }
            )
    input_digests.sort(key=lambda row: (row["role"], row["logicalId"], row["sha256"]))

    report: dict[str, object] = {
        "schemaVersion": BRIDGE_REPORT_SCHEMA_VERSION,
        "bridgeProfile": BRIDGE_PROFILE,
        "bridgeStatus": (
            "BRIDGE_READY_WITH_LIMITATIONS" if limited_root_requests else "BRIDGE_READY"
        ),
        "asOf": as_of_text,
        "requestEnvelopeCount": len(requests),
        "outcomeEnvelopeCount": len(outcomes),
        "limitedRootRequestIds": limited_root_requests,
        "mappingDecisions": decisions,
        "inputDigests": input_digests,
        "ltpContract": copy.deepcopy(LTP_SCHEMA_CONTRACT),
        "ltpInputSha256": _canonical_sha256(ltp_input),
        "nonClaims": [
            "No continuity verdict is computed by ContractGraph-QA.",
            "Observed confirmations do not establish canonical finality.",
            "Reorg and transaction-replacement semantics are outside bridge v0.1.",
            "Reviewed intent/binding declarations are not independent transaction-body decoding.",
            "An API or indexer observation does not prove an on-chain effect.",
        ],
        "claimBoundary": (
            "ContractGraph-QA validates and projects supplied reviewed evidence into the pinned LTP v0.1 envelope contract. "
            "Only the normative LTP verifier may compute continuity status, and its report remains bounded by the supplied snapshot."
        ),
    }
    return ltp_input, report
