"""Deterministic effective-validity checks over a normalized causal trace."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "cgqa/ancestral-validity/v0.1"


class AncestralValidityError(ValueError):
    """Raised when an ancestral-validity trace is malformed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AncestralValidityError(f"{name} must be an object")
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AncestralValidityError(f"{name} must be a non-empty string")
    return value


def _event_time(event: dict[str, Any]) -> int:
    value = event.get("occurredAt")
    if not isinstance(value, int) or isinstance(value, bool):
        raise AncestralValidityError(f"event {event.get('id')!r}.occurredAt must be an integer")
    return value


def validate_ancestral_trace(data: object) -> dict[str, Any]:
    trace = _object(data, "trace")
    if trace.get("schema") != SCHEMA:
        raise AncestralValidityError(f"schema must equal {SCHEMA!r}")
    subject = _object(trace.get("subject"), "subject")
    if not subject:
        raise AncestralValidityError("subject must not be empty")
    subject_hash = _sha256(subject)
    target_id = _text(trace.get("targetEventId"), "targetEventId")
    events = trace.get("events")
    if not isinstance(events, list) or not events:
        raise AncestralValidityError("events must be a non-empty list")

    seen: set[str] = set()
    for index, raw in enumerate(events):
        event = _object(raw, f"events[{index}]")
        event_id = _text(event.get("id"), f"events[{index}].id")
        if event_id in seen:
            raise AncestralValidityError(f"duplicate event id: {event_id}")
        seen.add(event_id)
        _text(event.get("kind"), f"events[{index}].kind")
        _text(event.get("actor"), f"events[{index}].actor")
        _event_time(event)
        local_valid = event.get("localValid", True)
        if not isinstance(local_valid, bool):
            raise AncestralValidityError(f"event {event_id!r}.localValid must be boolean")
        for key in (
            "parentId",
            "scope",
            "authorityRef",
            "evidenceParentId",
            "faultRef",
            "grantsTo",
            "subjectHash",
        ):
            if key in event and event[key] is not None:
                _text(event[key], f"event {event_id!r}.{key}")
        if event.get("subjectHash") is not None and event["subjectHash"] != subject_hash:
            raise AncestralValidityError(
                f"event {event_id!r}.subjectHash does not match the trace subject"
            )
        if "expiresAt" in event and event["expiresAt"] is not None:
            value = event["expiresAt"]
            if not isinstance(value, int) or isinstance(value, bool):
                raise AncestralValidityError(f"event {event_id!r}.expiresAt must be an integer")
        supersedes = event.get("supersedes", [])
        if not isinstance(supersedes, list) or not all(isinstance(v, str) and v for v in supersedes):
            raise AncestralValidityError(f"event {event_id!r}.supersedes must be a list of strings")
        if "requiresHandoff" in event and not isinstance(event["requiresHandoff"], bool):
            raise AncestralValidityError(f"event {event_id!r}.requiresHandoff must be boolean")

    if target_id not in seen:
        raise AncestralValidityError(f"targetEventId {target_id!r} is not present in events")
    return trace


def load_ancestral_trace(path: Path) -> dict[str, Any]:
    return validate_ancestral_trace(json.loads(path.read_text(encoding="utf-8")))


def _finding(
    code: str,
    message: str,
    refs: list[str],
    *,
    at_event_id: str | None = None,
) -> dict[str, object]:
    finding: dict[str, object] = {
        "code": code,
        "severity": "FAIL",
        "message": message,
        "refs": sorted(set(refs)),
    }
    if at_event_id is not None:
        finding["atEventId"] = at_event_id
    return finding


def _ancestry(
    target: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, object]]]:
    chain = [target]
    findings: list[dict[str, object]] = []
    seen = {target["id"]}
    cursor = target
    while cursor.get("parentId"):
        parent_id = cursor["parentId"]
        parent = by_id.get(parent_id)
        if parent is None:
            findings.append(
                _finding(
                    "ANCESTRY_GAP",
                    f"parent {parent_id!r} is missing from the trace",
                    [cursor["id"], parent_id],
                    at_event_id=cursor["id"],
                )
            )
            break
        if parent_id in seen:
            findings.append(
                _finding(
                    "ANCESTRY_CYCLE",
                    "causal ancestry contains a cycle",
                    list(seen) + [parent_id],
                    at_event_id=cursor["id"],
                )
            )
            break
        seen.add(parent_id)
        chain.append(parent)
        cursor = parent
    return chain, findings


def _finding_time(
    finding: dict[str, object],
    by_id: dict[str, dict[str, Any]],
    target_time: int,
) -> int:
    event_id = finding.get("atEventId")
    if isinstance(event_id, str) and event_id in by_id:
        return _event_time(by_id[event_id])
    return target_time


