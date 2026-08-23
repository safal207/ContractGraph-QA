"""Fail-closed JSON-RPC capture for transaction receipts and block witnesses.

The capture treats an RPC endpoint as an observation source, not as finality authority.
It never persists the endpoint URL or credentials. A successful capture binds:
- requested transaction hash;
- reported chain id;
- transaction receipt;
- containing block hash/header witness;
- observed head number and confirmation count at capture time.

No wall-clock value participates in verification and no finality claim is inferred.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CAPTURE_SCHEMA_VERSION = "rpc-capture-v0.1"
RESULT_SCHEMA_VERSION = "rpc-capture-result-v0.1"

RpcCaller = Callable[[str, str, list[object]], object]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _hex(value: Any, field: str, *, bytes_length: int | None = None) -> str:
    text = _text(value, field).lower()
    _require(text.startswith("0x"), f"{field} must be 0x-prefixed hex")
    body = text[2:]
    _require(bool(body), f"{field} must not be empty")
    try:
        bytes.fromhex(body)
    except ValueError as exc:
        raise ValueError(f"{field} must be valid hex") from exc
    if bytes_length is not None:
        _require(len(body) == bytes_length * 2, f"{field} must be {bytes_length} bytes")
    return text


def _quantity(value: Any, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        _require(value >= 0, f"{field} must be non-negative")
        return value
    text = _text(value, field).lower()
    _require(text.startswith("0x"), f"{field} must be an integer or hex quantity")
    try:
        parsed = int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid hex quantity") from exc
    _require(parsed >= 0, f"{field} must be non-negative")
    return parsed


def validate_rpc_url(rpc_url: str) -> str:
    value = _text(rpc_url, "rpc URL")
    parsed = urlsplit(value)
    _require(parsed.scheme in {"http", "https"}, "rpc URL scheme must be http or https")
    _require(bool(parsed.netloc), "rpc URL must include a host")
    return value


def normalize_tx_hash(tx_hash: str) -> str:
    return _hex(tx_hash, "transaction hash", bytes_length=32)


def json_rpc_call(rpc_url: str, method: str, params: list[object]) -> object:
    """Perform one JSON-RPC call without exposing the endpoint in returned evidence."""

    endpoint = validate_rpc_url(rpc_url)
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - URL is explicitly validated above
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError(f"RPC transport failed for {method}: {type(exc).__name__}") from exc

    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"RPC response for {method} is not valid JSON") from exc
    _require(isinstance(decoded, dict), f"RPC response for {method} must be an object")
    if decoded.get("error") is not None:
        error = decoded["error"]
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            raise ValueError(f"RPC {method} returned error code={code!r} message={message!r}")
        raise ValueError(f"RPC {method} returned an error")
    _require("result" in decoded, f"RPC response for {method} is missing result")
    return decoded["result"]


def _call(caller: RpcCaller, rpc_url: str, method: str, params: list[object]) -> object:
    return caller(rpc_url, method, params)


def capture_transaction(
    rpc_url: str,
    tx_hash: str,
    *,
    caller: RpcCaller = json_rpc_call,
) -> dict[str, object]:
    """Capture one transaction receipt and its block witness from a JSON-RPC endpoint."""

    validate_rpc_url(rpc_url)
    requested_tx = normalize_tx_hash(tx_hash)

    chain_raw = _call(caller, rpc_url, "eth_chainId", [])
    chain_id = _quantity(chain_raw, "eth_chainId result")

    receipt_raw = _call(caller, rpc_url, "eth_getTransactionReceipt", [requested_tx])
    if receipt_raw is None:
        observation = {
            "schemaVersion": CAPTURE_SCHEMA_VERSION,
            "chainId": chain_id,
            "transactionHash": requested_tx,
            "receipt": None,
            "blockWitness": None,
        }
        return {
            "schemaVersion": RESULT_SCHEMA_VERSION,
            "status": "inconclusive",
            "reason": "transaction_receipt_not_observed",
            "capture": observation,
            "captureSha256": _canonical_sha256(observation),
            "claimBoundary": "The configured RPC endpoint did not return a receipt; no mined/finality claim is made.",
        }

    _require(isinstance(receipt_raw, dict), "eth_getTransactionReceipt result must be an object or null")
    receipt = dict(receipt_raw)
    observed_tx = _hex(receipt.get("transactionHash"), "receipt.transactionHash", bytes_length=32)
    _require(observed_tx == requested_tx, "receipt transactionHash does not match requested transaction")
    block_hash = _hex(receipt.get("blockHash"), "receipt.blockHash", bytes_length=32)
    block_number = _quantity(receipt.get("blockNumber"), "receipt.blockNumber")

    block_raw = _call(caller, rpc_url, "eth_getBlockByHash", [block_hash, False])
    _require(isinstance(block_raw, dict), "eth_getBlockByHash result must be an object")
    block = dict(block_raw)
    observed_block_hash = _hex(block.get("hash"), "block.hash", bytes_length=32)
    observed_block_number = _quantity(block.get("number"), "block.number")
    _require(observed_block_hash == block_hash, "block.hash does not match receipt.blockHash")
    _require(observed_block_number == block_number, "block.number does not match receipt.blockNumber")
    parent_hash = _hex(block.get("parentHash"), "block.parentHash", bytes_length=32)
    timestamp = _quantity(block.get("timestamp"), "block.timestamp")

    head_raw = _call(caller, rpc_url, "eth_blockNumber", [])
    head_number = _quantity(head_raw, "eth_blockNumber result")
    _require(head_number >= block_number, "observed head is behind receipt block")
    confirmation_count = head_number - block_number + 1

    response_digests = {
        "chainIdResponseSha256": _canonical_sha256(chain_raw),
        "receiptResponseSha256": _canonical_sha256(receipt_raw),
        "blockResponseSha256": _canonical_sha256(block_raw),
        "headResponseSha256": _canonical_sha256(head_raw),
    }
    observation = {
        "schemaVersion": CAPTURE_SCHEMA_VERSION,
        "chainId": chain_id,
        "transactionHash": requested_tx,
        "receipt": receipt,
        "blockWitness": {
            "blockHash": block_hash,
            "blockNumber": block_number,
            "parentHash": parent_hash,
            "blockTimestamp": timestamp,
            "observedHeadNumber": head_number,
            "observedConfirmationCount": confirmation_count,
        },
        "rpcResponseDigests": response_digests,
    }
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": "pass",
        "capture": observation,
        "captureSha256": _canonical_sha256(observation),
        "claimBoundary": (
            "Exact over the responses returned by one configured RPC endpoint. The endpoint URL/credentials are not persisted. "
            "Observed confirmation count is not a finality guarantee and no independent canonical-chain claim is made."
        ),
    }


def write_capture_result(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
