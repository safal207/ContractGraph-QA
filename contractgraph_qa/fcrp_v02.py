"""Additive Fractal Causal Refactoring Protocol (FCRP) v0.2 evaluator.

v0.2 strengthens the evidence contract discovered by the repository self-tests.
It does not discover root causes or authorize mutations. It validates that a
causal/refactor case makes idea, time, evidence strength, simulation,
authorization, and propagation-stop boundaries explicit and coherent.
"""

from __future__ import annotations

import copy
from typing import Any

FCRP_V02_SCHEMA = "cgqa.fcrp-case.v0.2"
_ALLOWED_DIRECTIONS = {"DOWN", "UP", "SIDEWAYS", "STOP"}
_ALLOWED_VERDICTS = {"PASS", "FAIL", "NOT_REQUIRED"}
_ALLOWED_EVIDENCE_STRENGTH = {
    "OBSERVED",
    "RECOMPUTABLE",
    "ATTESTED",
    "PROVENANCE_ONLY",
    "SYNTHETIC",
}
_ALLOWED_TIME_DOMAINS = {
    "WALL_CLOCK",
    "PROTOCOL_CLOCK",
    "CAUSAL_SEQUENCE",
    "REPOSITORY_HISTORY",
}
_ALLOWED_SIMULATION_SURFACES = {
    "children",
    "siblings",
    "parent",
    "dependencies",
    "future",
}


