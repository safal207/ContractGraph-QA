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


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrientationCenterError(f"{name} must be a non-empty string")
    return value


def _status_item(value: object, name: str) -> dict[str, Any]:
    item = _object(value, name)
    _text(item.get("id"), f"{name}.id")
    _text(item.get("status"), f"{name}.status")
    if "subjectHash" in item and item["subjectHash"] is not None:
        _text(item["subjectHash"], f"{name}.subjectHash")
    return item


def _geometry_item(value: object, name: str) -> dict[str, Any]:
    item = _status_item(value, name)
    _text(item.get("subjectHash"), f"{name}.subjectHash")
    pair = _object(item.get("pair"), f"{name}.pair")
    _text(pair.get("classification"), f"{name}.pair.classification")
    if item.get("loop") is not None:
        loop = _object(item["loop"], f"{name}.loop")
        _text(loop.get("classification"), f"{name}.loop.classification")
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
    for name, value in (
        ("ancestry.status", ancestry.get("status")),
        ("authorityNow.status", authority.get("status")),
    ):
        _text(value, name)
    if "subjectHash" in ancestry and ancestry["subjectHash"] is not None:
        _text(ancestry["subjectHash"], "ancestry.subjectHash")
    if "effectiveValidity" in ancestry and ancestry["effectiveValidity"] is not None:
        _text(ancestry["effectiveValidity"], "ancestry.effectiveValidity")

    geometry_results = _list(bundle.get("geometryResults", []), "geometryResults")
    for index, item in enumerate(geometry_results):
        _geometry_item(item, f"geometryResults[{index}]")

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
        "requireGeometry",
        "requireChildSubjectBinding",
    ):
        if key in requirements and not isinstance(requirements[key], bool):
            raise OrientationCenterError(f"requirements.{key} must be boolean")
    return bundle


def load_orientation_center(path: Path) -> dict[str, Any]:
    return validate_orientation_center(json.loads(path.read_text(encoding="utf-8")))


def _reason(code: str, message: str, refs: list[str] | None = None) -> dict[str, object]:
    return {"code": code, "message": message, "refs": sorted(set(refs or []))}


def _subject_mismatch_ids(items: list[dict[str, Any]], subject_hash: str) -> list[str]:
    return [
        item["id"]
        for item in items
        if item.get("subjectHash") is not None and item.get("subjectHash") != subject_hash
    ]


