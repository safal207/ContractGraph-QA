"""Deterministic causal-context readiness evaluation for an Orientation Center."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "cgqa/orientation-center/v0.1"
READINESS_BALANCED = "BALANCED"
READINESS_INDETERMINATE = "INDETERMINATE"
READINESS_UNSTABLE = "UNSTABLE"


class OrientationCenterError(ValueError):
    """Raised when an orientation-center bundle is malformed."""


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
        raise OrientationCenterError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise OrientationCenterError(f"{name} must be a list")
    return value


def _status_item(value: object, name: str) -> dict[str, Any]:
    item = _object(value, name)
    if "id" not in item or not isinstance(item["id"], str) or not item["id"].strip():
        raise OrientationCenterError(f"{name}.id must be a non-empty string")
    if "status" not in item or not isinstance(item["status"], str) or not item["status"].strip():
        raise OrientationCenterError(f"{name}.status must be a non-empty string")
    return item


def validate_orientation_center(data: object) -> dict[str, Any]:
    bundle = _object(data, "bundle")
    if bundle.get("schema") != SCHEMA:
        raise OrientationCenterError(f"schema must equal {SCHEMA!r}")
    subject = _object(bundle.get("subject"), "subject")
    if not subject:
        raise OrientationCenterError("subject must not be empty")
    _object(bundle.get("state"), "state")
    ancestry = _object(bundle.get("ancestry"), "ancestry")
    authority = _object(bundle.get("authorityNow"), "authorityNow")
    for name, value in (("ancestry.status", ancestry.get("status")), ("authorityNow.status", authority.get("status"))):
        if not isinstance(value, str) or not value:
            raise OrientationCenterError(f"{name} must be a non-empty string")

    for field in (
        "supportingEvidence",
        "counterevidence",
        "verificationDebt",
        "independentWitnesses",
        "watchpoints",
    ):
        items = _list(bundle.get(field, []), field)
        for index, item in enumerate(items):
            _status_item(item, f"{field}[{index}]")

    requirements = _object(bundle.get("requirements", {}), "requirements")
    for key in (
        "requireSupportingEvidence",
        "requireIndependentWitness",
        "requireAncestry",
        "requireAuthority",
    ):
        if key in requirements and not isinstance(requirements[key], bool):
            raise OrientationCenterError(f"requirements.{key} must be boolean")
    return bundle


def load_orientation_center(path: Path) -> dict[str, Any]:
    return validate_orientation_center(json.loads(path.read_text(encoding="utf-8")))


def _reason(code: str, message: str, refs: list[str] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "refs": sorted(set(refs or []))}


def evaluate_orientation_center(bundle: dict[str, Any]) -> dict[str, object]:
    validated = validate_orientation_center(bundle)
    hard: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    requirements = validated.get("requirements", {})
    ancestry_status = str(validated["ancestry"]["status"]).upper()
    authority_status = str(validated["authorityNow"]["status"]).upper()

    if requirements.get("requireAncestry", True):
        if ancestry_status in {"INVALID", "FAIL", "UNSTABLE"}:
            hard.append(_reason("ANCESTRY_INVALID", "causal ancestry is invalid"))
        elif ancestry_status not in {"VALID", "VALID_WITHIN_TRACE", "PASS"}:
            unresolved.append(_reason("ANCESTRY_UNRESOLVED", "causal ancestry is not resolved"))

    if requirements.get("requireAuthority", True):
        if authority_status in {"INVALID", "FAIL", "REVOKED", "EXPIRED"}:
            hard.append(_reason("AUTHORITY_INVALID", "current authority is invalid, revoked, or expired"))
        elif authority_status not in {"VALID", "PASS", "CURRENT"}:
            unresolved.append(_reason("AUTHORITY_UNRESOLVED", "current authority is not resolved"))

    supporting = validated.get("supportingEvidence", [])
    supporting_valid = [item for item in supporting if str(item["status"]).upper() in {"VALID", "PASS", "WITNESSED"}]
    supporting_invalid = [item for item in supporting if str(item["status"]).upper() in {"INVALID", "FAIL"}]
    if supporting_invalid:
        hard.append(
            _reason(
                "SUPPORTING_EVIDENCE_INVALID",
                "declared supporting evidence contains an invalid item",
                [item["id"] for item in supporting_invalid],
            )
        )
    if requirements.get("requireSupportingEvidence", True) and not supporting_valid:
        unresolved.append(_reason("SUPPORTING_EVIDENCE_MISSING", "no valid supporting evidence is available"))

    counterevidence = validated.get("counterevidence", [])
    confirmed_counter = [item for item in counterevidence if str(item["status"]).upper() in {"CONFIRMED", "VALID", "FAIL"}]
    open_counter = [item for item in counterevidence if str(item["status"]).upper() in {"OPEN", "UNRESOLVED", "PENDING"}]
    if confirmed_counter:
        hard.append(
            _reason(
                "COUNTEREVIDENCE_CONFIRMED",
                "confirmed counterevidence contradicts the current orientation",
                [item["id"] for item in confirmed_counter],
            )
        )
    if open_counter:
        unresolved.append(
            _reason(
                "COUNTEREVIDENCE_UNRESOLVED",
                "counterevidence remains unresolved",
                [item["id"] for item in open_counter],
            )
        )

    debt = validated.get("verificationDebt", [])
    failed_debt = [
        item
        for item in debt
        if item.get("required", True)
        and str(item["status"]).upper() in {"COMPLETED_FAIL", "FAIL", "INVALID"}
    ]
    unresolved_debt = [
        item
        for item in debt
        if item.get("required", True)
        and str(item["status"]).upper()
        not in {"COMPLETED_PASS", "PASS", "NOT_APPLICABLE", "SKIPPED_WITH_REASON"}
        and item not in failed_debt
    ]
    if failed_debt:
        hard.append(
            _reason(
                "VERIFICATION_DEBT_FAILED",
                "required verification completed with a failing result",
                [item["id"] for item in failed_debt],
            )
        )
    if unresolved_debt:
        unresolved.append(
            _reason(
                "VERIFICATION_DEBT_UNRESOLVED",
                "required verification remains pending, deferred, blocked, or not run",
                [item["id"] for item in unresolved_debt],
            )
        )

    witnesses = validated.get("independentWitnesses", [])
    valid_witnesses = [item for item in witnesses if str(item["status"]).upper() in {"VALID", "PASS", "WITNESSED"}]
    invalid_witnesses = [item for item in witnesses if str(item["status"]).upper() in {"INVALID", "FAIL", "MISMATCH"}]
    if invalid_witnesses:
        hard.append(
            _reason(
                "INDEPENDENT_WITNESS_CONTRADICTION",
                "an independent witness contradicts the declared orientation",
                [item["id"] for item in invalid_witnesses],
            )
        )
    if requirements.get("requireIndependentWitness", False) and not valid_witnesses:
        unresolved.append(_reason("INDEPENDENT_WITNESS_MISSING", "a required independent witness is not available"))

    hard.sort(key=lambda row: str(row["code"]))
    unresolved.sort(key=lambda row: str(row["code"]))
    if hard:
        readiness = READINESS_UNSTABLE
    elif unresolved:
        readiness = READINESS_INDETERMINATE
    else:
        readiness = READINESS_BALANCED

    return {
        "schema": "cgqa/orientation-center-result/v0.1",
        "status": "pass" if readiness == READINESS_BALANCED else "hold",
        "readiness": readiness,
        "centerHash": _sha256(validated),
        "subjectHash": _sha256(validated["subject"]),
        "hardFindings": hard,
        "unresolved": unresolved,
        "watchpoints": list(validated.get("watchpoints", [])),
        "claimBoundary": (
            "Orientation readiness describes whether the declared causal context is resolved enough to proceed. "
            "BALANCED is not a truth, safety, or security verdict."
        ),
    }