class FCRPV02Error(ValueError):
    """Raised when an FCRP v0.2 case violates the structural contract."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FCRPV02Error(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise FCRPV02Error(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FCRPV02Error(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise FCRPV02Error(f"{field} must be a boolean")
    return value


def _text_list(value: object, field: str, *, non_empty: bool = False) -> list[str]:
    values = _list(value, field)
    normalized = [_text(item, f"{field}[{index}]") for index, item in enumerate(values)]
    if non_empty and not normalized:
        raise FCRPV02Error(f"{field} must not be empty")
    if len(normalized) != len(set(normalized)):
        raise FCRPV02Error(f"{field} must not contain duplicates")
    return normalized


def _evidence_refs(value: object, field: str, evidence_ids: set[str]) -> list[str]:
    refs = _text_list(value, field)
    for index, ref_id in enumerate(refs):
        if ref_id not in evidence_ids:
            raise FCRPV02Error(f"{field}[{index}] references unknown evidence id {ref_id}")
    return refs


def evaluate_fcrp_v02_case(case: dict[str, Any]) -> dict[str, Any]:
    """Validate one FCRP v0.2 case and return a deterministic protocol decision."""

    case = copy.deepcopy(_object(case, "case"))
    if case.get("schema") != FCRP_V02_SCHEMA:
        raise FCRPV02Error(f"case.schema must be {FCRP_V02_SCHEMA}")

    case_id = _text(case.get("caseId"), "case.caseId")

    scope = _object(case.get("scope"), "case.scope")
    _text(scope.get("nodeId"), "case.scope.nodeId")
    _text(scope.get("scale"), "case.scope.scale")
    idea = _object(scope.get("ideaContract"), "case.scope.ideaContract")
    _text(idea.get("purpose"), "case.scope.ideaContract.purpose")
    _text(idea.get("expectedOutcome"), "case.scope.ideaContract.expectedOutcome")
    _text_list(idea.get("invariants"), "case.scope.ideaContract.invariants", non_empty=True)
    _text_list(
        idea.get("forbiddenOutcomes"),
        "case.scope.ideaContract.forbiddenOutcomes",
        non_empty=True,
    )
    _text_list(idea.get("dependencies", []), "case.scope.ideaContract.dependencies")
    _text(idea.get("parentContract"), "case.scope.ideaContract.parentContract")

    evidence = _list(case.get("evidence"), "case.evidence")
    if not evidence:
        raise FCRPV02Error("case.evidence must not be empty")
    evidence_ids: set[str] = set()
    evidence_strengths: dict[str, str] = {}
    for index, item in enumerate(evidence):
        entry = _object(item, f"case.evidence[{index}]")
        evidence_id = _text(entry.get("id"), f"case.evidence[{index}].id")
        if evidence_id in evidence_ids:
            raise FCRPV02Error(f"duplicate evidence id {evidence_id}")
        evidence_ids.add(evidence_id)
        _text(entry.get("kind"), f"case.evidence[{index}].kind")
        _text(entry.get("ref"), f"case.evidence[{index}].ref")
        _text(entry.get("claim"), f"case.evidence[{index}].claim")
        strength = _text(entry.get("strength"), f"case.evidence[{index}].strength")
        if strength not in _ALLOWED_EVIDENCE_STRENGTH:
            raise FCRPV02Error(
                f"case.evidence[{index}].strength must be one of "
                f"{sorted(_ALLOWED_EVIDENCE_STRENGTH)}"
            )
        evidence_strengths[evidence_id] = strength
        if _bool(
            entry.get("mayGrantAuthority"),
            f"case.evidence[{index}].mayGrantAuthority",
        ):
            raise FCRPV02Error("evidence may inform authorization but may not itself grant authority")

    time_model = _object(case.get("timeModel"), "case.timeModel")
    domains = _text_list(time_model.get("domains"), "case.timeModel.domains", non_empty=True)
    unknown_domains = sorted(set(domains) - _ALLOWED_TIME_DOMAINS)
    if unknown_domains:
        raise FCRPV02Error(f"case.timeModel.domains contains unsupported values {unknown_domains}")
    primary_domain = _text(time_model.get("primaryDomain"), "case.timeModel.primaryDomain")
    if primary_domain not in domains:
        raise FCRPV02Error("case.timeModel.primaryDomain must be present in case.timeModel.domains")
    causal_advance_required = _bool(
        time_model.get("causalAdvanceRequired"),
        "case.timeModel.causalAdvanceRequired",
    )
    causal_advance_refs = _evidence_refs(
        time_model.get("causalAdvanceEvidenceRefs", []),
        "case.timeModel.causalAdvanceEvidenceRefs",
        evidence_ids,
    )
    if causal_advance_required and not causal_advance_refs:
        raise FCRPV02Error(
            "case.timeModel.causalAdvanceRequired=true requires causalAdvanceEvidenceRefs"
        )

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
        raise FCRPV02Error("case.causalPath must contain at least two causal points")
    point_order: dict[str, int] = {}
    for index, item in enumerate(causal_path):
        point = _object(item, f"case.causalPath[{index}]")
        point_id = _text(point.get("id"), f"case.causalPath[{index}].id")
        if point_id in point_order:
            raise FCRPV02Error(f"duplicate causal point id {point_id}")
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
    refactor = _text(
        divergence.get("selectedRefactorPoint"),
        "case.divergence.selectedRefactorPoint",
    )
    for field, point_id in (
        ("symptomPoint", symptom),
        ("firstMeaningfulDivergence", first_divergence),
        ("causePoint", cause),
        ("selectedRefactorPoint", refactor),
    ):
        if point_id not in point_order:
            raise FCRPV02Error(f"case.divergence.{field} references unknown causal point {point_id}")
    if point_order[first_divergence] > point_order[symptom]:
        raise FCRPV02Error("firstMeaningfulDivergence must not occur after symptomPoint")
    if point_order[cause] > point_order[symptom]:
        raise FCRPV02Error("causePoint must not occur after symptomPoint")
    _evidence_refs(
        divergence.get("evidenceRefs", []),
        "case.divergence.evidenceRefs",
        evidence_ids,
    )

    navigation = _object(case.get("navigation"), "case.navigation")
    direction = _text(navigation.get("direction"), "case.navigation.direction")
    if direction not in _ALLOWED_DIRECTIONS:
        raise FCRPV02Error(f"case.navigation.direction must be one of {sorted(_ALLOWED_DIRECTIONS)}")
    _text(navigation.get("reason"), "case.navigation.reason")

    refactor_plan = _object(case.get("refactor"), "case.refactor")
    if _text(refactor_plan.get("point"), "case.refactor.point") != refactor:
        raise FCRPV02Error("case.refactor.point must equal divergence.selectedRefactorPoint")
    _text(refactor_plan.get("change"), "case.refactor.change")
    _text(refactor_plan.get("expectedEffect"), "case.refactor.expectedEffect")

    simulation = _object(case.get("simulation"), "case.simulation")
    simulation_status = _text(simulation.get("status"), "case.simulation.status")
    if simulation_status not in _ALLOWED_VERDICTS:
        raise FCRPV02Error(
            f"case.simulation.status must be one of {sorted(_ALLOWED_VERDICTS)}"
        )
    surfaces = _text_list(
        simulation.get("checkedSurfaces", []),
        "case.simulation.checkedSurfaces",
    )
    unknown_surfaces = sorted(set(surfaces) - _ALLOWED_SIMULATION_SURFACES)
    if unknown_surfaces:
        raise FCRPV02Error(
            f"case.simulation.checkedSurfaces contains unsupported values {unknown_surfaces}"
        )
    simulation_refs = _evidence_refs(
        simulation.get("evidenceRefs", []),
        "case.simulation.evidenceRefs",
        evidence_ids,
    )
    if simulation_status == "PASS" and not simulation_refs:
        raise FCRPV02Error("a PASS simulation requires evidenceRefs")
    if simulation_status == "NOT_REQUIRED":
        _text(simulation.get("reason"), "case.simulation.reason")

    authorization = _object(case.get("authorization"), "case.authorization")
    if _bool(
        authorization.get("evidenceMayGrantAuthority"),
        "case.authorization.evidenceMayGrantAuthority",
    ):
        raise FCRPV02Error("case.authorization.evidenceMayGrantAuthority must be false")
    mutation_authorized = _bool(
        authorization.get("mutationAuthorized"),
        "case.authorization.mutationAuthorized",
    )
    authorization_ref = authorization.get("authorizationRef")
    if mutation_authorized:
        _text(authorization_ref, "case.authorization.authorizationRef")
    elif authorization_ref not in (None, ""):
        _text(authorization_ref, "case.authorization.authorizationRef")
    _text(
        authorization.get("authorityBoundary"),
        "case.authorization.authorityBoundary",
    )

    verification = _object(case.get("verification"), "case.verification")
    local = _text(verification.get("local"), "case.verification.local")
    upward = _text(verification.get("upward"), "case.verification.upward")
    if local not in {"PASS", "FAIL"}:
        raise FCRPV02Error("case.verification.local must be PASS or FAIL")
    if upward not in _ALLOWED_VERDICTS:
        raise FCRPV02Error(
            "case.verification.upward must be PASS, FAIL, or NOT_REQUIRED"
        )
    verification_refs = _evidence_refs(
        verification.get("evidenceRefs", []),
        "case.verification.evidenceRefs",
        evidence_ids,
    )
    if local == "PASS" and not verification_refs:
        raise FCRPV02Error("a PASS local verification requires evidenceRefs")

    stop = _object(verification.get("stopConditions"), "case.verification.stopConditions")
    stop_values = {
        "parentInvariantsPreserved": _bool(
            stop.get("parentInvariantsPreserved"),
            "case.verification.stopConditions.parentInvariantsPreserved",
        ),
        "crossBoundaryEffectsAbsent": _bool(
            stop.get("crossBoundaryEffectsAbsent"),
            "case.verification.stopConditions.crossBoundaryEffectsAbsent",
        ),
        "causalPropagationStopped": _bool(
            stop.get("causalPropagationStopped"),
            "case.verification.stopConditions.causalPropagationStopped",
        ),
        "causalExplanationComplete": _bool(
            stop.get("causalExplanationComplete"),
            "case.verification.stopConditions.causalExplanationComplete",
        ),
    }
    stop_ok = all(stop_values.values())
    if upward == "NOT_REQUIRED" and not stop_ok:
        raise FCRPV02Error(
            "upward verification may be NOT_REQUIRED only when all four stop conditions hold"
        )

    decision = (
        "PASS"
        if local == "PASS"
        and simulation_status != "FAIL"
        and (upward == "PASS" or (upward == "NOT_REQUIRED" and stop_ok))
        else "BLOCK"
    )

    return {
        "schema": "cgqa.fcrp-result.v0.2",
        "caseId": case_id,
        "decision": decision,
        "firstMeaningfulDivergence": first_divergence,
        "causePoint": cause,
        "refactorPoint": refactor,
        "navigationDirection": direction,
        "primaryTimeDomain": primary_domain,
        "causalAdvanceRequired": causal_advance_required,
        "simulationStatus": simulation_status,
        "mutationAuthorized": mutation_authorized,
        "evidenceStrengths": dict(sorted(evidence_strengths.items())),
        "localVerification": local,
        "upwardVerification": upward,
        "stopConditionsSatisfied": stop_ok,
        "causalPropagationStopped": stop_values["causalPropagationStopped"],
    }
