"""ASTRA Opportunity Exact-Head Scorecard v0.1.

This module applies LS-style exact-state/fail-closed discipline to opportunity
analysis. A high score is advisory only: evidence drift, incomplete identity, or
missing execution-surface evidence blocks OUTREACH.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


_ALLOWED_CHECKS = {"PASS", "HOLD", "INCOMPLETE", "NOT_RUN"}
_REQUIRED_CHECKS = (
    "identity",
    "execution_surface",
    "evidence_freshness",
    "reachability",
)


class AstraOpportunityError(ValueError):
    """Raised when an opportunity scorecard input is malformed."""


def _canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def source_set_digest(sources: list[dict[str, Any]]) -> str:
    """Digest reviewed source records, not remote page bytes.

    The digest freezes exactly what the analyst reviewed. It is not a claim that
    the remote source itself is immutable.
    """
    if not isinstance(sources, list) or not sources:
        raise AstraOpportunityError("sources must be a non-empty list")
    for source in sources:
        if not isinstance(source, dict):
            raise AstraOpportunityError("each source must be an object")
        for field in ("source_id", "locator", "claim"):
            if not str(source.get(field, "")).strip():
                raise AstraOpportunityError(f"source missing {field}")
    return "sha256:" + hashlib.sha256(_canonical(sources)).hexdigest()


def evaluate_opportunity(payload: dict[str, Any]) -> dict[str, Any]:
    """Return an advisory, fail-closed Opportunity Exact-Head Scorecard."""
    if not isinstance(payload, dict):
        raise AstraOpportunityError("payload must be an object")

    company_id = str(payload.get("company_id", "")).strip()
    initial_generation = str(payload.get("initial_product_generation", "")).strip()
    final_generation = str(payload.get("final_product_generation", "")).strip()
    next_best_evidence = str(payload.get("next_best_evidence", "")).strip()
    checks = payload.get("checks")
    sources = payload.get("sources")

    if not company_id or not initial_generation or not final_generation:
        raise AstraOpportunityError("company_id and both product generations are required")
    if not next_best_evidence:
        raise AstraOpportunityError("next_best_evidence is required")
    if not isinstance(checks, dict):
        raise AstraOpportunityError("checks must be an object")

    normalized_checks: dict[str, str] = {}
    for name in _REQUIRED_CHECKS:
        value = str(checks.get(name, "INCOMPLETE")).upper()
        if value not in _ALLOWED_CHECKS:
            raise AstraOpportunityError(f"invalid check status for {name}: {value}")
        normalized_checks[name] = value

    digest = source_set_digest(sources)
    drift = initial_generation != final_generation

    if drift:
        action = "HOLD"
        reason = "PRODUCT_GENERATION_DRIFT"
    elif any(value == "HOLD" for value in normalized_checks.values()):
        action = "HOLD"
        reason = "COHERENCE_GATE_HOLD"
    elif any(value in {"INCOMPLETE", "NOT_RUN"} for value in normalized_checks.values()):
        action = "INCOMPLETE"
        reason = "EVIDENCE_INCOMPLETE"
    else:
        action = "OUTREACH"
        reason = "EXACT_STATE_AND_REQUIRED_CHECKS_PASS"

    raw_score = payload.get("opportunity_score")
    if raw_score is not None:
        try:
            score = float(raw_score)
        except (TypeError, ValueError) as exc:
            raise AstraOpportunityError("opportunity_score must be numeric") from exc
        if not 0.0 <= score <= 10.0:
            raise AstraOpportunityError("opportunity_score must be within 0..10")
    else:
        score = None

    return {
        "schema_version": "astra-opportunity-exact-head-v0.1",
        "company_id": company_id,
        "initial_product_generation": initial_generation,
        "final_product_generation": final_generation,
        "exact_state_preserved": not drift,
        "source_set_digest": digest,
        "checks": normalized_checks,
        "opportunity_score": score,
        "verification_debt": str(payload.get("verification_debt", "UNKNOWN")).upper(),
        "competing_hypothesis": str(payload.get("competing_hypothesis", "UNSPECIFIED")),
        "next_best_evidence": next_best_evidence,
        "action": action,
        "reason": reason,
        "advisory_only": True,
        "outreach_authorized_by_scorecard": False,
        "private_correspondence_embedded": False,
    }
