"""Map raw JSON-RPC transaction receipts into normalized ExecutionTrace evidence.

The adapter is deliberately profile-driven and fail-closed. It does not guess an
ABI, event signature, state version, authority, or economic meaning. A reviewed
profile pins exact topic0 values and declares how supported 32-byte EVM words map
to ExecutionTrace fields.

Supported extraction sources:
- constant
- eventRef (transactionHash:logIndex)
- txHash
- logIndex
- address
- topic[index]
- dataWord[index]

Supported decoders for topic/data words:
- uint256
- bytes32
- address
- bool

Optional enumMap converts a decoded scalar to a reviewed symbolic string. Optional
prefix/suffix are applied after decoding and enum mapping.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from contractgraph_qa.execution_trace import execution_trace_from_dict

PROFILE_SCHEMA_VERSION = "evm-receipt-profile-v0.1"
RESULT_SCHEMA_VERSION = "evm-receipt-adapter-result-v0.1"

_PROFILE_KEYS = {
    "schemaVersion",
    "profileId",
    "traceIdPrefix",
    "chainId",
    "contractAddresses",
    "events",
    "scope",
}
_EVENT_KEYS = {"name", "topic0", "economicEffect", "stateCommit"}
_ECONOMIC_FIELDS = {"actionId", "effectKey", "occurrenceId", "applied"}
_COMMIT_FIELDS = {
    "commitId",
    "conflictKey",
    "parentState",
    "parentVersion",
    "operation",
    "successorState",
    "successorVersion",
    "committed",
}
_SPEC_KEYS = {"source", "value", "index", "decode", "enumMap", "prefix", "suffix"}
_SOURCES = {"constant", "eventRef", "txHash", "logIndex", "address", "topic", "dataWord"}
_DECODERS = {"uint256", "bytes32", "address", "bool"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hex(value: Any, field: str, *, bytes_length: int | None = None) -> str:
    text = _text(value, field).lower()
    _require(text.startswith("0x"), f"{field} must be 0x-prefixed hex")
    body = text[2:]
    _require(body and len(body) % 2 == 0, f"{field} must contain whole bytes")
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


def _normalize_address(value: Any, field: str) -> str:
    return _hex(value, field, bytes_length=20)


def _validate_spec(spec: Any, field: str) -> dict[str, Any]:
    _require(isinstance(spec, dict), f"{field} must be an object")
    extras = sorted(set(spec) - _SPEC_KEYS)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")
    source = _text(spec.get("source"), f"{field}.source")
    _require(source in _SOURCES, f"{field}.source is unsupported: {source}")
    result = dict(spec)
    result["source"] = source

    if source == "constant":
        _require("value" in spec, f"{field}.value is required for constant source")
    elif source in {"topic", "dataWord"}:
        index = spec.get("index")
        _require(isinstance(index, int) and not isinstance(index, bool) and index >= 0,
                 f"{field}.index must be a non-negative integer")
        decode = _text(spec.get("decode"), f"{field}.decode")
        _require(decode in _DECODERS, f"{field}.decode is unsupported: {decode}")
        result["decode"] = decode

    enum_map = spec.get("enumMap")
    if enum_map is not None:
        _require(isinstance(enum_map, dict) and bool(enum_map), f"{field}.enumMap must be a non-empty object")
        normalized_map: dict[str, str] = {}
        for key, value in enum_map.items():
            normalized_map[str(key)] = _text(value, f"{field}.enumMap[{key!r}]")
        result["enumMap"] = normalized_map

    for name in ("prefix", "suffix"):
        if name in spec:
            result[name] = _text(spec[name], f"{field}.{name}")
    return result


def profile_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(data, dict), "EVM receipt profile must be a JSON object")
    extras = sorted(set(data) - _PROFILE_KEYS)
    _require(not extras, "EVM receipt profile contains unexpected fields: " + ", ".join(extras))
    required = {"schemaVersion", "profileId", "traceIdPrefix", "chainId", "contractAddresses", "events"}
    missing = sorted(required - set(data))
    _require(not missing, "EVM receipt profile missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == PROFILE_SCHEMA_VERSION,
             f"schemaVersion must be {PROFILE_SCHEMA_VERSION}")

    addresses_raw = data["contractAddresses"]
    _require(isinstance(addresses_raw, list), "contractAddresses must be an array")
    addresses = [_normalize_address(item, f"contractAddresses[{index}]") for index, item in enumerate(addresses_raw)]
    _require(len(addresses) == len(set(addresses)), "contractAddresses must contain unique values")

    events_raw = data["events"]
    _require(isinstance(events_raw, list) and bool(events_raw), "events must be a non-empty array")
    events: list[dict[str, Any]] = []
    topics: set[str] = set()
    for index, item in enumerate(events_raw):
        field = f"events[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        extras = sorted(set(item) - _EVENT_KEYS)
        missing = sorted({"name", "topic0"} - set(item))
        _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")
        _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
        topic0 = _hex(item["topic0"], f"{field}.topic0", bytes_length=32)
        _require(topic0 not in topics, f"duplicate topic0 in profile: {topic0}")
        topics.add(topic0)

        mapped: dict[str, Any] = {
            "name": _text(item["name"], f"{field}.name"),
            "topic0": topic0,
        }
        for section_name, allowed_fields in (
            ("economicEffect", _ECONOMIC_FIELDS),
            ("stateCommit", _COMMIT_FIELDS),
        ):
            section = item.get(section_name)
            if section is None:
                continue
            _require(isinstance(section, dict), f"{field}.{section_name} must be an object")
            extras = sorted(set(section) - allowed_fields)
            missing_fields = sorted(allowed_fields - set(section))
            _require(not extras, f"{field}.{section_name} contains unexpected fields: {', '.join(extras)}")
            _require(not missing_fields, f"{field}.{section_name} missing required fields: {', '.join(missing_fields)}")
            mapped[section_name] = {
                key: _validate_spec(section[key], f"{field}.{section_name}.{key}")
                for key in sorted(allowed_fields)
            }
        _require("economicEffect" in mapped or "stateCommit" in mapped,
                 f"{field} must define economicEffect and/or stateCommit")
        events.append(mapped)

    scope_raw = data.get("scope")
    return {
        "schemaVersion": PROFILE_SCHEMA_VERSION,
        "profileId": _text(data["profileId"], "profileId"),
        "traceIdPrefix": _text(data["traceIdPrefix"], "traceIdPrefix"),
        "chainId": _quantity(data["chainId"], "chainId"),
        "contractAddresses": addresses,
        "events": events,
        **({"scope": _text(scope_raw, "scope")} if scope_raw is not None else {}),
    }


def load_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return profile_from_dict(json.load(handle))


def _unwrap_receipt(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and "result" in data:
        _require(data.get("result") is not None, "JSON-RPC receipt result is null")
        data = data["result"]
    _require(isinstance(data, dict), "receipt must be a JSON object or JSON-RPC result wrapper")
    return data


def load_receipt(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return _unwrap_receipt(json.load(handle))


def _decode_word(word: str, decoder: str, field: str) -> object:
    normalized = _hex(word, field, bytes_length=32)
    body = normalized[2:]
    if decoder == "uint256":
        return int(body, 16)
    if decoder == "bytes32":
        return normalized
    if decoder == "address":
        return "0x" + body[-40:]
    if decoder == "bool":
        value = int(body, 16)
        _require(value in {0, 1}, f"{field} bool word must be 0 or 1")
        return bool(value)
    raise ValueError(f"unsupported decoder: {decoder}")


def _data_word(data: str, index: int, field: str) -> str:
    normalized = _hex(data, field)
    body = normalized[2:]
    _require(len(body) % 64 == 0, f"{field} must contain whole 32-byte ABI words")
    start = index * 64
    end = start + 64
    _require(end <= len(body), f"{field} does not contain dataWord[{index}]")
    return "0x" + body[start:end]


def _extract(spec: Mapping[str, Any], *, receipt: Mapping[str, Any], log: Mapping[str, Any], field: str) -> object:
    source = str(spec["source"])
    tx_hash = _hex(receipt.get("transactionHash"), "receipt.transactionHash", bytes_length=32)
    log_index = _quantity(log.get("logIndex"), f"{field}.logIndex")

    if source == "constant":
        value: object = spec["value"]
    elif source == "eventRef":
        value = f"{tx_hash}:{log_index}"
    elif source == "txHash":
        value = tx_hash
    elif source == "logIndex":
        value = log_index
    elif source == "address":
        value = _normalize_address(log.get("address"), f"{field}.address")
    elif source == "topic":
        topics = log.get("topics")
        _require(isinstance(topics, list), f"{field}.topics must be an array")
        index = int(spec["index"])
        _require(index < len(topics), f"{field}.topics does not contain topic[{index}]")
        value = _decode_word(str(topics[index]), str(spec["decode"]), f"{field}.topic[{index}]")
    elif source == "dataWord":
        index = int(spec["index"])
        word = _data_word(str(log.get("data")), index, f"{field}.data")
        value = _decode_word(word, str(spec["decode"]), f"{field}.dataWord[{index}]")
    else:  # pragma: no cover - profile validation prevents this
        raise ValueError(f"unsupported source: {source}")

    enum_map = spec.get("enumMap")
    if isinstance(enum_map, dict):
        key = str(value)
        _require(key in enum_map, f"{field} decoded value has no enumMap entry: {key}")
        value = enum_map[key]

    prefix = spec.get("prefix")
    suffix = spec.get("suffix")
    if prefix is not None or suffix is not None:
        value = f"{prefix or ''}{value}{suffix or ''}"
    return value


def _coerce_mapping(section: Mapping[str, Mapping[str, Any]], *, receipt: Mapping[str, Any], log: Mapping[str, Any], field: str) -> dict[str, object]:
    values = {
        key: _extract(spec, receipt=receipt, log=log, field=f"{field}.{key}")
        for key, spec in section.items()
    }
    for key in ("actionId", "effectKey", "occurrenceId", "commitId", "conflictKey", "parentState", "operation", "successorState"):
        if key in values:
            values[key] = _text(str(values[key]), f"{field}.{key}")
    for key in ("parentVersion", "successorVersion"):
        if key in values:
            value = values[key]
            _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                     f"{field}.{key} must decode to a non-negative integer")
    for key in ("applied", "committed"):
        if key in values:
            _require(isinstance(values[key], bool), f"{field}.{key} must decode to a boolean")
    return values


def adapt_receipt(receipt_data: dict[str, Any], profile_data: dict[str, Any]) -> dict[str, object]:
    """Adapt one mined JSON-RPC receipt into one normalized ExecutionTrace document."""

    receipt = _unwrap_receipt(receipt_data)
    profile = profile_from_dict(profile_data)
    tx_hash = _hex(receipt.get("transactionHash"), "receipt.transactionHash", bytes_length=32)
    status = _quantity(receipt.get("status"), "receipt.status")
    _require(status in {0, 1}, "receipt.status must be 0x0/0 or 0x1/1")
    logs = receipt.get("logs")
    _require(isinstance(logs, list), "receipt.logs must be an array")

    event_by_topic = {str(item["topic0"]): item for item in profile["events"]}
    allowed_addresses = set(profile["contractAddresses"])
    events: list[dict[str, object]] = []
    unmatched_logs = 0
    removed_logs = 0
    filtered_address_logs = 0

    if status == 1:
        for index, raw_log in enumerate(logs):
            field = f"receipt.logs[{index}]"
            _require(isinstance(raw_log, dict), f"{field} must be an object")
            if bool(raw_log.get("removed", False)):
                removed_logs += 1
                continue
            address = _normalize_address(raw_log.get("address"), f"{field}.address")
            if allowed_addresses and address not in allowed_addresses:
                filtered_address_logs += 1
                continue
            topics = raw_log.get("topics")
            _require(isinstance(topics, list) and bool(topics), f"{field}.topics must be a non-empty array")
            topic0 = _hex(topics[0], f"{field}.topics[0]", bytes_length=32)
            mapping = event_by_topic.get(topic0)
            if mapping is None:
                unmatched_logs += 1
                continue
            log_index = _quantity(raw_log.get("logIndex"), f"{field}.logIndex")
            event_ref = f"{tx_hash}:{log_index}"
            event: dict[str, object] = {
                "eventId": event_ref,
                "sourceRef": f"evm:{profile['chainId']}:{tx_hash}:log:{log_index}",
            }
            if "economicEffect" in mapping:
                event["economicEffect"] = _coerce_mapping(
                    mapping["economicEffect"], receipt=receipt, log=raw_log,
                    field=f"{field}.{mapping['name']}.economicEffect",
                )
            if "stateCommit" in mapping:
                event["stateCommit"] = _coerce_mapping(
                    mapping["stateCommit"], receipt=receipt, log=raw_log,
                    field=f"{field}.{mapping['name']}.stateCommit",
                )
            events.append(event)

    trace_dict: dict[str, object] = {
        "schemaVersion": "execution-trace-v0.1",
        "traceId": f"{profile['traceIdPrefix']}:{tx_hash}",
        "events": events,
    }
    scope = profile.get("scope")
    if isinstance(scope, str):
        trace_dict["scope"] = scope

    # Re-parse through the canonical ExecutionTrace validator before returning.
    execution_trace_from_dict(trace_dict)
    adapter_status = "pass" if status == 1 and bool(events) else "inconclusive"
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": adapter_status,
        "receiptStatus": "success" if status == 1 else "reverted",
        "transactionHash": tx_hash,
        "chainId": profile["chainId"],
        "matchedEventCount": len(events),
        "unmatchedLogCount": unmatched_logs,
        "removedLogCount": removed_logs,
        "filteredAddressLogCount": filtered_address_logs,
        "receiptSha256": _canonical_sha256(receipt),
        "profileSha256": _canonical_sha256(profile),
        "executionTrace": trace_dict,
        "claimBoundary": (
            "Exact only for logs matched by reviewed topic0/address mappings and supported 32-byte field decoders. "
            "Receipt completeness, provider canonicality, ABI/profile correctness, omitted events, internal calls, "
            "authority and time witnesses remain separate provenance claims."
        ),
    }


def adapt_receipt_files(receipt_path: Path, profile_path: Path) -> dict[str, object]:
    return adapt_receipt(load_receipt(receipt_path), load_profile(profile_path))
