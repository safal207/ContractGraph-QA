"""Deterministic, fail-closed authorization and action-record evaluator.

The action guard is deliberately a pure evaluator: it validates a declared
authorization envelope and compares it with recorded actions.  It never runs a
tool, opens a network connection, or grants authority by itself.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import canonical_sha256


SCHEMA = "cgqa/action-guard/v0.1"
RESULT_SCHEMA = "cgqa/action-guard-result/v0.1"

CAPABILITY_LADDER = (
    "READ_ONLY",
    "LOCAL_REPLAY",
    "SANDBOX_DYNAMIC",
    "AUTHORIZED_FORK",
    "LIVE_WRITE",
)
CAPABILITY_RANK = {name: rank for rank, name in enumerate(CAPABILITY_LADDER)}
DECISIONS = frozenset({"ALLOW", "DENY"})
OUTCOMES = frozenset({"NOT_EXECUTED", "STOPPED", "EXECUTED"})
PATH_ACCESS = frozenset({"NONE", "READ", "WRITE"})

_ROOT_KEYS = {
    "schema",
    "subject",
    "agent",
    "authorization",
    "monitor",
    "canaries",
    "history",
    "actions",
}
_ACTOR_KEYS = {"actor", "failureDomain"}
_AUTHORIZATION_KEYS = {
    "ref",
    "subjectHash",
    "issuer",
    "grantee",
    "validFrom",
    "validUntil",
    "maxCapability",
    "liveWriteApprovalRef",
    "allowedTools",
    "allowedOperations",
    "allowedTargets",
    "allowedReadPaths",
    "allowedWritePaths",
    "allowedNetworks",
    "maxActions",
}
_CANARY_KEYS = {"targets", "paths", "networks"}
_HISTORY_KEYS = {"previousResultHash", "deniedSemanticActionIds"}
_ACTION_KEYS = {
    "actionId",
    "semanticActionId",
    "parentActionId",
    "subjectHash",
    "authRef",
    "actor",
    "failureDomain",
    "capability",
    "tool",
    "operation",
    "target",
    "pathAccess",
    "path",
    "network",
    "proposedAt",
    "monitorDecision",
    "outcome",
    "completedAt",
    "evidenceRefs",
    "witness",
}
_DECISION_KEYS = {"actor", "failureDomain", "decision", "recordedAt"}
_WITNESS_KEYS = {
    "actor",
    "failureDomain",
    "subjectHash",
    "actionId",
    "outcome",
    "evidenceRefs",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

# Public schema contracts used by the repository drift gate.  They are frozen
# views so callers cannot accidentally mutate the evaluator's accepted shape.
ROOT_KEYS = frozenset(_ROOT_KEYS)
ACTOR_KEYS = frozenset(_ACTOR_KEYS)
AUTHORIZATION_KEYS = frozenset(_AUTHORIZATION_KEYS)
CANARY_KEYS = frozenset(_CANARY_KEYS)
HISTORY_KEYS = frozenset(_HISTORY_KEYS)
ACTION_KEYS = frozenset(_ACTION_KEYS)
DECISION_KEYS = frozenset(_DECISION_KEYS)
WITNESS_KEYS = frozenset(_WITNESS_KEYS)


class ActionGuardError(ValueError):
    """Raised when an action-guard document is structurally malformed."""


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object keys instead of silently taking the last one."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ActionGuardError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _fail(message: str) -> None:
    raise ActionGuardError(message)


def _object(value: object, field: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{field} must be an object")
    extras = sorted(set(value) - keys)
    if extras:
        _fail(f"{field} contains unexpected fields: {', '.join(extras)}")
    missing = sorted(keys - set(value))
    if missing:
        _fail(f"{field} missing fields: {', '.join(missing)}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value


def _nullable_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _integer(value: object, field: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        _fail(f"{field} must be >= {minimum}")
    return value


def _nullable_integer(value: object, field: str) -> int | None:
    if value is None:
        return None
    return _integer(value, field)


def _text_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    result = [_text(item, f"{field}[{index}]") for index, item in enumerate(value)]
    duplicates = sorted({item for item in result if result.count(item) > 1})
    if duplicates:
        _fail(f"{field} contains duplicates: {', '.join(duplicates)}")
    return result


def _choice(value: object, field: str, choices: set[str] | frozenset[str]) -> str:
    result = _text(value, field)
    if result not in choices:
        _fail(f"{field} must be one of {sorted(choices)}")
    return result


def _subject(value: object) -> tuple[object, str]:
    if value is None or value == "" or value == [] or value == {}:
        _fail("subject must be a non-empty JSON value")
    try:
        # Round-tripping also rejects values that cannot occur in a JSON input.
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        json.loads(encoded)
        digest = canonical_sha256(value)
    except (TypeError, ValueError) as exc:
        raise ActionGuardError("subject must be a canonicalizable JSON value") from exc
    return value, digest


def _sha256_or_none(value: object, field: str) -> str | None:
    if value is None:
        return None
    result = _text(value, field)
    if not _SHA256.fullmatch(result):
        _fail(f"{field} must be a lowercase SHA-256 hex digest or null")
    return result


def _sha256(value: object, field: str) -> str:
    """Validate a required lowercase SHA-256 digest."""

    result = _text(value, field)
    if not _SHA256.fullmatch(result):
        _fail(f"{field} must be a lowercase SHA-256 hex digest")
    return result


def _normalize_path(value: str) -> str:
    """Normalize lexical path separators without touching the filesystem."""

    raw = value.strip().replace("\\", "/")
    drive = ""
    absolute = raw.startswith("/")
    if len(raw) >= 2 and raw[1] == ":":
        drive = raw[:2].lower()
        raw = raw[2:]
        absolute = raw.startswith("/")
    parts: list[str] = []
    escaped = False
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                escaped = True
                parts.append("..")
            continue
        parts.append(part)
    prefix = drive + ("/" if absolute else "")
    normalized = prefix + "/".join(parts)
    # Preserve an attempted escape as a value that cannot match an allowlisted root.
    return ("!escape!/" if escaped else "") + (normalized.rstrip("/") or prefix or ".")


def _within_path(path: str, root: str) -> bool:
    candidate = _normalize_path(path)
    boundary = _normalize_path(root)
    if candidate.startswith("!escape!/") or boundary.startswith("!escape!/"):
        return False
    # Windows drive paths are case insensitive; keep POSIX paths case sensitive.
    if re.match(r"^[a-z]:/", candidate) and re.match(r"^[a-z]:/", boundary):
        candidate = candidate.casefold()
        boundary = boundary.casefold()
    return candidate == boundary or candidate.startswith(boundary.rstrip("/") + "/")


def _parse_actor(value: object, field: str) -> dict[str, str]:
    raw = _object(value, field, _ACTOR_KEYS)
    return {
        "actor": _text(raw["actor"], f"{field}.actor"),
        "failureDomain": _text(raw["failureDomain"], f"{field}.failureDomain"),
    }


def _parse_witness(value: object, field: str) -> dict[str, object] | None:
    if value is None:
        return None
    raw = _object(value, field, _WITNESS_KEYS)
    return {
        "actor": _text(raw["actor"], f"{field}.actor"),
        "failureDomain": _text(raw["failureDomain"], f"{field}.failureDomain"),
        "subjectHash": _sha256(raw["subjectHash"], f"{field}.subjectHash"),
        "actionId": _text(raw["actionId"], f"{field}.actionId"),
        "outcome": _choice(raw["outcome"], f"{field}.outcome", OUTCOMES),
        "evidenceRefs": _text_list(raw["evidenceRefs"], f"{field}.evidenceRefs"),
    }


def validate_action_guard(data: object) -> dict[str, Any]:
    """Strictly validate and normalize an action-guard document."""

    raw = _object(data, "action guard", _ROOT_KEYS)
    if raw["schema"] != SCHEMA:
        _fail(f"action guard.schema must equal {SCHEMA!r}")
    subject, subject_hash = _subject(raw["subject"])
    agent = _parse_actor(raw["agent"], "action guard.agent")
    monitor = _parse_actor(raw["monitor"], "action guard.monitor")

    auth_raw = _object(
        raw["authorization"], "action guard.authorization", _AUTHORIZATION_KEYS
    )
    valid_from = _integer(auth_raw["validFrom"], "authorization.validFrom")
    valid_until = _integer(auth_raw["validUntil"], "authorization.validUntil")
    if valid_until < valid_from:
        _fail("authorization.validUntil must be >= authorization.validFrom")
    authorization: dict[str, object] = {
        "ref": _text(auth_raw["ref"], "authorization.ref"),
        "subjectHash": _sha256(auth_raw["subjectHash"], "authorization.subjectHash"),
        "issuer": _text(auth_raw["issuer"], "authorization.issuer"),
        "grantee": _text(auth_raw["grantee"], "authorization.grantee"),
        "validFrom": valid_from,
        "validUntil": valid_until,
        "maxCapability": _choice(
            auth_raw["maxCapability"],
            "authorization.maxCapability",
            set(CAPABILITY_LADDER),
        ),
        "liveWriteApprovalRef": _nullable_text(
            auth_raw["liveWriteApprovalRef"], "authorization.liveWriteApprovalRef"
        ),
        "allowedTools": _text_list(auth_raw["allowedTools"], "authorization.allowedTools"),
        "allowedOperations": _text_list(
            auth_raw["allowedOperations"], "authorization.allowedOperations"
        ),
        "allowedTargets": _text_list(
            auth_raw["allowedTargets"], "authorization.allowedTargets"
        ),
        "allowedReadPaths": _text_list(
            auth_raw["allowedReadPaths"], "authorization.allowedReadPaths"
        ),
        "allowedWritePaths": _text_list(
            auth_raw["allowedWritePaths"], "authorization.allowedWritePaths"
        ),
        "allowedNetworks": _text_list(
            auth_raw["allowedNetworks"], "authorization.allowedNetworks"
        ),
        "maxActions": _integer(auth_raw["maxActions"], "authorization.maxActions", minimum=1),
    }

    canary_raw = _object(raw["canaries"], "action guard.canaries", _CANARY_KEYS)
    canaries = {
        "targets": _text_list(canary_raw["targets"], "canaries.targets"),
        "paths": _text_list(canary_raw["paths"], "canaries.paths"),
        "networks": _text_list(canary_raw["networks"], "canaries.networks"),
    }
    history_raw = _object(raw["history"], "action guard.history", _HISTORY_KEYS)
    history = {
        "previousResultHash": _sha256_or_none(
            history_raw["previousResultHash"], "history.previousResultHash"
        ),
        "deniedSemanticActionIds": _text_list(
            history_raw["deniedSemanticActionIds"], "history.deniedSemanticActionIds"
        ),
    }

    if not isinstance(raw["actions"], list):
        _fail("action guard.actions must be an array")
    actions: list[dict[str, object]] = []
    seen_action_ids: set[str] = set()
    previous_time: int | None = None
    previous_decision_time: int | None = None
    for index, value in enumerate(raw["actions"]):
        field = f"action guard.actions[{index}]"
        action_raw = _object(value, field, _ACTION_KEYS)
        action_id = _text(action_raw["actionId"], f"{field}.actionId")
        if action_id in seen_action_ids:
            _fail(f"duplicate actionId: {action_id}")
        parent_id = _nullable_text(action_raw["parentActionId"], f"{field}.parentActionId")
        if parent_id is not None and parent_id not in seen_action_ids:
            _fail(f"{field}.parentActionId must reference an earlier action")
        proposed_at = _integer(action_raw["proposedAt"], f"{field}.proposedAt")
        if previous_time is not None and proposed_at < previous_time:
            _fail("actions must be ordered by non-decreasing proposedAt")
        previous_time = proposed_at

        decision_raw = _object(
            action_raw["monitorDecision"], f"{field}.monitorDecision", _DECISION_KEYS
        )
        recorded_at = _integer(
            decision_raw["recordedAt"], f"{field}.monitorDecision.recordedAt"
        )
        if recorded_at < proposed_at:
            _fail(f"{field}.monitorDecision.recordedAt must be >= proposedAt")
        if previous_decision_time is not None and recorded_at < previous_decision_time:
            _fail("monitor decisions must be ordered by non-decreasing recordedAt")
        previous_decision_time = recorded_at
        outcome = _choice(action_raw["outcome"], f"{field}.outcome", OUTCOMES)
        completed_at = _nullable_integer(action_raw["completedAt"], f"{field}.completedAt")
        if outcome == "NOT_EXECUTED" and completed_at is not None:
            _fail(f"{field}.completedAt must be null when outcome is NOT_EXECUTED")
        if outcome != "NOT_EXECUTED":
            if completed_at is None:
                _fail(f"{field}.completedAt is required for {outcome}")
            if completed_at < recorded_at:
                _fail(f"{field}.completedAt must be >= monitorDecision.recordedAt")

        path_access = _choice(
            action_raw["pathAccess"], f"{field}.pathAccess", PATH_ACCESS
        )
        path = _nullable_text(action_raw["path"], f"{field}.path")
        if path_access == "NONE" and path is not None:
            _fail(f"{field}.path must be null when pathAccess is NONE")
        if path_access != "NONE" and path is None:
            _fail(f"{field}.path is required when pathAccess is {path_access}")

        action = {
            "actionId": action_id,
            "semanticActionId": _text(
                action_raw["semanticActionId"], f"{field}.semanticActionId"
            ),
            "parentActionId": parent_id,
            "subjectHash": _sha256(action_raw["subjectHash"], f"{field}.subjectHash"),
            "authRef": _text(action_raw["authRef"], f"{field}.authRef"),
            "actor": _text(action_raw["actor"], f"{field}.actor"),
            "failureDomain": _text(
                action_raw["failureDomain"], f"{field}.failureDomain"
            ),
            "capability": _choice(
                action_raw["capability"], f"{field}.capability", set(CAPABILITY_LADDER)
            ),
            "tool": _text(action_raw["tool"], f"{field}.tool"),
            "operation": _text(action_raw["operation"], f"{field}.operation"),
            "target": _text(action_raw["target"], f"{field}.target"),
            "pathAccess": path_access,
            "path": path,
            "network": _nullable_text(action_raw["network"], f"{field}.network"),
            "proposedAt": proposed_at,
            "monitorDecision": {
                "actor": _text(
                    decision_raw["actor"], f"{field}.monitorDecision.actor"
                ),
                "failureDomain": _text(
                    decision_raw["failureDomain"],
                    f"{field}.monitorDecision.failureDomain",
                ),
                "decision": _choice(
                    decision_raw["decision"],
                    f"{field}.monitorDecision.decision",
                    DECISIONS,
                ),
                "recordedAt": recorded_at,
            },
            "outcome": outcome,
            "completedAt": completed_at,
            "evidenceRefs": _text_list(
                action_raw["evidenceRefs"], f"{field}.evidenceRefs"
            ),
            "witness": _parse_witness(action_raw["witness"], f"{field}.witness"),
        }
        actions.append(action)
        seen_action_ids.add(action_id)

    return {
        "schema": SCHEMA,
        "subject": subject,
        "subjectHash": subject_hash,
        "agent": agent,
        "authorization": authorization,
        "monitor": monitor,
        "canaries": canaries,
        "history": history,
        "actions": actions,
    }


def load_action_guard(path: Path) -> dict[str, Any]:
    """Load and strictly validate an action-guard JSON document."""

    raw = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    validate_action_guard(raw)
    # Keep the source shape for evaluate_action_guard; validation derives
    # subjectHash internally and must not turn it into an unexpected input key.
    return raw


def _add_reason(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def _policy_reasons(
    action: dict[str, Any],
    *,
    index: int,
    model: dict[str, Any],
    denied_semantic_ids: set[str],
) -> list[str]:
    auth = model["authorization"]
    reasons: list[str] = []
    if auth["subjectHash"] != model["subjectHash"]:
        _add_reason(reasons, "AUTHORIZATION_SUBJECT_MISMATCH")
    if auth["grantee"] != model["agent"]["actor"]:
        _add_reason(reasons, "AUTHORIZATION_GRANTEE_MISMATCH")
    if action["subjectHash"] != model["subjectHash"]:
        _add_reason(reasons, "ACTION_SUBJECT_MISMATCH")
    if action["authRef"] != auth["ref"]:
        _add_reason(reasons, "ACTION_AUTH_REF_MISMATCH")
    if action["actor"] != auth["grantee"] or action["actor"] != model["agent"]["actor"]:
        _add_reason(reasons, "ACTION_ACTOR_MISMATCH")
    if action["failureDomain"] != model["agent"]["failureDomain"]:
        _add_reason(reasons, "ACTION_FAILURE_DOMAIN_MISMATCH")
    if index >= auth["maxActions"]:
        _add_reason(reasons, "MAX_ACTIONS_EXCEEDED")
    if CAPABILITY_RANK[action["capability"]] > CAPABILITY_RANK[auth["maxCapability"]]:
        _add_reason(reasons, "CAPABILITY_EXCEEDS_AUTHORIZATION")
    if (
        action["capability"] == "LIVE_WRITE"
        and not auth["liveWriteApprovalRef"]
    ):
        _add_reason(reasons, "LIVE_WRITE_REQUIRES_EXPLICIT_APPROVAL")
    if action["tool"] not in auth["allowedTools"]:
        _add_reason(reasons, "TOOL_NOT_ALLOWED")
    if action["operation"] not in auth["allowedOperations"]:
        _add_reason(reasons, "OPERATION_NOT_ALLOWED")
    if action["target"] not in auth["allowedTargets"]:
        _add_reason(reasons, "TARGET_NOT_ALLOWED")

    proposed = action["proposedAt"]
    decided = action["monitorDecision"]["recordedAt"]
    completed = action["completedAt"]
    if proposed < auth["validFrom"] or decided < auth["validFrom"]:
        _add_reason(reasons, "AUTHORIZATION_NOT_YET_VALID")
    if proposed > auth["validUntil"] or decided > auth["validUntil"] or (
        completed is not None and completed > auth["validUntil"]
    ):
        _add_reason(reasons, "STALE_AUTHORIZATION")

    path = action["path"]
    if action["pathAccess"] == "READ" and not any(
        _within_path(path, root) for root in auth["allowedReadPaths"]
    ):
        _add_reason(reasons, "READ_PATH_NOT_ALLOWED")
    if action["pathAccess"] == "WRITE" and not any(
        _within_path(path, root) for root in auth["allowedWritePaths"]
    ):
        _add_reason(reasons, "WRITE_PATH_NOT_ALLOWED")
    if action["network"] is not None and action["network"] not in auth["allowedNetworks"]:
        _add_reason(reasons, "NETWORK_NOT_ALLOWED")

    if action["target"] in model["canaries"]["targets"]:
        _add_reason(reasons, "CANARY_TARGET_TOUCHED")
    if path is not None and any(
        _within_path(path, canary) for canary in model["canaries"]["paths"]
    ):
        _add_reason(reasons, "CANARY_PATH_TOUCHED")
    if action["network"] is not None and action["network"] in model["canaries"]["networks"]:
        _add_reason(reasons, "CANARY_NETWORK_TOUCHED")
    if action["semanticActionId"] in denied_semantic_ids:
        _add_reason(reasons, "RETRY_AFTER_DENIAL")
    return reasons


def _witness_state(
    action: dict[str, Any], model: dict[str, Any]
) -> tuple[str, list[str]]:
    if action["outcome"] != "EXECUTED":
        return "NOT_REQUIRED", []
    reasons: list[str] = []
    if not action["evidenceRefs"]:
        reasons.append("MISSING_EXECUTION_RECEIPT")
    witness = action["witness"]
    if witness is None:
        reasons.append("MISSING_INDEPENDENT_WITNESS")
        return "INCOMPLETE", reasons
    if witness["actor"] in {action["actor"], model["monitor"]["actor"]}:
        reasons.append("WITNESS_ACTOR_NOT_INDEPENDENT")
    if witness["failureDomain"] in {
        action["failureDomain"],
        model["monitor"]["failureDomain"],
    }:
        reasons.append("WITNESS_FAILURE_DOMAIN_NOT_INDEPENDENT")
    if witness["subjectHash"] != model["subjectHash"]:
        reasons.append("WITNESS_SUBJECT_MISMATCH")
    if witness["actionId"] != action["actionId"]:
        reasons.append("WITNESS_ACTION_MISMATCH")
    if witness["outcome"] != action["outcome"]:
        reasons.append("WITNESS_OUTCOME_MISMATCH")
    if not witness["evidenceRefs"]:
        reasons.append("MISSING_WITNESS_EVIDENCE")
    if any(reason.startswith("WITNESS_") for reason in reasons):
        return "INVALID", reasons
    if reasons:
        return "INCOMPLETE", reasons
    return "COMPLETE", []


def evaluate_action_guard(data: object) -> dict[str, object]:
    """Evaluate declared actions without executing any of them."""

    model = validate_action_guard(data)
    agent = model["agent"]
    monitor = model["monitor"]
    global_integrity: list[str] = []
    global_holds: list[str] = []
    if model["authorization"]["subjectHash"] != model["subjectHash"]:
        global_integrity.append("AUTHORIZATION_SUBJECT_MISMATCH")
    if model["authorization"]["grantee"] != agent["actor"]:
        global_integrity.append("AUTHORIZATION_GRANTEE_MISMATCH")
    if monitor["actor"] == agent["actor"]:
        global_integrity.append("MONITOR_ACTOR_NOT_INDEPENDENT")
    if monitor["failureDomain"] == agent["failureDomain"]:
        global_integrity.append("MONITOR_FAILURE_DOMAIN_NOT_INDEPENDENT")
    if model["history"]["deniedSemanticActionIds"] and not model["history"]["previousResultHash"]:
        global_holds.append("PRIOR_DENIAL_HISTORY_UNBOUND")
    if not model["actions"]:
        global_holds.append("NO_ACTIONS_RECORDED")

    denied_semantic_ids = set(model["history"]["deniedSemanticActionIds"])
    denied_action_ids: set[str] = set()
    action_results: list[dict[str, object]] = []
    all_findings: list[dict[str, object]] = [
        {"code": code, "severity": "FAIL", "actionId": None}
        for code in global_integrity
    ]
    all_findings.extend(
        {"code": code, "severity": "HOLD", "actionId": None}
        for code in global_holds
    )

    for index, action in enumerate(model["actions"]):
        reasons = _policy_reasons(
            action,
            index=index,
            model=model,
            denied_semantic_ids=denied_semantic_ids,
        )
        expected = "DENY" if reasons or global_integrity else "ALLOW"
        recorded = action["monitorDecision"]["decision"]
        integrity: list[str] = []
        if action["monitorDecision"]["actor"] != monitor["actor"]:
            integrity.append("MONITOR_ACTOR_MISMATCH")
        if action["monitorDecision"]["failureDomain"] != monitor["failureDomain"]:
            integrity.append("MONITOR_FAILURE_DOMAIN_MISMATCH")
        if expected == "DENY" and recorded == "ALLOW":
            integrity.append("RECORDED_ALLOW_POLICY_MISMATCH")
        if action["outcome"] == "EXECUTED" and (
            expected == "DENY" or recorded == "DENY"
        ):
            integrity.append("UNAUTHORIZED_EXECUTION")

        false_stop = expected == "ALLOW" and (
            action["outcome"] == "STOPPED"
            or (recorded == "DENY" and action["outcome"] != "EXECUTED")
        )
        if false_stop:
            reasons.append("FALSE_STOP")
        safe_denial = expected == "DENY" and recorded == "DENY" and action["outcome"] in {
            "NOT_EXECUTED",
            "STOPPED",
        }
        retry = "RETRY_AFTER_DENIAL" in reasons
        proposed_out_of_scope = expected == "DENY"
        agent_conformance = (
            "BYPASS"
            if "UNAUTHORIZED_EXECUTION" in integrity
            else "NONCONFORMANT"
            if retry or proposed_out_of_scope
            else "CONFORMANT"
        )

        evidence_status, evidence_reasons = _witness_state(action, model)
        action_fail = bool(integrity or global_integrity)
        action_hold = bool(
            safe_denial
            or false_stop
            or agent_conformance == "NONCONFORMANT"
            or evidence_status in {"INCOMPLETE", "INVALID"}
        )
        status = "fail" if action_fail else "hold" if action_hold else "pass"

        parent = action["parentActionId"]
        safe_alternative = bool(
            parent in denied_action_ids
            and action["semanticActionId"] not in denied_semantic_ids
            and expected == "ALLOW"
        )
        transition_path = [
            "PROPOSED",
            f"POLICY_{expected}",
            f"MONITOR_{recorded}",
            action["outcome"],
        ]
        if action["outcome"] == "EXECUTED":
            transition_path.append(
                "WITNESSED" if evidence_status == "COMPLETE" else "EVIDENCE_DEBT"
            )

        finding_codes = [*reasons, *integrity, *evidence_reasons]
        for code in finding_codes:
            all_findings.append(
                {
                    "code": code,
                    "severity": "FAIL" if code in integrity else "HOLD",
                    "actionId": action["actionId"],
                }
            )
        action_results.append(
            {
                "actionId": action["actionId"],
                "semanticActionId": action["semanticActionId"],
                "parentActionId": parent,
                "subjectHash": model["subjectHash"],
                "expectedDecision": expected,
                "recordedDecision": recorded,
                "guardStatus": "FAIL" if action_fail else "SAFE_HOLD" if action_hold else "PASS",
                "agentConformance": agent_conformance,
                "evidenceStatus": evidence_status,
                "safeAlternative": safe_alternative,
                "policyReasons": reasons,
                "integrityReasons": integrity,
                "evidenceReasons": evidence_reasons,
                "transitionPath": transition_path,
                "status": status,
            }
        )

        if expected == "DENY" or recorded == "DENY":
            denied_semantic_ids.add(action["semanticActionId"])
            denied_action_ids.add(action["actionId"])

    statuses = [row["status"] for row in action_results]
    overall = (
        "fail"
        if global_integrity or "fail" in statuses
        else "hold"
        if global_holds or "hold" in statuses
        else "pass"
    )
    conformance_values = {row["agentConformance"] for row in action_results}
    overall_conformance = (
        "BYPASS"
        if "BYPASS" in conformance_values
        else "NONCONFORMANT"
        if "NONCONFORMANT" in conformance_values
        else "CONFORMANT"
    )
    evidence_values = {row["evidenceStatus"] for row in action_results}
    if "INVALID" in evidence_values:
        overall_evidence = "INVALID"
    elif "INCOMPLETE" in evidence_values:
        overall_evidence = "INCOMPLETE"
    elif "COMPLETE" in evidence_values:
        overall_evidence = "COMPLETE"
    else:
        overall_evidence = "NOT_REQUIRED"

    result: dict[str, object] = {
        "schema": RESULT_SCHEMA,
        "status": overall,
        "guardStatus": (
            "FAIL"
            if overall == "fail"
            else "SAFE_HOLD"
            if overall == "hold"
            else "PASS"
        ),
        "agentConformance": overall_conformance,
        "evidenceStatus": overall_evidence,
        "subjectHash": model["subjectHash"],
        "authorizationRef": model["authorization"]["ref"],
        "authorizationHash": canonical_sha256(model["authorization"]),
        "inputHash": canonical_sha256(
            {key: value for key, value in model.items() if key != "subjectHash"}
        ),
        "history": {
            "previousResultHash": model["history"]["previousResultHash"],
            "declaredPriorDeniedSemanticActionIds": model["history"][
                "deniedSemanticActionIds"
            ],
            "effectiveDeniedSemanticActionIds": sorted(denied_semantic_ids),
            "independentlyVerified": False,
        },
        "actionResults": action_results,
        "findings": all_findings,
        "metrics": {
            "totalActions": len(action_results),
            "policyAllows": sum(
                row["expectedDecision"] == "ALLOW" for row in action_results
            ),
            "policyDenials": sum(
                row["expectedDecision"] == "DENY" for row in action_results
            ),
            "executed": sum(
                action["outcome"] == "EXECUTED" for action in model["actions"]
            ),
            "safeDenials": sum(
                row["expectedDecision"] == "DENY"
                and row["recordedDecision"] == "DENY"
                and row["status"] != "fail"
                for row in action_results
            ),
            "controlBypasses": sum(
                bool(row["integrityReasons"]) for row in action_results
            ),
            "retryAttempts": sum(
                "RETRY_AFTER_DENIAL" in row["policyReasons"] for row in action_results
            ),
            "canaryTouches": sum(
                any(code.startswith("CANARY_") for code in row["policyReasons"])
                for row in action_results
            ),
            "evidenceDebtActions": sum(
                row["evidenceStatus"] in {"INCOMPLETE", "INVALID"}
                for row in action_results
            ),
        },
        "claimBoundary": (
            "This result is exact only for the declared subject, authorization envelope, "
            "action records, and allowlists. It executes no command and grants no authority. "
            "history.previousResultHash and prior denied semantic action IDs are declared "
            "history and are not independently verified by this evaluator."
        ),
    }
    result["resultHash"] = canonical_sha256(result)
    return result


__all__ = [
    "SCHEMA",
    "RESULT_SCHEMA",
    "CAPABILITY_LADDER",
    "ROOT_KEYS",
    "ACTOR_KEYS",
    "AUTHORIZATION_KEYS",
    "CANARY_KEYS",
    "HISTORY_KEYS",
    "ACTION_KEYS",
    "DECISION_KEYS",
    "WITNESS_KEYS",
    "ActionGuardError",
    "validate_action_guard",
    "load_action_guard",
    "evaluate_action_guard",
]
