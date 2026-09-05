"""Strict offline adapters from reviewed tool captures into TSSE evidence.

The capture is data, never a command description to execute.  Adapters verify
every referenced file from raw bytes, derive all hashes themselves, and keep a
successful normalization separate from any claim that a security scan passed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from contractgraph_qa.tsse import (
    DIMENSIONS,
    INVARIANT_KINDS,
    MODEL_SCHEMA,
    run_tsse_model,
    validate_tsse_model,
)


CAPTURE_SCHEMA = "cgqa/tsse-tool-capture/v0.1"
PROFILE_SCHEMA = "cgqa/tsse-tool-profile/v0.1"
RESULT_SCHEMA = "cgqa/tsse-tool-adapter-result/v0.1"
CAPTURE_SCHEMA_VERSION = CAPTURE_SCHEMA
PROFILE_SCHEMA_VERSION = PROFILE_SCHEMA
RESULT_SCHEMA_VERSION = RESULT_SCHEMA
ADAPTER_VERSION = "v0.1"

MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 500_000
MAX_JSON_COLLECTION_ITEMS = 100_000
MAX_JSON_STRING_CHARS = 1_000_000

STATE_HASH_DOMAIN = "cgqa/tsse-state-projection/v0.1"
ENVIRONMENT_HASH_DOMAIN = "cgqa/tsse-environment-projection/v0.1"

TOOLS = frozenset({"cargo-soroban", "foundry", "echidna", "medusa", "slither"})
DYNAMIC_TOOLS = frozenset({"cargo-soroban", "foundry", "echidna", "medusa"})
RUN_TERMINATIONS = frozenset(
    {"completed", "failed", "timed-out", "interrupted", "crashed", "unknown"}
)
PRIMARY_ARTIFACT_KINDS = {
    "cargo-soroban": "cargo-soroban-transition-receipt",
    "foundry": "foundry-test-output",
    "echidna": "echidna-campaign-json",
    "medusa": "medusa-counterexample",
    "slither": "slither-json",
}

TOP_LEVEL_KEYS = {
    "schema",
    "captureId",
    "tool",
    "toolVersion",
    "subject",
    "run",
    "toolArtifacts",
    "observations",
    "invariants",
    "forbiddenTransitions",
    "scope",
}
PROFILE_KEYS = {
    "schema",
    "profileId",
    "tool",
    "acceptedToolVersions",
    "acceptedExitCodes",
    "observationHash",
    "subject",
    "invariants",
    "forbiddenTransitions",
    "scope",
}
SUBJECT_KEYS = {"repository", "revision", "artifacts"}
SUBJECT_ARTIFACT_KEYS = {"path", "digest"}
TOOL_ARTIFACT_KEYS = {"id", "kind", "path", "digest"}
RUN_KEYS = {"argv", "exitCode", "termination", "seed", "bounds"}
BOUND_KEYS = {"testLimit", "maxSequenceLength", "timeLimitSeconds", "workers"}
OBSERVATION_KEYS = {
    "id",
    "incoming",
    "time",
    "space",
    "state",
    "environment",
    "actor",
    "authority",
    "value",
}
INCOMING_KEYS = {"id", "cause", "action", "evidenceRefs"}
TIME_KEYS = {"block", "timestamp", "epoch"}
SPACE_KEYS = {"chainId", "contract", "callFrame", "storageDomain", "protocolLocation"}
STATE_KEYS = {"phase", "values"}
ENVIRONMENT_KEYS = {"oracleState", "tokenModel", "feeMode", "implementation"}
ACTOR_KEYS = {"identity", "role"}
AUTHORITY_KEYS = {"epoch", "status"}
VALUE_KEYS = {"unit", "locked", "moved"}
INVARIANT_KEYS = {"id", "kind", "description"}
FORBIDDEN_TRANSITION_KEYS = {"id", "fromPhase", "toPhase", "invariantId"}
NATIVE_BINDING_KEYS = {"artifactId", "locator", "index"}


class ToolCaptureError(ValueError):
    """Raised when a capture or referenced artifact is not trustworthy enough."""


TSSEAdapterError = ToolCaptureError


def canonical_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 JSON representation used by every adapter hash."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ToolCaptureError(f"value is not canonical JSON: {exc}") from exc


def canonical_sha256(value: object) -> str:
    """Hash canonical JSON as a lowercase SHA-256 digest."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Hash one raw byte snapshot as a lowercase SHA-256 digest."""

    return hashlib.sha256(value).hexdigest()


def canonical_result_hash(result: dict[str, Any]) -> str:
    """Hash an adapter result while excluding its self-referential resultHash."""

    material = {key: value for key, value in result.items() if key != "resultHash"}
    return canonical_sha256(material)


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ToolCaptureError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ToolCaptureError(f"non-finite JSON number {value!r} is not allowed")


def _enforce_json_limits(value: object, field: str) -> None:
    stack: list[tuple[object, int, str]] = [(value, 0, field)]
    nodes = 0
    while stack:
        current, depth, current_field = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ToolCaptureError(
                f"{field} exceeds the {MAX_JSON_NODES} JSON-node limit"
            )
        if depth > MAX_JSON_DEPTH:
            raise ToolCaptureError(
                f"{current_field} exceeds the {MAX_JSON_DEPTH} level nesting limit"
            )
        if isinstance(current, str):
            if len(current) > MAX_JSON_STRING_CHARS:
                raise ToolCaptureError(
                    f"{current_field} exceeds the {MAX_JSON_STRING_CHARS} character limit"
                )
            continue
        if current is None or isinstance(current, (bool, int)):
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                raise ToolCaptureError(f"{current_field} contains NaN or infinity")
            continue
        if isinstance(current, list):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise ToolCaptureError(
                    f"{current_field} exceeds the collection item limit"
                )
            stack.extend(
                (item, depth + 1, f"{current_field}[{index}]")
                for index, item in enumerate(current)
            )
            continue
        if isinstance(current, dict):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise ToolCaptureError(
                    f"{current_field} exceeds the collection item limit"
                )
            for key, item in current.items():
                if not isinstance(key, str):
                    raise ToolCaptureError(
                        f"{current_field} object keys must be strings"
                    )
                if len(key) > MAX_JSON_STRING_CHARS:
                    raise ToolCaptureError(
                        f"{current_field} contains an oversized object key"
                    )
                stack.append((item, depth + 1, f"{current_field}.{key}"))
            continue
        raise ToolCaptureError(f"{current_field} contains a non-JSON value")


