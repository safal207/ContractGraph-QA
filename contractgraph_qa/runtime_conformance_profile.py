from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from contractgraph_qa.runtime_conformance_matrix import (
    CAPABILITY_STATUSES,
    MUTATION_STATUSES,
    PROJECTION_SPEC,
)

PROFILE_SCHEMA_VERSION = "agent-runtime-conformance-profile/v0.1"
VALIDATION_SCHEMA_VERSION = "agent-runtime-conformance-profile-validation/v0.1"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")
_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "projectionSpec",
    "id",
    "name",
    "source",
    "boundaryType",
    "projection",
    "replay",
    "explicitAbsence",
    "deadlineBinding",
    "persistence",
    "appendOnly",
    "destructiveMutations",
    "evidenceRefs",
    "claimBoundary",
}


def load_runtime_conformance_profile(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        profile = json.load(handle)
    validate_runtime_conformance_profile(profile)
    return profile


def validate_runtime_conformance_profile(profile: dict[str, Any]) -> None:
    """Validate one portable Agent Runtime Conformance Profile v0.1.

    Validation proves that the profile is structurally and internally
    consistent. It does not prove the truth, completeness, or authenticity of
    the referenced benchmark evidence.
    """

    if not isinstance(profile, dict):
        raise ValueError("runtime conformance profile must be a JSON object")

    extras = sorted(set(profile) - _TOP_LEVEL_KEYS)
    if extras:
        raise ValueError(f"runtime conformance profile contains unexpected fields: {', '.join(extras)}")
    missing = sorted(_TOP_LEVEL_KEYS - set(profile))
    if missing:
        raise ValueError(f"runtime conformance profile missing required fields: {', '.join(missing)}")

    if profile.get("schemaVersion") != PROFILE_SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {PROFILE_SCHEMA_VERSION}")
    if profile.get("projectionSpec") != PROJECTION_SPEC:
        raise ValueError(f"projectionSpec must be {PROJECTION_SPEC}")

    _non_empty_text(profile.get("id"), "id")
    _non_empty_text(profile.get("name"), "name")
    _non_empty_text(profile.get("boundaryType"), "boundaryType")
    _non_empty_text(profile.get("claimBoundary"), "claimBoundary")

    source = profile.get("source")
    if not isinstance(source, dict) or set(source) != {"repository", "commit"}:
        raise ValueError("source must contain exactly repository and commit")
    repository = _non_empty_text(source.get("repository"), "source.repository")
    if not _REPOSITORY.fullmatch(repository):
        raise ValueError("source.repository must use owner/name form")
    commit = _non_empty_text(source.get("commit"), "source.commit")
    if not _HEX40.fullmatch(commit):
        raise ValueError("source.commit must be a pinned 40-character lowercase SHA")

    projection = profile.get("projection")
    if not isinstance(projection, dict) or set(projection) != {"status", "passed", "total"}:
        raise ValueError("projection must contain exactly status, passed, and total")
    status = projection.get("status")
    if status not in {"pass", "fail"}:
        raise ValueError("projection.status must be pass or fail")
    passed = projection.get("passed")
    total = projection.get("total")
    if isinstance(passed, bool) or not isinstance(passed, int):
        raise ValueError("projection.passed must be an integer")
    if isinstance(total, bool) or not isinstance(total, int) or total != 8:
        raise ValueError("projection.total must be 8")
    if passed < 0 or passed > total:
        raise ValueError("projection.passed is outside the score range")
    if (status == "pass") != (passed == total):
        raise ValueError("projection status and score disagree")

    for axis in ("replay", "explicitAbsence", "deadlineBinding", "persistence", "appendOnly"):
        value = profile.get(axis)
        if value not in CAPABILITY_STATUSES:
            raise ValueError(f"{axis} has an invalid capability status")

    # An 8/8 projection necessarily contains these three passing checks.
    if status == "pass":
        for axis in ("replay", "explicitAbsence", "deadlineBinding"):
            if profile[axis] != "pass":
                raise ValueError(f"projection=pass requires {axis}=pass")

    mutations = profile.get("destructiveMutations")
    if not isinstance(mutations, dict) or set(mutations) != {"status", "operations"}:
        raise ValueError("destructiveMutations must contain exactly status and operations")
    mutation_status = mutations.get("status")
    if mutation_status not in MUTATION_STATUSES:
        raise ValueError("destructiveMutations.status is invalid")
    operations = mutations.get("operations")
    if not isinstance(operations, list) or any(
        not isinstance(operation, str) or not operation.strip() for operation in operations
    ):
        raise ValueError("destructiveMutations.operations must be a string array")
    if len(set(operations)) != len(operations):
        raise ValueError("destructiveMutations.operations contains duplicates")
    if mutation_status == "present":
        if not operations:
            raise ValueError("destructive mutations are present but no operations are named")
        if profile.get("appendOnly") != "fail":
            raise ValueError("observed destructive mutations require appendOnly=fail")
    elif operations:
        raise ValueError("destructive operations may only be listed with status=present")

    evidence_refs = profile.get("evidenceRefs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise ValueError("evidenceRefs must be a non-empty string array")
    if any(not isinstance(reference, str) or not reference.strip() for reference in evidence_refs):
        raise ValueError("evidenceRefs must contain only non-empty strings")
    if len(set(evidence_refs)) != len(evidence_refs):
        raise ValueError("evidenceRefs contains duplicates")


def evaluate_runtime_conformance_profile(profile: dict[str, Any]) -> dict[str, object]:
    """Return a machine-readable interpretation after strict validation."""

    validate_runtime_conformance_profile(profile)
    projection = profile["projection"]
    mutations = profile["destructiveMutations"]
    return {
        "schemaVersion": VALIDATION_SCHEMA_VERSION,
        "profileValid": True,
        "runtimeId": profile["id"],
        "runtimeName": profile["name"],
        "source": profile["source"],
        "boundaryType": profile["boundaryType"],
        "projectionConformant": projection["status"] == "pass",
        "projection": {
            "status": projection["status"],
            "passed": projection["passed"],
            "total": projection["total"],
        },
        "axes": {
            "replay": profile["replay"],
            "explicitAbsence": profile["explicitAbsence"],
            "deadlineBinding": profile["deadlineBinding"],
            "persistence": profile["persistence"],
            "appendOnly": profile["appendOnly"],
            "destructiveMutations": mutations["status"],
        },
        "destructiveMutationOperations": list(mutations["operations"]),
        "evidenceReferenceCount": len(profile["evidenceRefs"]),
        "claimBoundary": profile["claimBoundary"],
        "semantics": {
            "profileValidMeans": "structure and internal consistency validated",
            "projectionConformantMeans": "all eight Witness Projection Conformance v0.1 checks passed",
            "notProven": "evidence authenticity, completeness, framework-wide safety, or storage immutability unless explicitly measured",
        },
    }


def _non_empty_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()
