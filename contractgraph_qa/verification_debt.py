"""Deterministic verification-debt accounting distinct from semantic verdicts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_bool,
    require_list,
    require_object,
    require_subject,
    require_text,
)

SCHEMA = "cgqa/verification-debt/v0.1"
ALLOWED = {
    "SUBMITTED",
    "ADMITTED",
    "DEFERRED_CAPACITY",
    "DEFERRED_OVERSIZED",
    "DEFERRED_BUDGET",
    "BLOCKED",
    "COMPLETED",
    "COMPLETED_PASS",
    "COMPLETED_FAIL",
    "NOT_APPLICABLE",
}
RESOLVED = {"COMPLETED_PASS", "NOT_APPLICABLE"}
FAILED = {"COMPLETED_FAIL"}


class VerificationDebtError(CausalTemporalError):
    """Raised when verification-debt input is malformed."""


def validate_verification_debt(data: object) -> dict[str, Any]:
    model = require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise VerificationDebtError(f"schema must equal {SCHEMA!r}")
    _, subject_hash = require_subject(model)
    work = require_list(model.get("work"), "work")
    seen: set[str] = set()
    for index, raw in enumerate(work):
        item = require_object(raw, f"work[{index}]")
        work_id = require_text(item.get("id"), f"work[{index}].id")
        if work_id in seen:
            raise VerificationDebtError(f"duplicate work id: {work_id}")
        seen.add(work_id)
        require_text(item.get("capability"), f"work[{index}].capability")
        required = item.get("required", True)
        require_bool(required, f"work[{index}].required")
        status = require_text(item.get("status"), f"work[{index}].status")
        if status not in ALLOWED:
            raise VerificationDebtError(f"unsupported work status: {status}")
        if item.get("subjectHash") != subject_hash:
            raise VerificationDebtError(f"work[{index}].subjectHash does not match exact subject")
    return model


def load_verification_debt(path: Path) -> dict[str, Any]:
    return validate_verification_debt(json.loads(path.read_text(encoding="utf-8")))


def evaluate_verification_debt(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_verification_debt(model)
    subject_hash = canonical_sha256(validated["subject"])
    work = sorted(validated["work"], key=lambda item: item["id"])
    required = [item for item in work if item.get("required", True)]
    failed = [item for item in required if item["status"] in FAILED]
    unresolved = [item for item in required if item["status"] not in RESOLVED | FAILED]
    resolved = [item for item in required if item["status"] in RESOLVED]
    optional_unresolved = [
        item for item in work if not item.get("required", True) and item["status"] not in RESOLVED | FAILED
    ]

    if failed:
        status = "fail"
        orientation_impact = "UNSTABLE"
    elif unresolved:
        status = "hold"
        orientation_impact = "INDETERMINATE"
    else:
        status = "pass"
        orientation_impact = "BALANCED_ALLOWED"

    return {
        "schema": "cgqa/verification-debt-result/v0.1",
        "status": status,
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(validated),
        "requiredCount": len(required),
        "resolvedRequiredIds": [item["id"] for item in resolved],
        "unresolvedRequiredIds": [item["id"] for item in unresolved],
        "failedRequiredIds": [item["id"] for item in failed],
        "optionalUnresolvedIds": [item["id"] for item in optional_unresolved],
        "orientationImpact": orientation_impact,
        "debtReceipts": [
            {
                "id": item["id"],
                "status": item["status"],
                "required": item.get("required", True),
                "capability": item["capability"],
                "subjectHash": subject_hash,
            }
            for item in work
        ],
        "claimBoundary": (
            "Verification workflow state is not a semantic verdict: Completed != PASS, "
            "Deferred != Invalid, and unresolved required work remains debt."
        ),
    }