def parse_json_bytes(raw: bytes, field: str) -> object:
    """Parse one UTF-8 JSON snapshot with duplicate-key and NaN rejection."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolCaptureError(f"{field} must be UTF-8 JSON: {exc}") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except ToolCaptureError:
        raise
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ToolCaptureError(f"failed to parse {field}: {exc}") from exc
    _enforce_json_limits(parsed, field)
    return parsed


def _read_limited(path: Path, *, maximum: int, field: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ToolCaptureError(f"failed to stat {field} {path}: {exc}") from exc
    if size > maximum:
        raise ToolCaptureError(
            f"{field} exceeds the {maximum}-byte input limit"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ToolCaptureError(f"failed to read {field} {path}: {exc}") from exc
    if len(raw) > maximum:
        raise ToolCaptureError(
            f"{field} exceeds the {maximum}-byte input limit"
        )
    return raw


def _strict_object(
    value: object,
    field: str,
    *,
    keys: set[str],
    required: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolCaptureError(f"{field} must be an object")
    unknown = sorted(set(value) - keys)
    if unknown:
        raise ToolCaptureError(f"{field} contains unknown fields: {', '.join(unknown)}")
    required_keys = keys if required is None else required
    missing = sorted(required_keys - set(value))
    if missing:
        raise ToolCaptureError(f"{field} missing required fields: {', '.join(missing)}")
    return value


def _array(value: object, field: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise ToolCaptureError(f"{field} must be an array")
    if non_empty and not value:
        raise ToolCaptureError(f"{field} must not be empty")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolCaptureError(f"{field} must be a non-empty string")
    if value != value.strip():
        raise ToolCaptureError(f"{field} must not contain leading or trailing whitespace")
    return value


def _integer(value: object, field: str, *, non_negative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolCaptureError(f"{field} must be an integer")
    if non_negative and value < 0:
        raise ToolCaptureError(f"{field} must be non-negative")
    return value


def _nullable_non_negative_int(value: object, field: str) -> int | None:
    if value is None:
        return None
    return _integer(value, field, non_negative=True)


def _nullable_non_negative_number(value: object, field: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolCaptureError(f"{field} must be a non-negative finite number or null")
    if not math.isfinite(value) or value < 0:
        raise ToolCaptureError(f"{field} must be a non-negative finite number or null")
    return value


def _digest(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ToolCaptureError(f"{field} must be a 64-character lowercase SHA-256 digest")
    return text


def _json_value(value: object, field: str) -> object:
    _enforce_json_limits(value, field)
    return value


def _relative_path(value: object, field: str) -> str:
    text = _text(value, field)
    if "\\" in text:
        raise ToolCaptureError(f"{field} must use portable '/' separators")
    if "\x00" in text:
        raise ToolCaptureError(f"{field} must not contain NUL")
    posix = PurePosixPath(text)
    windows = PureWindowsPath(text)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or windows.root:
        raise ToolCaptureError(f"{field} must be relative")
    if any(part in {"", ".", ".."} for part in posix.parts):
        raise ToolCaptureError(f"{field} must not contain empty, current, or parent segments")
    if posix.as_posix() != text:
        raise ToolCaptureError(f"{field} must be a normalized relative path")
    return text


def _unique_text_array(
    value: object,
    field: str,
    *,
    non_empty: bool = False,
) -> list[str]:
    items = [_text(item, f"{field}[{index}]") for index, item in enumerate(_array(value, field, non_empty=non_empty))]
    if len(items) != len(set(items)):
        raise ToolCaptureError(f"{field} must not contain duplicates")
    return items


def _validate_run(value: object, *, tool: str) -> dict[str, Any]:
    run = _strict_object(value, "capture.run", keys=RUN_KEYS)
    argv = _array(run["argv"], "capture.run.argv", non_empty=True)
    for index, item in enumerate(argv):
        _text(item, f"capture.run.argv[{index}]")
    exit_code = run["exitCode"]
    if exit_code is not None:
        _integer(exit_code, "capture.run.exitCode", non_negative=True)
    termination = _text(run["termination"], "capture.run.termination")
    if termination not in RUN_TERMINATIONS:
        raise ToolCaptureError(
            f"capture.run.termination has unsupported value {termination!r}"
        )
    if termination == "completed" and exit_code is None:
        raise ToolCaptureError(
            "capture.run.exitCode must be recorded for a completed run"
        )
    if run["seed"] is not None:
        _text(run["seed"], "capture.run.seed")
    bounds = _strict_object(run["bounds"], "capture.run.bounds", keys=BOUND_KEYS)
    test_limit = _nullable_non_negative_int(
        bounds["testLimit"], "capture.run.bounds.testLimit"
    )
    max_sequence = _nullable_non_negative_int(
        bounds["maxSequenceLength"], "capture.run.bounds.maxSequenceLength"
    )
    time_limit = _nullable_non_negative_int(
        bounds["timeLimitSeconds"], "capture.run.bounds.timeLimitSeconds"
    )
    workers = _nullable_non_negative_int(
        bounds["workers"], "capture.run.bounds.workers"
    )
    if workers is not None and workers < 1:
        raise ToolCaptureError("capture.run.bounds.workers must be at least 1 or null")
    if termination == "completed" and tool in DYNAMIC_TOOLS:
        if test_limit is None or test_limit < 1:
            raise ToolCaptureError(
                "a completed dynamic run requires positive testLimit"
            )
        if time_limit is None or time_limit < 1:
            raise ToolCaptureError(
                "a completed dynamic run requires positive timeLimitSeconds"
            )
        if max_sequence is None or max_sequence < 1:
            raise ToolCaptureError(
                "a completed dynamic run requires positive maxSequenceLength"
            )
        if workers is None:
            raise ToolCaptureError(
                "a completed dynamic run requires positive workers"
            )
    return run


def _validate_subject(value: object, *, field: str = "capture.subject") -> dict[str, Any]:
    subject = _strict_object(value, field, keys=SUBJECT_KEYS)
    _text(subject["repository"], f"{field}.repository")
    _text(subject["revision"], f"{field}.revision")
    artifacts = _array(subject["artifacts"], f"{field}.artifacts", non_empty=True)
    paths: set[str] = set()
    for index, raw in enumerate(artifacts):
        item_field = f"{field}.artifacts[{index}]"
        item = _strict_object(raw, item_field, keys=SUBJECT_ARTIFACT_KEYS)
        path = _relative_path(item["path"], f"{item_field}.path")
        if path in paths:
            raise ToolCaptureError(f"duplicate subject artifact path {path!r}")
        paths.add(path)
        _digest(item["digest"], f"{item_field}.digest")
    subject["artifacts"] = sorted(artifacts, key=lambda item: item["path"])
    return subject


def _validate_tool_artifacts(value: object) -> tuple[list[dict[str, Any]], set[str]]:
    artifacts = _array(value, "capture.toolArtifacts", non_empty=True)
    ids: set[str] = set()
    paths: set[str] = set()
    for index, raw in enumerate(artifacts):
        field = f"capture.toolArtifacts[{index}]"
        item = _strict_object(raw, field, keys=TOOL_ARTIFACT_KEYS)
        item_id = _text(item["id"], f"{field}.id")
        if item_id in ids:
            raise ToolCaptureError(f"duplicate tool artifact id {item_id!r}")
        ids.add(item_id)
        path = _relative_path(item["path"], f"{field}.path")
        if path in paths:
            raise ToolCaptureError(f"duplicate tool artifact path {path!r}")
        paths.add(path)
        _text(item["kind"], f"{field}.kind")
        _digest(item["digest"], f"{field}.digest")
    return sorted(artifacts, key=lambda item: item["id"]), ids


def _validate_invariants(
    value: object,
    *,
    dynamic: bool,
    field: str = "capture.invariants",
) -> tuple[list[dict[str, Any]], set[str]]:
    invariants = _array(value, field, non_empty=dynamic)
    ids: set[str] = set()
    for index, raw in enumerate(invariants):
        item_field = f"{field}[{index}]"
        item = _strict_object(raw, item_field, keys=INVARIANT_KEYS)
        item_id = _text(item["id"], f"{item_field}.id")
        if item_id in ids:
            raise ToolCaptureError(f"duplicate invariant id {item_id!r}")
        ids.add(item_id)
        kind = _text(item["kind"], f"{item_field}.kind")
        if kind not in INVARIANT_KINDS:
            raise ToolCaptureError(f"{item_field}.kind has unsupported value {kind!r}")
        _text(item["description"], f"{item_field}.description")
    return sorted(invariants, key=lambda item: item["id"]), ids


def _validate_forbidden(
    value: object,
    *,
    invariant_ids: set[str],
    dynamic: bool,
    field: str = "capture.forbiddenTransitions",
) -> list[dict[str, Any]]:
    forbidden = _array(value, field, non_empty=dynamic)
    ids: set[str] = set()
    referenced_invariants: set[str] = set()
    for index, raw in enumerate(forbidden):
        item_field = f"{field}[{index}]"
        item = _strict_object(raw, item_field, keys=FORBIDDEN_TRANSITION_KEYS)
        item_id = _text(item["id"], f"{item_field}.id")
        if item_id in ids:
            raise ToolCaptureError(f"duplicate forbidden transition id {item_id!r}")
        ids.add(item_id)
        _text(item["fromPhase"], f"{item_field}.fromPhase")
        _text(item["toPhase"], f"{item_field}.toPhase")
        invariant_id = _text(item["invariantId"], f"{item_field}.invariantId")
        if invariant_id not in invariant_ids:
            raise ToolCaptureError(
                f"{item_field}.invariantId references unknown invariant {invariant_id!r}"
            )
        referenced_invariants.add(invariant_id)
    orphaned = sorted(invariant_ids - referenced_invariants)
    if orphaned:
        raise ToolCaptureError(
            f"{field} leaves invariant policy unreferenced: "
            + ", ".join(orphaned)
        )
    return sorted(forbidden, key=lambda item: item["id"])


def _validate_coordinates(observation: dict[str, Any], field: str) -> None:
    time = _strict_object(observation["time"], f"{field}.time", keys=TIME_KEYS)
    for key in sorted(TIME_KEYS):
        _integer(time[key], f"{field}.time.{key}", non_negative=True)

    space = _strict_object(observation["space"], f"{field}.space", keys=SPACE_KEYS)
    for key in sorted(SPACE_KEYS):
        _text(space[key], f"{field}.space.{key}")

    state = _strict_object(observation["state"], f"{field}.state", keys=STATE_KEYS)
    _text(state["phase"], f"{field}.state.phase")
    values = state["values"]
    if not isinstance(values, dict):
        raise ToolCaptureError(f"{field}.state.values must be an object")
    _json_value(values, f"{field}.state.values")

    environment = _strict_object(
        observation["environment"], f"{field}.environment", keys=ENVIRONMENT_KEYS
    )
    for key in sorted(ENVIRONMENT_KEYS):
        _text(environment[key], f"{field}.environment.{key}")

    actor = _strict_object(observation["actor"], f"{field}.actor", keys=ACTOR_KEYS)
    for key in sorted(ACTOR_KEYS):
        _text(actor[key], f"{field}.actor.{key}")

    authority = _strict_object(
        observation["authority"], f"{field}.authority", keys=AUTHORITY_KEYS
    )
    _integer(authority["epoch"], f"{field}.authority.epoch", non_negative=True)
    _text(authority["status"], f"{field}.authority.status")

    economic_value = _strict_object(
        observation["value"], f"{field}.value", keys=VALUE_KEYS
    )
    _text(economic_value["unit"], f"{field}.value.unit")
    _integer(economic_value["locked"], f"{field}.value.locked", non_negative=True)
    _integer(economic_value["moved"], f"{field}.value.moved", non_negative=True)


def _validate_observations(
    value: object,
    *,
    dynamic: bool,
    artifact_ids: set[str],
) -> list[dict[str, Any]]:
    observations = _array(value, "capture.observations")
    if not dynamic:
        if observations:
            raise ToolCaptureError("Slither captures must have no observations")
        return observations
    if len(observations) < 2:
        raise ToolCaptureError("dynamic captures require at least two observations")

    observation_ids: set[str] = set()
    incoming_ids: set[str] = set()
    referenced_artifacts: set[str] = set()
    for index, raw in enumerate(observations):
        field = f"capture.observations[{index}]"
        observation = _strict_object(raw, field, keys=OBSERVATION_KEYS)
        observation_id = _text(observation["id"], f"{field}.id")
        if observation_id in observation_ids:
            raise ToolCaptureError(f"duplicate observation id {observation_id!r}")
        observation_ids.add(observation_id)
        incoming = observation["incoming"]
        if index == 0:
            if incoming is not None:
                raise ToolCaptureError("the first observation incoming value must be null")
        else:
            incoming_item = _strict_object(incoming, f"{field}.incoming", keys=INCOMING_KEYS)
            incoming_id = _text(incoming_item["id"], f"{field}.incoming.id")
            if incoming_id in incoming_ids:
                raise ToolCaptureError(f"duplicate incoming transition id {incoming_id!r}")
            incoming_ids.add(incoming_id)
            _text(incoming_item["cause"], f"{field}.incoming.cause")
            _text(incoming_item["action"], f"{field}.incoming.action")
            refs = _unique_text_array(
                incoming_item["evidenceRefs"],
                f"{field}.incoming.evidenceRefs",
                non_empty=True,
            )
            unknown = sorted(set(refs) - artifact_ids)
            if unknown:
                raise ToolCaptureError(
                    f"{field}.incoming.evidenceRefs references unknown artifacts: "
                    + ", ".join(unknown)
                )
            incoming_item["evidenceRefs"] = sorted(refs)
            referenced_artifacts.update(refs)
        _validate_coordinates(observation, field)

    orphaned = sorted(artifact_ids - referenced_artifacts)
    if orphaned:
        raise ToolCaptureError(
            "capture.toolArtifacts contains evidence not referenced by a transition: "
            + ", ".join(orphaned)
        )
    return observations


def validate_tool_capture(data: object) -> dict[str, Any]:
    """Validate and normalize one strict ``cgqa/tsse-tool-capture/v0.1`` object."""

    _enforce_json_limits(data, "capture")
    capture = copy.deepcopy(_strict_object(data, "capture", keys=TOP_LEVEL_KEYS))
    if capture["schema"] != CAPTURE_SCHEMA:
        raise ToolCaptureError(f"capture.schema must equal {CAPTURE_SCHEMA!r}")
    _text(capture["captureId"], "capture.captureId")
    tool = _text(capture["tool"], "capture.tool")
    if tool not in TOOLS:
        raise ToolCaptureError(f"capture.tool has unsupported value {tool!r}")
    _text(capture["toolVersion"], "capture.toolVersion")
    _text(capture["scope"], "capture.scope")
    capture["subject"] = _validate_subject(capture["subject"])
    capture["run"] = _validate_run(capture["run"], tool=tool)
    tool_artifacts, artifact_ids = _validate_tool_artifacts(capture["toolArtifacts"])
    capture["toolArtifacts"] = tool_artifacts

    dynamic = tool in DYNAMIC_TOOLS
    invariants, invariant_ids = _validate_invariants(capture["invariants"], dynamic=dynamic)
    capture["invariants"] = invariants
    capture["forbiddenTransitions"] = _validate_forbidden(
        capture["forbiddenTransitions"],
        invariant_ids=invariant_ids,
        dynamic=dynamic,
    )
    capture["observations"] = _validate_observations(
        capture["observations"], dynamic=dynamic, artifact_ids=artifact_ids
    )
    if dynamic:
        maximum = capture["run"]["bounds"]["maxSequenceLength"]
        sequence_length = len(capture["observations"]) - 1
        if maximum is not None and sequence_length > maximum:
            raise ToolCaptureError(
                "capture observation sequence exceeds run.bounds.maxSequenceLength"
            )

    primary_kind = PRIMARY_ARTIFACT_KINDS[tool]
    primary = [item for item in tool_artifacts if item["kind"] == primary_kind]
    if len(primary) != 1:
        raise ToolCaptureError(
            f"{tool} capture requires exactly one artifact of kind {primary_kind!r}"
        )
    if tool == "slither":
        if len(tool_artifacts) != 1 or len(primary) != 1:
            raise ToolCaptureError("Slither captures require exactly one slither-json artifact")
        if capture["invariants"] or capture["forbiddenTransitions"]:
            raise ToolCaptureError(
                "Slither captures must not declare dynamic invariants or forbidden transitions"
            )
    return capture


def validate_tool_profile(data: object) -> dict[str, Any]:
    """Validate one externally reviewed ``cgqa/tsse-tool-profile/v0.1``."""

    _enforce_json_limits(data, "profile")
    profile = copy.deepcopy(_strict_object(data, "profile", keys=PROFILE_KEYS))
    if profile["schema"] != PROFILE_SCHEMA:
        raise ToolCaptureError(f"profile.schema must equal {PROFILE_SCHEMA!r}")
    _text(profile["profileId"], "profile.profileId")
    tool = _text(profile["tool"], "profile.tool")
    if tool not in TOOLS:
        raise ToolCaptureError(f"profile.tool has unsupported value {tool!r}")
    versions = _unique_text_array(
        profile["acceptedToolVersions"],
        "profile.acceptedToolVersions",
        non_empty=True,
    )
    profile["acceptedToolVersions"] = sorted(versions)
    exit_codes = _array(
        profile["acceptedExitCodes"],
        "profile.acceptedExitCodes",
        non_empty=True,
    )
    normalized_codes = [
        _integer(item, f"profile.acceptedExitCodes[{index}]", non_negative=True)
        for index, item in enumerate(exit_codes)
    ]
    if len(normalized_codes) != len(set(normalized_codes)):
        raise ToolCaptureError("profile.acceptedExitCodes must not contain duplicates")
    profile["acceptedExitCodes"] = sorted(normalized_codes)
    profile["subject"] = _validate_subject(
        profile["subject"], field="profile.subject"
    )
    dynamic = tool in DYNAMIC_TOOLS
    observation_hash = profile["observationHash"]
    if dynamic:
        _digest(observation_hash, "profile.observationHash")
    elif observation_hash is not None:
        raise ToolCaptureError("Slither profile.observationHash must be null")
    invariants, invariant_ids = _validate_invariants(
        profile["invariants"],
        dynamic=dynamic,
        field="profile.invariants",
    )
    profile["invariants"] = invariants
    profile["forbiddenTransitions"] = _validate_forbidden(
        profile["forbiddenTransitions"],
        invariant_ids=invariant_ids,
        dynamic=dynamic,
        field="profile.forbiddenTransitions",
    )
    _text(profile["scope"], "profile.scope")
    if tool == "slither" and (
        profile["invariants"] or profile["forbiddenTransitions"]
    ):
        raise ToolCaptureError(
            "Slither profiles must not declare dynamic invariants or forbidden transitions"
        )
    return profile


def load_tool_capture(path: str | Path) -> dict[str, Any]:
    """Load one UTF-8 capture once, reject duplicate keys, and validate it."""

    capture_path = Path(path)
    raw = _read_limited(
        capture_path,
        maximum=MAX_CAPTURE_BYTES,
        field="tool capture",
    )
    return validate_tool_capture(parse_json_bytes(raw, f"tool capture {capture_path}"))


def load_tool_profile(path: str | Path) -> dict[str, Any]:
    """Load one size-bounded reviewed tool profile with strict JSON parsing."""

    profile_path = Path(path)
    raw = _read_limited(
        profile_path,
        maximum=MAX_CAPTURE_BYTES,
        field="tool profile",
    )
    return validate_tool_profile(parse_json_bytes(raw, f"tool profile {profile_path}"))


def _resolve_artifact(base_dir: Path, relative: str) -> Path:
    try:
        base = base_dir.resolve(strict=True)
    except OSError as exc:
        raise ToolCaptureError(f"capture base directory cannot be resolved: {exc}") from exc
    if not base.is_dir():
        raise ToolCaptureError(f"capture base path is not a directory: {base_dir}")
    candidate = base.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ToolCaptureError(f"artifact {relative!r} cannot be resolved: {exc}") from exc
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ToolCaptureError(f"artifact {relative!r} escapes the capture directory") from exc
    if not resolved.is_file():
        raise ToolCaptureError(f"artifact {relative!r} is not a regular file")
    return resolved


def _verify_artifacts(
    capture: dict[str, Any],
    base_dir: Path,
    profile: dict[str, Any],
    profile_base_dir: Path,
) -> dict[str, Any]:
    raw_cache: dict[Path, bytes] = {}
    total_bytes = 0

    def verify(
        item: dict[str, Any],
        field: str,
        root: Path,
    ) -> tuple[dict[str, Any], bytes]:
        nonlocal total_bytes
        path = _resolve_artifact(root, item["path"])
        if path not in raw_cache:
            raw_cache[path] = _read_limited(
                path,
                maximum=MAX_ARTIFACT_BYTES,
                field=field,
            )
            total_bytes += len(raw_cache[path])
            if total_bytes > MAX_TOTAL_ARTIFACT_BYTES:
                raise ToolCaptureError(
                    "verified artifact set exceeds the total byte limit"
                )
        raw = raw_cache[path]
        observed = sha256_bytes(raw)
        if observed != item["digest"]:
            raise ToolCaptureError(
                f"{field} {item['path']!r} digest mismatch: expected {item['digest']}, observed {observed}"
            )
        verified = {key: item[key] for key in item}
        verified["digest"] = observed
        verified["byteLength"] = len(raw)
        return verified, raw

    capture_subject_artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(capture["subject"]["artifacts"]):
        item_verified, _ = verify(
            item,
            f"capture subject artifact[{index}]",
            base_dir,
        )
        capture_subject_artifacts.append(item_verified)

    profile_subject_artifacts: list[dict[str, Any]] = []
    for index, item in enumerate(profile["subject"]["artifacts"]):
        item_verified, _ = verify(
            item,
            f"profile subject artifact[{index}]",
            profile_base_dir,
        )
        profile_subject_artifacts.append(item_verified)

    tool_artifacts: list[dict[str, Any]] = []
    tool_raw: dict[str, bytes] = {}
    for index, item in enumerate(capture["toolArtifacts"]):
        item_verified, raw = verify(
            item,
            f"capture tool artifact[{index}]",
            base_dir,
        )
        tool_artifacts.append(item_verified)
        tool_raw[item["id"]] = raw

    capture_subject_artifacts.sort(key=lambda item: item["path"])
    profile_subject_artifacts.sort(key=lambda item: item["path"])
    tool_artifacts.sort(key=lambda item: item["id"])
    bundle_material = [
        {"path": item["path"], "digest": item["digest"]}
        for item in profile_subject_artifacts
    ]
    return {
        "subjectArtifacts": profile_subject_artifacts,
        "captureSubjectArtifacts": capture_subject_artifacts,
        "profileSubjectArtifacts": profile_subject_artifacts,
        "toolArtifacts": tool_artifacts,
        "toolRaw": tool_raw,
        "subjectBundleHash": canonical_sha256(bundle_material),
    }


def profile_material(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the full validated external policy bound into adapter identity."""

    return copy.deepcopy(profile)


