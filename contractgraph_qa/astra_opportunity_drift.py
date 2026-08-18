"""ASTRA Opportunity Drift Watch v0.1.

Compare two frozen Opportunity Exact-Head scorecards without rewriting history.
The watch is advisory-only: it may surface a material transition or require
re-verification, but it never authorizes outreach by itself.
"""
from __future__ import annotations

from typing import Any


class AstraOpportunityDriftError(ValueError):
    """Raised when drift-watch inputs are malformed."""


def _score(card: dict[str, Any]) -> float | None:
    value = card.get("opportunity_score")
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise AstraOpportunityDriftError("opportunity_score must be numeric") from exc
    if not 0.0 <= score <= 10.0:
        raise AstraOpportunityDriftError("opportunity_score must be within 0..10")
    return score


def _surface_set(card: dict[str, Any]) -> set[str]:
    raw = card.get("execution_surfaces", [])
    if raw is None:
        return set()
    if not isinstance(raw, list):
        raise AstraOpportunityDriftError("execution_surfaces must be a list")
    values = {str(item).strip() for item in raw if str(item).strip()}
    return values


def evaluate_opportunity_drift(payload: dict[str, Any]) -> dict[str, Any]:
    """Compare prior/current frozen scorecards and classify material drift.

    Material positive drift requires fresh execution-surface evidence, not only a
    higher subjective score. Identity drift or stale/incomplete current evidence
    blocks promotion and requires re-verification.
    """
    if not isinstance(payload, dict):
        raise AstraOpportunityDriftError("payload must be an object")

    previous = payload.get("previous")
    current = payload.get("current")
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise AstraOpportunityDriftError("previous and current scorecards are required")

    previous_company = str(previous.get("company_id", "")).strip()
    current_company = str(current.get("company_id", "")).strip()
    if not previous_company or not current_company:
        raise AstraOpportunityDriftError("both scorecards require company_id")
    if previous_company != current_company:
        return {
            "schema_version": "astra-opportunity-drift-v0.1",
            "company_id": current_company,
            "classification": "IDENTITY_DRIFT",
            "action": "HOLD",
            "reason": "COMPANY_IDENTITY_CHANGED",
            "advisory_only": True,
            "outreach_authorized": False,
        }

    previous_generation = str(previous.get("final_product_generation", "")).strip()
    current_generation = str(current.get("final_product_generation", "")).strip()
    if not previous_generation or not current_generation:
        raise AstraOpportunityDriftError("both scorecards require final_product_generation")

    current_action = str(current.get("action", "INCOMPLETE")).upper()
    current_checks = current.get("checks", {})
    if not isinstance(current_checks, dict):
        raise AstraOpportunityDriftError("current checks must be an object")

    blocking = any(
        str(value).upper() in {"HOLD", "INCOMPLETE", "NOT_RUN"}
        for value in current_checks.values()
    ) or current_action in {"HOLD", "INCOMPLETE"}

    previous_surfaces = _surface_set(previous)
    current_surfaces = _surface_set(current)
    added_surfaces = sorted(current_surfaces - previous_surfaces)
    removed_surfaces = sorted(previous_surfaces - current_surfaces)

    previous_score = _score(previous)
    current_score = _score(current)
    delta_score = None
    if previous_score is not None and current_score is not None:
        delta_score = round(current_score - previous_score, 3)

    generation_changed = previous_generation != current_generation

    if blocking:
        classification = "REVERIFY"
        action = "HOLD"
        reason = "CURRENT_EVIDENCE_NOT_COHERENT"
    elif generation_changed and removed_surfaces and not added_surfaces:
        classification = "NEGATIVE_DRIFT"
        action = "REASSESS"
        reason = "EXECUTION_SURFACE_CONTRACTED"
    elif added_surfaces:
        classification = "MATERIAL_POSITIVE_DRIFT"
        action = "PRIORITIZE_REVIEW"
        reason = "NEW_EXECUTION_SURFACE_OBSERVED"
    elif generation_changed:
        classification = "GENERATION_DRIFT"
        action = "REVERIFY"
        reason = "PRODUCT_GENERATION_CHANGED_WITHOUT_NEW_SURFACE_PROOF"
    elif delta_score is not None and abs(delta_score) >= float(payload.get("score_noise_threshold", 0.5)):
        classification = "SCORE_DRIFT_ONLY"
        action = "NO_AUTOMATIC_PROMOTION"
        reason = "SCORE_CHANGED_WITHOUT_EXECUTION_SURFACE_CHANGE"
    else:
        classification = "STABLE"
        action = "NO_CHANGE"
        reason = "NO_MATERIAL_DRIFT"

    return {
        "schema_version": "astra-opportunity-drift-v0.1",
        "company_id": current_company,
        "previous_generation": previous_generation,
        "current_generation": current_generation,
        "generation_changed": generation_changed,
        "previous_score": previous_score,
        "current_score": current_score,
        "delta_score": delta_score,
        "added_execution_surfaces": added_surfaces,
        "removed_execution_surfaces": removed_surfaces,
        "classification": classification,
        "action": action,
        "reason": reason,
        "next_best_evidence": str(current.get("next_best_evidence", "")).strip(),
        "advisory_only": True,
        "outreach_authorized": False,
        "history_rewritten": False,
    }