def run_ancestral_validity(trace: dict[str, Any]) -> dict[str, object]:
    validated = validate_ancestral_trace(trace)
    events = [dict(event) for event in validated["events"]]
    by_id = {event["id"]: event for event in events}
    target = by_id[validated["targetEventId"]]
    chain, findings = _ancestry(target, by_id)
    ancestor_ids = {event["id"] for event in chain}
    target_time = _event_time(target)
    target_scope = target.get("scope")

    if not target.get("localValid", True):
        findings.append(
            _finding(
                "LOCAL_INVALID",
                "target event is locally invalid",
                [target["id"]],
                at_event_id=target["id"],
            )
        )

    root = chain[-1]
    if not root.get("localValid", True):
        findings.append(
            _finding(
                "INVALID_ROOT_INHERITANCE",
                "target inherits from a locally invalid causal root",
                [root["id"], target["id"]],
                at_event_id=root["id"],
            )
        )

    for event in chain[1:]:
        event_scope = event.get("scope")
        if target_scope is not None and event_scope is not None and event_scope != target_scope:
            findings.append(
                _finding(
                    "FOREIGN_SCOPE_ANCESTOR",
                    "causal ancestor belongs to a different workflow scope",
                    [event["id"], target["id"]],
                    at_event_id=event["id"],
                )
            )
        if event.get("kind") != "APPROVAL":
            continue
        expired = event.get("expiresAt") is not None and int(event["expiresAt"]) < target_time
        scope_mismatch = (
            target_scope is not None
            and event_scope is not None
            and event_scope != target_scope
        )
        if expired or scope_mismatch:
            reason = "expired" if expired else "belongs to a different workflow scope"
            findings.append(
                _finding(
                    "STALE_PARENT",
                    f"approval ancestor is {reason} for the target action",
                    [event["id"], target["id"]],
                    at_event_id=event["id"],
                )
            )

    same_scope_events = [
        event
        for event in events
        if _event_time(event) <= target_time
        and (target_scope is None or event.get("scope") in (None, target_scope))
    ]
    for rejection in same_scope_events:
        if rejection.get("kind") != "REJECTION":
            continue
        superseded = set(rejection.get("supersedes", [])) & ancestor_ids
        if not superseded:
            continue
        fresh_approval = any(
            event.get("kind") == "APPROVAL"
            and _event_time(event) > _event_time(rejection)
            and event["id"] in ancestor_ids
            for event in same_scope_events
        )
        if not fresh_approval:
            findings.append(
                _finding(
                    "REJECTED_BRANCH_REUSE",
                    "target re-enters an ancestor branch superseded by rejection without fresh approval",
                    [rejection["id"], target["id"], *sorted(superseded)],
                    at_event_id=rejection["id"],
                )
            )

    if target.get("requiresHandoff", False):
        authority_ref = target.get("authorityRef")
        handoff = by_id.get(authority_ref) if authority_ref else None
        valid_handoff = bool(
            handoff
            and handoff.get("kind") == "HANDOFF"
            and handoff.get("grantsTo") == target.get("actor")
            and _event_time(handoff) <= target_time
            and (target_scope is None or handoff.get("scope") in (None, target_scope))
        )
        if not valid_handoff:
            refs = [target["id"]]
            if authority_ref:
                refs.append(authority_ref)
            findings.append(
                _finding(
                    "MISSING_AUTHORITY_HANDOFF",
                    "target requires an explicit authority handoff to its actor",
                    refs,
                    at_event_id=target["id"],
                )
            )

    for event in chain:
        if event.get("kind") != "MEMORY":
            continue
        evidence_parent = event.get("evidenceParentId")
        if not evidence_parent or evidence_parent not in by_id:
            refs = [event["id"], target["id"]]
            if evidence_parent:
                refs.append(evidence_parent)
            findings.append(
                _finding(
                    "MEMORY_WITHOUT_EVIDENCE_ORIGIN",
                    "memory-derived causal ancestor has no resolvable evidence origin",
                    refs,
                    at_event_id=event["id"],
                )
            )

    if target.get("kind") == "REMEDIATION":
        fault_ref = target.get("faultRef")
        fault = by_id.get(fault_ref) if fault_ref else None
        if not fault or fault.get("kind") != "FAULT":
            refs = [target["id"]]
            if fault_ref:
                refs.append(fault_ref)
            findings.append(
                _finding(
                    "REMEDIATION_WITHOUT_FAULT_LINK",
                    "remediation is not bound to a resolvable FAULT event",
                    refs,
                    at_event_id=target["id"],
                )
            )

    findings.sort(
        key=lambda row: (
            _finding_time(row, by_id, target_time),
            str(row["code"]),
            tuple(row["refs"]),
        )
    )
    effective = "invalid" if findings else "valid_within_trace"
    first_invalidity = findings[0] if findings else None
    affected_descendants: list[str] = []
    if first_invalidity is not None:
        first_time = _finding_time(first_invalidity, by_id, target_time)
        affected_descendants = [
            event["id"]
            for event in reversed(chain)
            if _event_time(event) >= first_time
        ]
        if target["id"] not in affected_descendants:
            affected_descendants.append(target["id"])

    subject_hash = _sha256(validated["subject"])
    explicit_subject_events = sum(
        1 for event in events if event.get("subjectHash") == subject_hash
    )
    return {
        "schema": "cgqa/ancestral-validity-result/v0.1",
        "status": "pass" if effective == "valid_within_trace" else "fail",
        "traceHash": _sha256(validated),
        "subjectHash": subject_hash,
        "subjectBinding": (
            "EXPLICIT_EVENT_BINDING"
            if explicit_subject_events == len(events)
            else "TRACE_LEVEL_BINDING"
        ),
        "targetEventId": target["id"],
        "localValidity": "valid" if target.get("localValid", True) else "invalid",
        "effectiveValidity": effective,
        "ancestry": [event["id"] for event in chain],
        "firstInvalidity": first_invalidity,
        "affectedDescendants": affected_descendants,
        "findings": findings,
        "securityVerdictAuthorized": False,
        "claimBoundary": (
            "Effective validity is derived only from the normalized trace fields supplied to this evaluator; "
            "it does not prove that the trace is complete or independently witnessed."
        ),
    }