def _require_profile_match(
    capture: dict[str, Any], profile: dict[str, Any]
) -> None:
    for key in ("tool", "subject", "invariants", "forbiddenTransitions", "scope"):
        if canonical_bytes(capture[key]) != canonical_bytes(profile[key]):
            raise ToolCaptureError(
                f"capture.{key} does not exactly match reviewed profile.{key}"
            )
    if capture["toolVersion"] not in profile["acceptedToolVersions"]:
        raise ToolCaptureError(
            f"capture.toolVersion {capture['toolVersion']!r} is not accepted by profile"
        )
    exit_code = capture["run"]["exitCode"]
    if exit_code is not None and exit_code not in profile["acceptedExitCodes"]:
        raise ToolCaptureError(
            f"capture.run.exitCode {exit_code!r} is not accepted by profile"
        )
    if capture["tool"] in DYNAMIC_TOOLS:
        observed = canonical_sha256(capture["observations"])
        if observed != profile["observationHash"]:
            raise ToolCaptureError(
                "capture.observations do not match reviewed profile.observationHash"
            )


def primary_artifact(
    capture: dict[str, Any], verified: dict[str, Any]
) -> tuple[dict[str, Any], bytes]:
    """Return the single verified tool-specific primary artifact and raw bytes."""

    expected_kind = PRIMARY_ARTIFACT_KINDS[capture["tool"]]
    matches = [
        item for item in verified["toolArtifacts"] if item["kind"] == expected_kind
    ]
    if len(matches) != 1:
        raise ToolCaptureError(
            f"{capture['tool']} requires exactly one verified {expected_kind!r} artifact"
        )
    item = matches[0]
    return item, verified["toolRaw"][item["id"]]


