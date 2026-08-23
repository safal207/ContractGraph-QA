"""Compose CGQ-RACE-001 into an existing Hydrated Contract Lattice result.

This layer is intentionally additive. The core hydrated verifier keeps its v0.1
API and semantics; callers may opt into a reviewed protective-ordering model.
Once supplied, that model becomes a required proof leg for a full PASS.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Mapping

from contractgraph_qa.protective_ordering import (
    ProtectiveOrderingModel,
    protective_ordering_model_sha256,
    run_protective_ordering_model,
)

RESULT_SCHEMA_VERSION = "hydrated-race-composition-result-v0.1"


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compose_hydrated_with_protective_ordering(
    hydrated_result: Mapping[str, object],
    race_model: ProtectiveOrderingModel,
) -> dict[str, object]:
    """Make CGQ-RACE-001 an explicit required proof leg for one hydrated result."""

    base_status = hydrated_result.get("status")
    if base_status not in {"pass", "fail", "inconclusive"}:
        raise ValueError("hydrated result has invalid status")

    race_result = run_protective_ordering_model(race_model)
    race_status = race_result["status"]

    if base_status == "fail" or race_status == "fail":
        overall = "fail"
    elif base_status == "pass" and race_status == "pass":
        overall = "pass"
    else:
        overall = "inconclusive"

    result = copy.deepcopy(dict(hydrated_result))
    result["status"] = overall
    result["protectiveOrderingVerification"] = race_result

    fingerprint_raw = result.get("evidenceFingerprint")
    fingerprint = dict(fingerprint_raw) if isinstance(fingerprint_raw, dict) else {}
    fingerprint.pop("assessmentSha256", None)
    fingerprint["raceModelSha256"] = protective_ordering_model_sha256(race_model)
    fingerprint["assessmentSha256"] = _canonical_sha256(fingerprint)
    result["evidenceFingerprint"] = fingerprint

    base_boundary = result.get("claimBoundary")
    boundary_prefix = str(base_boundary) + " " if isinstance(base_boundary, str) and base_boundary else ""
    result["claimBoundary"] = (
        boundary_prefix
        + "When a protective-ordering model is supplied, full PASS additionally requires CGQ-RACE-001 PASS. "
        "The race verifier is exact over the reviewed two-order counterfactual; joint action enablement, "
        "modeled outcomes, and the business requirement that the protective right survive ordering remain "
        "separate source/specification evidence claims."
    )
    result["compositionSchemaVersion"] = RESULT_SCHEMA_VERSION
    return result
