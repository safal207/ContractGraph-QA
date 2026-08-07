"""Manifest/result validation and deterministic ContractGraph-QA finding export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SEVERITIES = {"critical", "high", "medium", "low", "info"}
MANIFEST_KEYS = {
    "schemaVersion",
    "adapterId",
    "contract",
    "network",
    "scope",
    "search",
    "stateFields",
    "actions",
    "invariants",
}
SCOPE_KEYS = {"scopeId", "authorization", "authorizationReference", "target"}
SEARCH_KEYS = {"maxDepth"}
ACTION_KEYS = {"id", "display", "actor"}
INVARIANT_KEYS = {"id", "title", "severity", "summary", "expression", "impact", "recommendation"}
RESULT_KEYS = {
    "adapterId",
    "scopeId",
    "manifestSha256",
    "findingId",
    "invariantId",
    "replay",
    "exploredCandidates",
    "notes",
    "path",
}
STEP_KEYS = {"actionId", "parameter", "preState", "postState", "effect"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_non_empty_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _require_non_negative_int(value: Any, field: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{field} must be a non-negative integer",
    )
    return value


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _require(isinstance(data, dict), f"{label} must be a JSON object")
    return data


def manifest_sha256(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(manifest: dict[str, Any]) -> None:
    _reject_extra_keys(manifest, MANIFEST_KEYS, "manifest")
    _require(manifest.get("schemaVersion") == 1, "manifest.schemaVersion must equal 1")
    for field in ("adapterId", "contract", "network"):
        _require_non_empty_string(manifest.get(field), f"manifest.{field}")

    scope = manifest.get("scope")
    _require(isinstance(scope, dict), "manifest.scope must be an object")
    _reject_extra_keys(scope, SCOPE_KEYS, "manifest.scope")
    for field in ("scopeId", "authorization", "authorizationReference", "target"):
        _require_non_empty_string(scope.get(field), f"manifest.scope.{field}")

    search = manifest.get("search")
    _require(isinstance(search, dict), "manifest.search must be an object")
    _reject_extra_keys(search, SEARCH_KEYS, "manifest.search")
    _require_non_negative_int(search.get("maxDepth"), "manifest.search.maxDepth")
    _require(search["maxDepth"] > 0, "manifest.search.maxDepth must be greater than zero")

    state_fields = manifest.get("stateFields")
    _require(isinstance(state_fields, list) and state_fields, "manifest.stateFields must be non-empty")
    seen_state_fields: set[str] = set()
    for index, field in enumerate(state_fields):
        name = _require_non_empty_string(field, f"manifest.stateFields[{index}]")
        _require(name not in seen_state_fields, f"duplicate state field: {name}")
        seen_state_fields.add(name)

    actions = manifest.get("actions")
    _require(isinstance(actions, list) and actions, "manifest.actions must be non-empty")
    action_ids: set[str] = set()
    for index, action in enumerate(actions):
        _require(isinstance(action, dict), f"manifest.actions[{index}] must be an object")
        _reject_extra_keys(action, ACTION_KEYS, f"manifest.actions[{index}]")
        action_id = _require_non_empty_string(action.get("id"), f"manifest.actions[{index}].id")
        _require(action_id not in action_ids, f"duplicate action id: {action_id}")
        action_ids.add(action_id)
        _require_non_empty_string(action.get("display"), f"manifest.actions[{index}].display")
        _require_non_empty_string(action.get("actor"), f"manifest.actions[{index}].actor")

    invariants = manifest.get("invariants")
    _require(isinstance(invariants, list) and invariants, "manifest.invariants must be non-empty")
    invariant_ids: set[str] = set()
    for index, invariant in enumerate(invariants):
        _require(isinstance(invariant, dict), f"manifest.invariants[{index}] must be an object")
        _reject_extra_keys(invariant, INVARIANT_KEYS, f"manifest.invariants[{index}]")
        invariant_id = _require_non_empty_string(
            invariant.get("id"), f"manifest.invariants[{index}].id"
        )
        _require(invariant_id not in invariant_ids, f"duplicate invariant id: {invariant_id}")
        invariant_ids.add(invariant_id)
        for field in ("title", "summary", "expression", "impact", "recommendation"):
            _require_non_empty_string(
                invariant.get(field), f"manifest.invariants[{index}].{field}"
            )
        severity = _require_non_empty_string(
            invariant.get("severity"), f"manifest.invariants[{index}].severity"
        ).lower()
        _require(severity in SEVERITIES, f"invalid severity for invariant {invariant_id}")


def validate_result(result: dict[str, Any]) -> None:
    _reject_extra_keys(result, RESULT_KEYS, "result")
    for field in (
        "adapterId",
        "scopeId",
        "manifestSha256",
        "findingId",
        "invariantId",
        "replay",
    ):
        _require_non_empty_string(result.get(field), f"result.{field}")

    fingerprint = result["manifestSha256"]
    _require(
        len(fingerprint) == 64 and all(char in "0123456789abcdef" for char in fingerprint),
        "result.manifestSha256 must be a lowercase SHA-256 hex digest",
    )

    if "exploredCandidates" in result:
        _require_non_negative_int(result["exploredCandidates"], "result.exploredCandidates")
    if "notes" in result:
        _require_non_empty_string(result["notes"], "result.notes")

    path = result.get("path")
    _require(isinstance(path, list) and path, "result.path must be non-empty")
    for index, step in enumerate(path):
        _require(isinstance(step, dict), f"result.path[{index}] must be an object")
        _reject_extra_keys(step, STEP_KEYS, f"result.path[{index}]")
        _require_non_empty_string(step.get("actionId"), f"result.path[{index}].actionId")
        for field in ("preState", "postState", "effect"):
            _require_non_empty_string(step.get(field), f"result.path[{index}].{field}")
        if "parameter" in step:
            parameter = step["parameter"]
            _require(
                isinstance(parameter, (str, int)) and not isinstance(parameter, bool),
                f"result.path[{index}].parameter must be a string or integer",
            )


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _render_action(action: dict[str, Any], step: dict[str, Any], index: int) -> str:
    display = action["display"]
    has_placeholder = "{parameter}" in display
    has_parameter = "parameter" in step
    if has_placeholder:
        _require(has_parameter, f"result.path[{index}].parameter required by action display")
        return display.replace("{parameter}", str(step["parameter"]))
    _require(not has_parameter, f"result.path[{index}].parameter supplied but action has no placeholder")
    return display


def export_finding(manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    validate_result(result)

    _require(result["adapterId"] == manifest["adapterId"], "result.adapterId does not match manifest")
    _require(result["scopeId"] == manifest["scope"]["scopeId"], "result.scopeId does not match manifest")
    _require(
        result["manifestSha256"] == manifest_sha256(manifest),
        "result.manifestSha256 does not match manifest",
    )
    _require(
        len(result["path"]) <= manifest["search"]["maxDepth"],
        "result.path exceeds manifest.search.maxDepth",
    )

    actions = _index_by_id(manifest["actions"])
    invariants = _index_by_id(manifest["invariants"])

    invariant_id = result["invariantId"]
    _require(invariant_id in invariants, f"unknown invariant id: {invariant_id}")
    invariant = invariants[invariant_id]

    exported_path: list[dict[str, Any]] = []
    for index, step in enumerate(result["path"], start=1):
        action_id = step["actionId"]
        _require(action_id in actions, f"unknown action id: {action_id}")
        action = actions[action_id]
        exported_path.append(
            {
                "step": index,
                "actor": action["actor"],
                "action": _render_action(action, step, index - 1),
                "preState": step["preState"],
                "postState": step["postState"],
                "effect": step["effect"],
            }
        )

    scope = manifest["scope"]
    evidence: dict[str, Any] = {
        "authorization": scope["authorization"],
        "replay": result["replay"],
        "adapterId": manifest["adapterId"],
        "scopeId": scope["scopeId"],
        "authorizationReference": scope["authorizationReference"],
        "target": scope["target"],
        "manifestSha256": result["manifestSha256"],
        "notes": result.get(
            "notes",
            "Finding exported deterministically from a validated adapter manifest and explorer result.",
        ),
    }
    if "exploredCandidates" in result:
        evidence["exploredCandidates"] = result["exploredCandidates"]

    return {
        "id": result["findingId"],
        "title": invariant["title"],
        "severity": invariant["severity"].lower(),
        "contract": manifest["contract"],
        "network": manifest["network"],
        "summary": invariant["summary"],
        "invariant": {"id": invariant["id"], "expression": invariant["expression"]},
        "minimalFailingPath": exported_path,
        "impact": invariant["impact"],
        "recommendation": invariant["recommendation"],
        "evidence": evidence,
    }


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