def incoming_actions(capture: dict[str, Any]) -> list[str]:
    """Return the reviewed dynamic action sequence in causal order."""

    return [item["incoming"]["action"] for item in capture["observations"][1:]]


def function_base(value: object, field: str) -> str:
    """Normalize a Solidity function signature to its non-empty base name."""

    text = _text(value, field)
    base = text.split("(", 1)[0].strip()
    if not base or any(character.isspace() for character in base):
        raise ToolCaptureError(f"{field} has an invalid function name")
    return base


def executable_basename(capture: dict[str, Any]) -> str:
    """Return a platform-neutral lowercase basename of recorded argv[0]."""

    return capture["run"]["argv"][0].replace("\\", "/").rsplit("/", 1)[-1].lower()


def require_completed_run(capture: dict[str, Any], *, tool: str) -> None:
    if capture["run"]["termination"] != "completed":
        raise ToolCaptureError(f"{tool} native binding requires a completed run")
    if capture["run"]["exitCode"] is None:
        raise ToolCaptureError(f"{tool} native binding requires a recorded exit code")


def build_native_bindings(
    capture: dict[str, Any],
    *,
    artifact_id: str,
    locators: list[str],
) -> dict[str, dict[str, Any]]:
    transitions = capture["observations"][1:]
    if len(locators) != len(transitions):
        raise ToolCaptureError("native locator count does not match capture transitions")
    return {
        observation["incoming"]["id"]: {
            "artifactId": artifact_id,
            "locator": locators[index],
            "index": index,
        }
        for index, observation in enumerate(transitions)
    }


