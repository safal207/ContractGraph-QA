#!/usr/bin/env python3
"""Fail closed when ContractGraph-QA JSON Schemas drift from runtime contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.engagement import (  # noqa: E402
    CHECK_KEYS,
    ENGAGEMENT_RESULT_KEYS,
    SAFE_ARTIFACT_ID,
    STATUSES,
)
from contractgraph_qa.finding import (  # noqa: E402
    ACTION_KEYS,
    INVARIANT_KEYS,
    MANIFEST_KEYS,
    RESULT_KEYS,
    SCOPE_KEYS,
    SEARCH_KEYS,
    SEVERITIES,
    STEP_KEYS,
)

MANIFEST_SCHEMA = ROOT / "graph" / "schema" / "adapter-manifest.schema.json"
RESULT_SCHEMA = ROOT / "graph" / "schema" / "explorer-result.schema.json"
ENGAGEMENT_RESULT_SCHEMA = ROOT / "graph" / "schema" / "engagement-result.schema.json"
NON_WHITESPACE_PATTERN = r"\S"


class SchemaContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaContractError(message)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(data, dict), f"schema must be an object: {path}")
    return data


def _keys(schema: dict[str, Any], field: str) -> set[str]:
    props = schema.get("properties")
    _require(isinstance(props, dict), f"{field}.properties missing")
    return set(props)


def _required(schema: dict[str, Any], field: str) -> set[str]:
    required = schema.get("required")
    _require(isinstance(required, list), f"{field}.required missing")
    return set(required)


def _strict_object(schema: dict[str, Any], field: str) -> None:
    _require(schema.get("type") == "object", f"{field} must be type object")
    _require(schema.get("additionalProperties") is False, f"{field} must reject extra fields")


def _non_blank_string(schema: dict[str, Any], field: str) -> None:
    _require(schema.get("type") == "string", f"{field} must be a string")
    _require(schema.get("minLength") == 1, f"{field}.minLength must equal 1")
    _require(schema.get("pattern") == NON_WHITESPACE_PATTERN, f"{field}.pattern must equal \\S")


def _step_contract(step: dict[str, Any], field: str) -> None:
    _strict_object(step, field)
    _require(_keys(step, field) == STEP_KEYS, f"{field} property set drift")
    _require(_required(step, field) == STEP_KEYS - {"parameter"}, f"{field} required set drift")
    for name in ("actionId", "preState", "postState", "effect"):
        _non_blank_string(step["properties"][name], f"{field}.{name}")
    parameter = step["properties"]["parameter"]
    one_of = parameter.get("oneOf")
    _require(isinstance(one_of, list), f"{field}.parameter.oneOf missing")
    _require(
        {entry.get("type") for entry in one_of if isinstance(entry, dict)} == {"integer", "string"},
        f"{field}.parameter type drift",
    )


def check_schema_contract() -> dict[str, Any]:
    manifest = _load(MANIFEST_SCHEMA)
    result = _load(RESULT_SCHEMA)
    engagement_result = _load(ENGAGEMENT_RESULT_SCHEMA)

    _strict_object(manifest, "manifest")
    _require(_keys(manifest, "manifest") == MANIFEST_KEYS, "manifest property set drift")
    _require(_required(manifest, "manifest") == MANIFEST_KEYS, "manifest required set drift")
    _require(manifest["properties"]["schemaVersion"].get("const") == 1, "manifest schemaVersion drift")
    for name in ("adapterId", "contract", "network"):
        _non_blank_string(manifest["properties"][name], f"manifest.{name}")

    scope = manifest["properties"]["scope"]
    _strict_object(scope, "manifest.scope")
    _require(_keys(scope, "manifest.scope") == SCOPE_KEYS, "manifest.scope property set drift")
    _require(_required(scope, "manifest.scope") == SCOPE_KEYS, "manifest.scope required set drift")
    for name in sorted(SCOPE_KEYS):
        _non_blank_string(scope["properties"][name], f"manifest.scope.{name}")

    search = manifest["properties"]["search"]
    _strict_object(search, "manifest.search")
    _require(_keys(search, "manifest.search") == SEARCH_KEYS, "manifest.search property set drift")
    _require(_required(search, "manifest.search") == SEARCH_KEYS, "manifest.search required set drift")
    _require(search["properties"]["maxDepth"] == {"type": "integer", "minimum": 1}, "maxDepth schema drift")

    state_fields = manifest["properties"]["stateFields"]
    _require(state_fields.get("type") == "array", "stateFields must be an array")
    _require(state_fields.get("minItems") == 1, "stateFields.minItems drift")
    _require(state_fields.get("uniqueItems") is True, "stateFields must require uniqueItems")
    _non_blank_string(state_fields["items"], "manifest.stateFields[]")

    action = manifest["properties"]["actions"]["items"]
    _strict_object(action, "manifest.actions[]")
    _require(_keys(action, "manifest.actions[]") == ACTION_KEYS, "action property set drift")
    _require(_required(action, "manifest.actions[]") == ACTION_KEYS, "action required set drift")
    for name in sorted(ACTION_KEYS):
        _non_blank_string(action["properties"][name], f"manifest.actions[].{name}")

    invariant = manifest["properties"]["invariants"]["items"]
    _strict_object(invariant, "manifest.invariants[]")
    _require(_keys(invariant, "manifest.invariants[]") == INVARIANT_KEYS, "invariant property set drift")
    _require(_required(invariant, "manifest.invariants[]") == INVARIANT_KEYS, "invariant required set drift")
    for name in sorted(INVARIANT_KEYS - {"severity"}):
        _non_blank_string(invariant["properties"][name], f"manifest.invariants[].{name}")
    severity = invariant["properties"]["severity"]
    _non_blank_string(severity, "manifest.invariants[].severity")
    _require(set(severity.get("enum", [])) == SEVERITIES, "severity enum drift")

    _strict_object(result, "result")
    _require(_keys(result, "result") == RESULT_KEYS, "result property set drift")
    expected_result_required = RESULT_KEYS - {"exploredCandidates", "notes"}
    _require(_required(result, "result") == expected_result_required, "result required set drift")
    for name in ("adapterId", "scopeId", "findingId", "invariantId", "replay"):
        _non_blank_string(result["properties"][name], f"result.{name}")
    fingerprint = result["properties"]["manifestSha256"]
    _require(fingerprint.get("type") == "string", "result.manifestSha256 must be string")
    _require(fingerprint.get("pattern") == "^[0-9a-f]{64}$", "manifestSha256 pattern drift")
    _non_blank_string(result["properties"]["notes"], "result.notes")
    _require(
        result["properties"]["exploredCandidates"] == {"type": "integer", "minimum": 0},
        "exploredCandidates schema drift",
    )
    path = result["properties"]["path"]
    _require(path.get("type") == "array", "result.path must be an array")
    _require(path.get("minItems") == 1, "result.path.minItems drift")
    _step_contract(path["items"], "result.path[]")

    _strict_object(engagement_result, "engagementResult")
    _require(
        _keys(engagement_result, "engagementResult") == ENGAGEMENT_RESULT_KEYS,
        "engagement result property set drift",
    )
    _require(
        _required(engagement_result, "engagementResult") == ENGAGEMENT_RESULT_KEYS,
        "engagement result required set drift",
    )
    _require(
        engagement_result["properties"]["schemaVersion"].get("const") == 1,
        "engagement result schemaVersion drift",
    )
    engagement_id = engagement_result["properties"]["engagementId"]
    _require(engagement_id.get("type") == "string", "engagementId must be string")
    _require(engagement_id.get("minLength") == 1, "engagementId minLength drift")
    _require(engagement_id.get("pattern") == SAFE_ARTIFACT_ID.pattern, "engagementId safe pattern drift")
    for name in ("adapterId", "scopeId", "searchRunId", "replay"):
        _non_blank_string(engagement_result["properties"][name], f"engagementResult.{name}")
    engagement_fingerprint = engagement_result["properties"]["manifestSha256"]
    _require(engagement_fingerprint.get("type") == "string", "engagement manifestSha256 must be string")
    _require(
        engagement_fingerprint.get("pattern") == "^[0-9a-f]{64}$",
        "engagement manifestSha256 pattern drift",
    )

    checks = engagement_result["properties"]["checks"]
    _require(checks.get("type") == "array", "engagementResult.checks must be array")
    _require(checks.get("minItems") == 1, "engagementResult.checks.minItems drift")
    check = checks["items"]
    _strict_object(check, "engagementResult.checks[]")
    _require(_keys(check, "engagementResult.checks[]") == CHECK_KEYS, "engagement check property set drift")
    expected_check_required = {"invariantId", "status", "exploredCandidates", "notes"}
    _require(
        _required(check, "engagementResult.checks[]") == expected_check_required,
        "engagement check required set drift",
    )
    _non_blank_string(check["properties"]["invariantId"], "engagementResult.checks[].invariantId")
    status = check["properties"]["status"]
    _require(status.get("type") == "string", "engagement status must be string")
    _require(set(status.get("enum", [])) == STATUSES, "engagement status enum drift")
    finding_id = check["properties"]["findingId"]
    _require(finding_id.get("type") == "string", "engagement findingId must be string")
    _require(finding_id.get("minLength") == 1, "engagement findingId minLength drift")
    _require(finding_id.get("pattern") == SAFE_ARTIFACT_ID.pattern, "engagement findingId safe pattern drift")
    _require(
        check["properties"]["exploredCandidates"] == {"type": "integer", "minimum": 0},
        "engagement exploredCandidates schema drift",
    )
    _non_blank_string(check["properties"]["notes"], "engagementResult.checks[].notes")
    engagement_path = check["properties"]["path"]
    _require(engagement_path.get("type") == "array", "engagement path must be array")
    _require(engagement_path.get("minItems") == 1, "engagement path minItems drift")
    _step_contract(engagement_path["items"], "engagementResult.checks[].path[]")
    all_of = check.get("allOf")
    _require(isinstance(all_of, list) and len(all_of) == 1, "engagement status conditional drift")

    return {
        "ok": True,
        "manifestSchema": str(MANIFEST_SCHEMA.relative_to(ROOT)),
        "resultSchema": str(RESULT_SCHEMA.relative_to(ROOT)),
        "engagementResultSchema": str(ENGAGEMENT_RESULT_SCHEMA.relative_to(ROOT)),
        "severityValues": sorted(SEVERITIES),
        "engagementStatuses": sorted(STATUSES),
    }


def main() -> int:
    print(json.dumps(check_schema_contract(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