def evaluate_orientation_center(bundle: dict[str, Any]) -> dict[str, object]:
    validated = validate_orientation_center(bundle)
    hard: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    requirements = validated.get("requirements", {})
    subject_hash = _sha256(validated["subject"])
    ancestry = validated["ancestry"]
    ancestry_status = str(ancestry["status"]).upper()
    effective_validity = str(ancestry.get("effectiveValidity", "")).upper()
    authority_status = str(validated["authorityNow"]["status"]).upper()

    ancestry_subject_hash = ancestry.get("subjectHash")
    if ancestry_subject_hash is not None and ancestry_subject_hash != subject_hash:
        hard.append(
            _reason(
                "ANCESTRY_SUBJECT_MISMATCH",
                "ancestry receipt is bound to a different exact subject",
            )
        )
    elif requirements.get("requireChildSubjectBinding", False) and ancestry_subject_hash is None:
        unresolved.append(
            _reason(
                "ANCESTRY_SUBJECT_BINDING_MISSING",
                "ancestry receipt lacks required exact-subject binding",
            )
        )

    if requirements.get("requireAncestry", True):
        if effective_validity == "INVALID" or ancestry_status in {"INVALID", "FAIL", "UNSTABLE"}:
            hard.append(_reason("ANCESTRY_INVALID", "causal ancestry is invalid"))
        elif ancestry_status not in {"VALID", "VALID_WITHIN_TRACE", "PASS"}:
            unresolved.append(_reason("ANCESTRY_UNRESOLVED", "causal ancestry is not resolved"))

    if requirements.get("requireAuthority", True):
        if authority_status in {"INVALID", "FAIL", "REVOKED", "EXPIRED"}:
            hard.append(_reason("AUTHORITY_INVALID", "current authority is invalid, revoked, or expired"))
        elif authority_status not in {"VALID", "PASS", "CURRENT"}:
            unresolved.append(_reason("AUTHORITY_UNRESOLVED", "current authority is not resolved"))

    geometry_results = validated.get("geometryResults", [])
    geometry_mismatch = _subject_mismatch_ids(geometry_results, subject_hash)
    if geometry_mismatch:
        hard.append(
            _reason(
                "GEOMETRY_SUBJECT_MISMATCH",
                "Transition Geometry receipt is bound to a different exact subject",
                geometry_mismatch,
            )
        )
    if requirements.get("requireGeometry", False) and not geometry_results:
        unresolved.append(
            _reason("GEOMETRY_MISSING", "required Transition Geometry evidence is not available")
        )
    for item in geometry_results:
        pair_classification = str(item["pair"]["classification"]).upper()
        loop = item.get("loop")
        loop_classification = (
            str(loop.get("classification", "")).upper() if isinstance(loop, dict) else ""
        )
        if pair_classification == "TORSION_DETECTED" or loop_classification == "CURVATURE_DETECTED":
            unresolved.append(
                _reason(
                    "GEOMETRY_PATH_DEPENDENCE",
                    "material path dependence requires explicit review before orientation is balanced",
                    [item["id"]],
                )
            )

    supporting = validated.get("supportingEvidence", [])
    supporting_valid = [
        item for item in supporting if str(item["status"]).upper() in {"VALID", "PASS", "WITNESSED"}
    ]
    supporting_invalid = [
        item for item in supporting if str(item["status"]).upper() in {"INVALID", "FAIL"}
    ]
    if supporting_invalid:
        hard.append(
            _reason(
                "SUPPORTING_EVIDENCE_INVALID",
                "declared supporting evidence contains an invalid item",
                [item["id"] for item in supporting_invalid],
            )
        )
    if requirements.get("requireSupportingEvidence", True) and not supporting_valid:
        unresolved.append(
            _reason("SUPPORTING_EVIDENCE_MISSING", "no valid supporting evidence is available")
        )

    counterevidence = validated.get("counterevidence", [])
    confirmed_counter = [
        item for item in counterevidence if str(item["status"]).upper() in {"CONFIRMED", "VALID", "FAIL"}
    ]
    open_counter = [
        item for item in counterevidence if str(item["status"]).upper() in {"OPEN", "UNRESOLVED", "PENDING"}
    ]
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
    valid_witnesses = [
        item for item in witnesses if str(item["status"]).upper() in {"VALID", "PASS", "WITNESSED"}
    ]
    invalid_witnesses = [
        item for item in witnesses if str(item["status"]).upper() in {"INVALID", "FAIL", "MISMATCH"}
    ]
    if invalid_witnesses:
        hard.append(
            _reason(
                "INDEPENDENT_WITNESS_CONTRADICTION",
                "an independent witness contradicts the declared orientation",
                [item["id"] for item in invalid_witnesses],
            )
        )
    if requirements.get("requireIndependentWitness", False) and not valid_witnesses:
        unresolved.append(
            _reason("INDEPENDENT_WITNESS_MISSING", "a required independent witness is not available")
        )

    if requirements.get("requireChildSubjectBinding", False):
        for field in (
            "supportingEvidence",
            "counterevidence",
            "verificationDebt",
            "independentWitnesses",
            "watchpoints",
        ):
            items = validated.get(field, [])
            missing = [item["id"] for item in items if item.get("subjectHash") is None]
            mismatched = _subject_mismatch_ids(items, subject_hash)
            if missing:
                unresolved.append(
                    _reason(
                        "CHILD_SUBJECT_BINDING_MISSING",
                        f"{field} contains receipts without required exact-subject binding",
                        missing,
                    )
                )
            if mismatched:
                hard.append(
                    _reason(
                        "CHILD_SUBJECT_MISMATCH",
                        f"{field} contains receipts for another exact subject",
                        mismatched,
                    )
                )

    hard.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
    unresolved.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
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
        "subjectHash": subject_hash,
        "contributingCapabilities": {
            "ancestry": ancestry_status,
            "geometry": [item["pair"]["classification"] for item in geometry_results],
            "verificationDebtItems": len(debt),
            "independentWitnessItems": len(witnesses),
        },
        "hardFindings": hard,
        "unresolved": unresolved,
        "watchpoints": list(validated.get("watchpoints", [])),
        "securityVerdictAuthorized": False,
        "claimBoundary": (
            "Orientation readiness describes whether the declared causal context is resolved enough to proceed. "
            "BALANCED is not a truth, safety, or security verdict."
        ),
    }