def _changed_dimensions(source: dict[str, Any], target: dict[str, Any]) -> list[str]:
    return [
        dimension
        for dimension in DIMENSIONS
        if canonical_bytes(source[dimension]) != canonical_bytes(target[dimension])
    ]


def build_dynamic_tsse_model(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Build a fully derived linear TSSE model from a validated dynamic capture."""

    tool = capture["tool"]
    if tool not in DYNAMIC_TOOLS:
        raise ToolCaptureError(f"{tool!r} is not a dynamic TSSE adapter")
    profile_hash = canonical_sha256(profile_material(profile))
    exact_subject = {
        "repository": profile["subject"]["repository"],
        "commit": "sha256:" + verified["subjectBundleHash"],
        "adapter": f"cgqa-tsse-{tool}/{ADAPTER_VERSION}:{profile_hash}",
    }
    subject_hash = canonical_sha256(exact_subject)

    evidence = [
        {
            "id": item["id"],
            "subjectHash": subject_hash,
            "kind": item["kind"],
            "source": item["path"],
            "digest": item["digest"],
        }
        for item in verified["toolArtifacts"]
    ]
    nodes: list[dict[str, Any]] = []
    for index, observation in enumerate(capture["observations"]):
        environment_coordinates = dict(observation["environment"])
        state_projection = {
            "domain": STATE_HASH_DOMAIN,
            "phase": observation["state"]["phase"],
            "values": observation["state"]["values"],
        }
        environment_projection = {
            "domain": ENVIRONMENT_HASH_DOMAIN,
            "environment": environment_coordinates,
        }
        nodes.append(
            {
                "id": observation["id"],
                "subjectHash": subject_hash,
                "time": {**observation["time"], "causalStep": index},
                "space": copy.deepcopy(observation["space"]),
                "state": {
                    "phase": observation["state"]["phase"],
                    "stateHash": canonical_sha256(state_projection),
                    "values": copy.deepcopy(observation["state"]["values"]),
                },
                "environment": {
                    **environment_coordinates,
                    "externalStateHash": canonical_sha256(environment_projection),
                },
                "actor": copy.deepcopy(observation["actor"]),
                "authority": copy.deepcopy(observation["authority"]),
                "value": copy.deepcopy(observation["value"]),
            }
        )

    transitions: list[dict[str, Any]] = []
    for index in range(1, len(nodes)):
        incoming = capture["observations"][index]["incoming"]
        transition = {
            "id": incoming["id"],
            "sequence": index - 1,
            "predecessorId": None if index == 1 else transitions[-1]["id"],
            "sourceId": nodes[index - 1]["id"],
            "targetId": nodes[index]["id"],
            "cause": incoming["cause"],
            "action": incoming["action"],
            "evidenceRefs": list(incoming["evidenceRefs"]),
            "crossedBoundaries": _changed_dimensions(nodes[index - 1], nodes[index]),
        }
        transitions.append(transition)

    model = {
        "schema": MODEL_SCHEMA,
        "modelId": capture["captureId"],
        "exactSubject": exact_subject,
        "evidence": evidence,
        "nodes": nodes,
        "transitions": transitions,
        "invariants": copy.deepcopy(profile["invariants"]),
        "forbiddenTransitions": copy.deepcopy(profile["forbiddenTransitions"]),
        "requirements": {
            "requireMonotonicTime": True,
            "requireCausalContinuity": True,
            "requireExactSubjectBinding": True,
            "requireEvidenceBindings": True,
        },
        "scope": profile["scope"],
    }
    return validate_tsse_model(model), profile_hash


def adapt_dynamic_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
    *,
    expected_tool: str,
    native_bindings: dict[str, dict[str, Any]],
    native_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Finish normalization after a tool-specific native receipt is bound."""

    if capture["tool"] != expected_tool:
        raise ToolCaptureError(
            f"{expected_tool} adapter cannot process tool {capture['tool']!r}"
        )
    require_completed_run(capture, tool=expected_tool)
    if native_evidence.get("status") != "bound":
        raise ToolCaptureError("native evidence must be successfully bound")
    transition_ids = {
        item["incoming"]["id"] for item in capture["observations"][1:]
    }
    if set(native_bindings) != transition_ids:
        raise ToolCaptureError(
            "nativeBindings must cover every transition exactly once"
        )
    primary, _ = primary_artifact(capture, verified)
    for transition_id, binding in native_bindings.items():
        if not isinstance(binding, dict):
            raise ToolCaptureError(
                f"nativeBindings[{transition_id!r}] must be an object"
            )
        if set(binding) != NATIVE_BINDING_KEYS:
            raise ToolCaptureError(
                f"nativeBindings[{transition_id!r}] has invalid fields"
            )
        if binding.get("artifactId") != primary["id"]:
            raise ToolCaptureError(
                f"nativeBindings[{transition_id!r}] is not bound to the primary artifact"
            )

    model, profile_hash = build_dynamic_tsse_model(capture, profile, verified)
    tsse_result = run_tsse_model(model)
    normalization_status = "complete"
    nested_status = tsse_result.get("status")
    if nested_status == "hold":
        status = "hold"
    elif nested_status == "pass":
        status = "ready"
    else:
        raise ToolCaptureError(
            f"nested TSSE returned unsupported status {nested_status!r}"
        )

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "captureId": capture["captureId"],
        "tool": capture["tool"],
        "toolVersion": capture["toolVersion"],
        "status": status,
        "normalizationStatus": normalization_status,
        "scanVerdict": "NOT_ASSESSED",
        "captureHash": canonical_sha256(capture),
        "subjectBundleHash": verified["subjectBundleHash"],
        "profileId": profile["profileId"],
        "profileHash": profile_hash,
        "normalizationHash": canonical_sha256(
            {
                "profileHash": profile_hash,
                "run": capture["run"],
                "nativeBindings": native_bindings,
                "nativeEvidence": native_evidence,
                "tsseModel": model,
                "tsseResult": tsse_result,
            }
        ),
        "subject": {
            "repository": profile["subject"]["repository"],
            "revision": profile["subject"]["revision"],
            "artifacts": verified["subjectArtifacts"],
        },
        "profileArtifactVerification": {
            "status": "verified",
            "subjectBundleHash": verified["subjectBundleHash"],
            "artifacts": verified["profileSubjectArtifacts"],
        },
        "captureSubjectArtifacts": verified["captureSubjectArtifacts"],
        "run": copy.deepcopy(capture["run"]),
        "toolArtifacts": verified["toolArtifacts"],
        "nativeBindings": copy.deepcopy(native_bindings),
        "nativeEvidence": copy.deepcopy(native_evidence),
        "tsseModel": model,
        "tsseResult": tsse_result,
        "claimBoundary": (
            "The adapter verified capture and independently reviewed profile artifacts, parsed the "
            "supported native primary receipt, and bound its action sequence to reviewed finite "
            "observations before TSSE evaluation. It did not execute argv, prove producer or binary "
            "authenticity, infer campaign completeness, discover omitted states, or assess system "
            "security. READY means this bounded evidence is suitable for review, not a scan PASS."
        ),
        "verificationDebt": [
            "The capture author remains responsible for observation completeness and semantic accuracy.",
            "Native parsing binds the supported receipt fields, not all tool implementation semantics.",
            "Dynamic campaign coverage and unobserved reachable paths remain unassessed.",
            "Independent replay packaging and tool-binary attestation remain outstanding.",
        ],
    }
    result["resultHash"] = canonical_result_hash(result)
    return result


