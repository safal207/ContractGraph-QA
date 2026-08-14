"""Minimal executable Fractal Causal Refactoring Protocol (FCRP) core.

FCRP v0.1 does not claim automated root-cause discovery. It validates that a
causal-refactoring case keeps its idea, evidence, causal path, first meaningful
divergence, selected refactor point, and upward-verification boundary explicit
and internally coherent.
"""

from __future__ import annotations

import copy
from typing import Any

FCRP_SCHEMA = "cgqa.fcrp-case.v0.1"
_ALLOWED_DIRECTIONS = {"DOWN", "UP", "SIDEWAYS", "STOP"}
_ALLOWED_VERDICTS = {"PASS", "FAIL", "NOT_REQUIRED"}


class FCRPError(ValueError):
    """Raised when an FCRP case violates the v0.1 structural contract."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FCRPError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise FCRPError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FCRPError(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise FCRPError(f"{field} must be a boolean")
    return value


def _evidence_refs(value: object, field: str, evidence_ids: set[str]) -> list[str]:
    refs = _list(value, field)
    normalized: list[str] = []
    for index, ref in enumerate(refs):
        ref_id = _text(ref, f"{field}[{index}]")
        if ref_id not in evidence_ids:
            raise FCRPError(f"{field}[{index}] references unknown evidence id {ref_id}")
        normalized.append(ref_id)
    return normalized


def evaluate_fcrp_case(case: dict[str, Any]) -> dict[str, Any]:
    """Validate one FCRP case and return its deterministic protocol decision."""
    case = copy.deepcopy(_object(case, "case"))
    if case.get("schema") != FCRP_SCHEMA:
        raise FCRPError(f"case.schema must be {FCRP_SCHEMA}")

    case_id = _text(case.get("caseId"), "case.caseId")
    scope = _object(case.get("scope"), "case.scope")
    _text(scope.get("nodeId"), "case.scope.nodeId")
    _text(scope.get("scale"), "case.scope.scale")
    _text(scope.get("idea"), "case.scope.idea")

    evidence = _list(case.get("evidence"), "case.evidence")
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence):
        entry = _object(item, f"case.evidence[{index}]")
        evidence_id = _text(entry.get("id"), f"case.evidence[{index}].id")
        if evidence_id in evidence_ids:
            raise FCRPError(f"duplicate evidence id {evidence_id}")
        evidence_ids.add(evidence_id)
        _text(entry.get("kind"), f"case.evidence[{index}].kind")
        _text(entry.get("ref"), f"case.evidence[{index}].ref")
        _text(entry.get("claim"), f"case.evidence[{index}].claim")

    timeline = _object(case.get("timeline"), "case.timeline")
    for phase in ("past", "present", "future"):
        state = _object(timeline.get(phase), f"case.timeline.{phase}")
        _text(state.get("summary"), f"case.timeline.{phase}.summary")
        _evidence_refs(
            state.get("evidenceRefs", []),
            f"case.timeline.{phase}.evidenceRefs",
            evidence_ids,
        )

    causal_path = _list(case.get("causalPath"), "case.causalPath")
    if len(causal_path) < 2:
        raise FCRPError("case.causalPath must contain at least two causal points")

    point_order: dict[str, int] = {}
    for index, item in enumerate(causal_path):
        point = _object(item, f"case.causalPath[{index}]")
        point_id = _text(point.get("id"), f"case.causalPath[{index}].id")
        if point_id in point_order:
            raise FCRPError(f"duplicate causal point id {point_id}")
        point_order[point_id] = index
        _text(point.get("level"), f"case.causalPath[{index}].level")
        _text(point.get("phase"), f"case.causalPath[{index}].phase")
        _text(point.get("statement"), f"case.causalPath[{index}].statement")
        _evidence_refs(
            point.get("evidenceRefs", []),
            f"case.causalPath[{index}].evidenceRefs",
            evidence_ids,
        )

    divergence = _object(case.get("divergence"), "case.divergence")
    symptom = _text(divergence.get("symptomPoint"), "case.divergence.symptomPoint")
    first_divergence = _text(
        divergence.get("firstMeaningfulDivergence"),
        "case.divergence.firstMeaningfulDivergence",
    )
    cause = _text(divergence.get("causePoint"), "case.divergence.causePoint")
    refactor = _text(divergence.get("selectedRefactorPoint"), "case.divergence.selectedRefactorPoint")
    for field, point_id in (
        ("symptomPoint", symptom),
        ("firstMeaningfulDivergence", first_divergence),
        ("causePoint", cause),
        ("selectedRefactorPoint", refactor),
    ):
        if point_id not in point_order:
            raise FCRPError(f"case.divergence.{field} references unknown causal point {point_id}")

    if point_order[first_divergence] > point_order[symptom]:
        raise FCRPError("firstMeaningfulDivergence must not occur after symptomPoint")
    if point_order[cause] > point_order[symptom]:
        raise FCRPError("causePoint must not occur after symptomPoint")
    _evidence_refs(
        divergence.get("evidenceRefs", []),
        "case.divergence.evidenceRefs",
        evidence_ids,
    )

    navigation = _object(case.get("navigation"), "case.navigation")
    direction = _text(navigation.get("direction"), "case.navigation.direction")
    if direction not in _ALLOWED_DIRECTIONS:
        raise FCRPError(f"case.navigation.direction must be one of {sorted(_ALLOWED_DIRECTIONS)}")
    _text(navigation.get("reason"), "case.navigation.reason")

    refactor_plan = _object(case.get("refactor"), "case.refactor")
    if _text(refactor_plan.get("point"), "case.refactor.point") != refactor:
        raise FCRPError("case.refactor.point must equal divergence.selectedRefactorPoint")
    _text(refactor_plan.get("change"), "case.refactor.change")
    _text(refactor_plan.get("expectedEffect"), "case.refactor.expectedEffect")

    verification = _object(case.get("verification"), "case.verification")
    local = _text(verification.get("local"), "case.verification.local")
    upward = _text(verification.get("upward"), "case.verification.upward")
    if local not in _ALLOWED_VERDICTS - {"NOT_REQUIRED"}:
        raise FCRPError("case.verification.local must be PASS or FAIL")
    if upward not in _ALLOWED_VERDICTS:
        raise FCRPError("case.verification.upward must be PASS, FAIL, or NOT_REQUIRED")
    verification_refs = _evidence_refs(
        verification.get("evidenceRefs", []),
        "case.verification.evidenceRefs",
        evidence_ids,
    )
    if local == "PASS" and not verification_refs:
        raise FCRPError("a PASS local verification requires evidenceRefs")

    stop = _object(verification.get("stopConditions"), "case.verification.stopConditions")
    stop_ok = all(
        (
            _bool(stop.get("parentInvariantsPreserved"), "case.verification.stopConditions.parentInvariantsPreserved"),
            _bool(stop.get("crossBoundaryEffectsAbsent"), "case.verification.stopConditions.crossBoundaryEffectsAbsent"),
            _bool(stop.get("causalExplanationComplete"), "case.verification.stopConditions.causalExplanationComplete"),
        )
    )
    if upward == "NOT_REQUIRED" and not stop_ok:
        raise FCRPError("upward verification may be NOT_REQUIRED only when all stop conditions hold")

    decision = "PASS" if local == "PASS" and (upward == "PASS" or (upward == "NOT_REQUIRED" and stop_ok)) else "BLOCK"
    return {
        "schema": "cgqa.fcrp-result.v0.1",
        "caseId": case_id,
        "decision": decision,
        "firstMeaningfulDivergence": first_divergence,
        "causePoint": cause,
        "refactorPoint": refactor,
        "navigationDirection": direction,
        "localVerification": local,
        "upwardVerification": upward,
        "stopConditionsSatisfied": stop_ok,
    }