def _adapt_validated_capture(
    capture: dict[str, Any],
    base_dir: Path,
    profile: dict[str, Any],
    profile_base_dir: Path,
) -> dict[str, Any]:
    _require_profile_match(capture, profile)
    verified = _verify_artifacts(
        capture,
        base_dir,
        profile,
        profile_base_dir,
    )
    tool = capture["tool"]
    if tool == "foundry":
        from contractgraph_qa.tsse_adapters.foundry import adapt_foundry_capture

        return adapt_foundry_capture(capture, profile, verified)
    if tool == "echidna":
        from contractgraph_qa.tsse_adapters.echidna import adapt_echidna_capture

        return adapt_echidna_capture(capture, profile, verified)
    if tool == "medusa":
        from contractgraph_qa.tsse_adapters.medusa import adapt_medusa_capture

        return adapt_medusa_capture(capture, profile, verified)
    if tool == "cargo-soroban":
        from contractgraph_qa.tsse_adapters.soroban import adapt_soroban_capture

        return adapt_soroban_capture(capture, profile, verified)
    if tool == "slither":
        from contractgraph_qa.tsse_adapters.slither import adapt_slither_capture

        return adapt_slither_capture(capture, profile, verified)
    raise ToolCaptureError(f"no adapter dispatch is registered for tool {tool!r}")


def adapt_tool_capture(
    data: object,
    base_dir: str | Path,
    profile: object,
    profile_base_dir: str | Path,
    capture_path: str | Path | None = None,
    profile_path: str | Path | None = None,
) -> dict[str, Any]:
    """Adapt a capture only under an independently reviewed external profile.

    Path arguments are provenance-only checks; recorded argv is never executed.
    """

    capture = validate_tool_capture(data)
    reviewed_profile = validate_tool_profile(profile)
    root = Path(base_dir)
    profile_root = Path(profile_base_dir)
    for label, candidate in (
        ("capture_path", capture_path),
        ("profile_path", profile_path),
    ):
        if candidate is not None and Path(candidate).name in {"", ".", ".."}:
            raise ToolCaptureError(f"{label} must identify a JSON file")
    return _adapt_validated_capture(
        capture,
        root,
        reviewed_profile,
        profile_root,
    )


def adapt_tool_capture_file(
    capture_path: str | Path,
    profile_path: str | Path,
) -> dict[str, Any]:
    """Load capture/profile once and verify artifacts below their own parents."""

    capture_source = Path(capture_path)
    profile_source = Path(profile_path)
    capture_raw = _read_limited(
        capture_source,
        maximum=MAX_CAPTURE_BYTES,
        field="tool capture",
    )
    profile_raw = _read_limited(
        profile_source,
        maximum=MAX_CAPTURE_BYTES,
        field="tool profile",
    )
    capture = validate_tool_capture(
        parse_json_bytes(capture_raw, f"tool capture {capture_source}")
    )
    profile = validate_tool_profile(
        parse_json_bytes(profile_raw, f"tool profile {profile_source}")
    )
    return _adapt_validated_capture(
        capture,
        capture_source.parent,
        profile,
        profile_source.parent,
    )


__all__ = [
    "ACTOR_KEYS",
    "AUTHORITY_KEYS",
    "BOUND_KEYS",
    "ADAPTER_VERSION",
    "CAPTURE_SCHEMA",
    "CAPTURE_SCHEMA_VERSION",
    "DYNAMIC_TOOLS",
    "ENVIRONMENT_KEYS",
    "FORBIDDEN_TRANSITION_KEYS",
    "INCOMING_KEYS",
    "INVARIANT_KEYS",
    "MAX_ARTIFACT_BYTES",
    "MAX_CAPTURE_BYTES",
    "MAX_JSON_COLLECTION_ITEMS",
    "MAX_JSON_DEPTH",
    "MAX_JSON_NODES",
    "MAX_JSON_STRING_CHARS",
    "MAX_TOTAL_ARTIFACT_BYTES",
    "NATIVE_BINDING_KEYS",
    "OBSERVATION_KEYS",
    "PRIMARY_ARTIFACT_KINDS",
    "PROFILE_KEYS",
    "PROFILE_SCHEMA",
    "PROFILE_SCHEMA_VERSION",
    "RESULT_SCHEMA",
    "RESULT_SCHEMA_VERSION",
    "RUN_KEYS",
    "RUN_TERMINATIONS",
    "SPACE_KEYS",
    "STATE_KEYS",
    "STATE_HASH_DOMAIN",
    "SUBJECT_ARTIFACT_KEYS",
    "SUBJECT_KEYS",
    "TIME_KEYS",
    "TOOLS",
    "TOOL_ARTIFACT_KEYS",
    "TOP_LEVEL_KEYS",
    "TSSEAdapterError",
    "ToolCaptureError",
    "VALUE_KEYS",
    "ENVIRONMENT_HASH_DOMAIN",
    "adapt_dynamic_capture",
    "adapt_tool_capture",
    "adapt_tool_capture_file",
    "build_native_bindings",
    "build_dynamic_tsse_model",
    "canonical_bytes",
    "canonical_result_hash",
    "canonical_sha256",
    "executable_basename",
    "function_base",
    "incoming_actions",
    "load_tool_capture",
    "load_tool_profile",
    "parse_json_bytes",
    "primary_artifact",
    "profile_material",
    "require_completed_run",
    "sha256_bytes",
    "validate_tool_capture",
    "validate_tool_profile",
]
