"""Deterministic before/after verification for reviewed causal repairs.

CGQ-CAUSAL-001 answers a deliberately narrow question: did a reviewed candidate
change remove the declared failing invariant(s) without regressing declared guard
invariants?

The verifier does not infer causality from source code and does not claim global or
minimal repair. Baseline/candidate assessments and the changed-elements declaration
are evidence inputs. This makes the primitive recursively reusable at function,
contract, protocol, or product scale without overstating what was proved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "causal-repair-v0.1"
RESULT_SCHEMA_VERSION = "causal-repair-result-v0.1"
INVARIANT_ID = "CGQ-CAUSAL-001"
INVARIANT_NAME = "REPAIR_REMOVES_TARGET_WITHOUT_REGRESSION"

_STATUSES = {"pass", "fail", "inconclusive", "not_applicable"}
_MODEL_KEYS = {
    "schemaVersion",
    "repairId",
    "invariantId",
    "change",
    "targetInvariantIds",
    "guardInvariantIds",
    "baseline",
    "candidate",
    "scope",
}
_CHANGE_KEYS = {"changeId", "description", "changedElements"}
_ASSESSMENT_KEYS = {"assessmentId", "evidenceSha256", "invariantResults"}
_RESULT_KEYS = {"invariantId", "status"}


@dataclass(frozen=True, slots=True)
class InvariantResult:
    invariant_id: str
    status: str


@dataclass(frozen=True, slots=True)
class AssessmentSnapshot:
    assessment_id: str
    evidence_sha256: str
    invariant_results: tuple[InvariantResult, ...]


@dataclass(frozen=True, slots=True)
class ReviewedChange:
    change_id: str
    description: str
    changed_elements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalRepairModel:
    repair_id: str
    invariant_id: str
    change: ReviewedChange
    target_invariant_ids: tuple[str, ...]
    guard_invariant_ids: tuple[str, ...]
    baseline: AssessmentSnapshot
    candidate: AssessmentSnapshot
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _unique_texts(value: Any, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    items = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if not allow_empty:
        _require(bool(items), f"{field} must not be empty")
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    _require(len(text) == 64 and all(ch in "0123456789abcdef" for ch in text), f"{field} must be a 64-character hex sha256")
    return text


def _assessment_from_dict(data: Any, field: str) -> AssessmentSnapshot:
    _require(isinstance(data, dict), f"{field} must be an object")
    _reject_extra_keys(data, _ASSESSMENT_KEYS, field)
    missing = sorted(_ASSESSMENT_KEYS - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
    raw_results = data["invariantResults"]
    _require(isinstance(raw_results, list) and raw_results, f"{field}.invariantResults must be a non-empty array")
    results: list[InvariantResult] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_results):
        result_field = f"{field}.invariantResults[{index}]"
        _require(isinstance(raw, dict), f"{result_field} must be an object")
        _reject_extra_keys(raw, _RESULT_KEYS, result_field)
        missing_result = sorted(_RESULT_KEYS - set(raw))
        _require(not missing_result, f"{result_field} missing required fields: {', '.join(missing_result)}")
        invariant_id = _text(raw["invariantId"], f"{result_field}.invariantId")
        _require(invariant_id not in seen, f"duplicate invariantId in {field}: {invariant_id}")
        seen.add(invariant_id)
        status = _text(raw["status"], f"{result_field}.status")
        _require(status in _STATUSES, f"{result_field}.status is unsupported")
        results.append(InvariantResult(invariant_id=invariant_id, status=status))
    return AssessmentSnapshot(
        assessment_id=_text(data["assessmentId"], f"{field}.assessmentId"),
        evidence_sha256=_sha256(data["evidenceSha256"], f"{field}.evidenceSha256"),
        invariant_results=tuple(results),
    )


def causal_repair_model_from_dict(data: dict[str, Any]) -> CausalRepairModel:
    _require(isinstance(data, dict), "causal repair model must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "causal repair model")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "causal repair model missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")
    invariant_id = _text(data["invariantId"], "invariantId")
    _require(invariant_id == INVARIANT_ID, f"invariantId must be {INVARIANT_ID}")

    raw_change = data["change"]
    _require(isinstance(raw_change, dict), "change must be an object")
    _reject_extra_keys(raw_change, _CHANGE_KEYS, "change")
    missing_change = sorted(_CHANGE_KEYS - set(raw_change))
    _require(not missing_change, "change missing required fields: " + ", ".join(missing_change))
    change = ReviewedChange(
        change_id=_text(raw_change["changeId"], "change.changeId"),
        description=_text(raw_change["description"], "change.description"),
        changed_elements=_unique_texts(raw_change["changedElements"], "change.changedElements"),
    )

    targets = _unique_texts(data["targetInvariantIds"], "targetInvariantIds")
    guards = _unique_texts(data["guardInvariantIds"], "guardInvariantIds", allow_empty=True)
    _require(not set(targets).intersection(guards), "targetInvariantIds and guardInvariantIds must be disjoint")

    scope_raw = data.get("scope")
    return CausalRepairModel(
        repair_id=_text(data["repairId"], "repairId"),
        invariant_id=invariant_id,
        change=change,
        target_invariant_ids=targets,
        guard_invariant_ids=guards,
        baseline=_assessment_from_dict(data["baseline"], "baseline"),
        candidate=_assessment_from_dict(data["candidate"], "candidate"),
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_causal_repair_model(path: Path) -> CausalRepairModel:
    with path.open("r", encoding="utf-8") as handle:
        return causal_repair_model_from_dict(json.load(handle))


def causal_repair_model_to_dict(model: CausalRepairModel) -> dict[str, object]:
    def assessment(snapshot: AssessmentSnapshot) -> dict[str, object]:
        return {
            "assessmentId": snapshot.assessment_id,
            "evidenceSha256": snapshot.evidence_sha256,
            "invariantResults": [
                {"invariantId": item.invariant_id, "status": item.status}
                for item in snapshot.invariant_results
            ],
        }

    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "repairId": model.repair_id,
        "invariantId": model.invariant_id,
        "change": {
            "changeId": model.change.change_id,
            "description": model.change.description,
            "changedElements": list(model.change.changed_elements),
        },
        "targetInvariantIds": list(model.target_invariant_ids),
        "guardInvariantIds": list(model.guard_invariant_ids),
        "baseline": assessment(model.baseline),
        "candidate": assessment(model.candidate),
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def causal_repair_model_sha256(model: CausalRepairModel) -> str:
    canonical = json.dumps(causal_repair_model_to_dict(model), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _index(snapshot: AssessmentSnapshot) -> dict[str, str]:
    return {item.invariant_id: item.status for item in snapshot.invariant_results}


def run_causal_repair_model(model: CausalRepairModel) -> dict[str, object]:
    """Compare reviewed baseline/candidate evidence and classify the repair delta."""

    before = _index(model.baseline)
    after = _index(model.candidate)
    required = set(model.target_invariant_ids) | set(model.guard_invariant_ids)
    missing_baseline = sorted(required - set(before))
    missing_candidate = sorted(required - set(after))

    deltas: list[dict[str, str]] = []
    for invariant_id in sorted(set(before) | set(after)):
        old = before.get(invariant_id, "missing")
        new = after.get(invariant_id, "missing")
        if old != new:
            deltas.append({"invariantId": invariant_id, "baseline": old, "candidate": new})

    targets_not_failing_at_baseline = sorted(
        invariant_id for invariant_id in model.target_invariant_ids if before.get(invariant_id) != "fail"
    )
    repaired_targets = sorted(
        invariant_id for invariant_id in model.target_invariant_ids if before.get(invariant_id) == "fail" and after.get(invariant_id) == "pass"
    )
    unresolved_targets = sorted(
        invariant_id for invariant_id in model.target_invariant_ids if after.get(invariant_id) == "fail"
    )
    inconclusive_targets = sorted(
        invariant_id
        for invariant_id in model.target_invariant_ids
        if after.get(invariant_id) in {"inconclusive", "not_applicable"}
    )

    regressions = sorted(
        invariant_id
        for invariant_id in model.guard_invariant_ids
        if before.get(invariant_id) == "pass" and after.get(invariant_id) == "fail"
    )
    weakened_evidence = sorted(
        invariant_id
        for invariant_id in model.guard_invariant_ids
        if before.get(invariant_id) == "pass" and after.get(invariant_id) in {"inconclusive", "not_applicable"}
    )
    invalid_guard_baseline = sorted(
        invariant_id
        for invariant_id in model.guard_invariant_ids
        if before.get(invariant_id) != "pass"
    )

    common_ids = set(before).intersection(after)
    pre_existing_failures = sorted(
        invariant_id for invariant_id in common_ids if before[invariant_id] == "fail" and after[invariant_id] == "fail"
    )
    newly_introduced_failures = sorted(
        invariant_id for invariant_id in common_ids if before[invariant_id] != "fail" and after[invariant_id] == "fail"
    )
    candidate_failures = sorted(invariant_id for invariant_id, status in after.items() if status == "fail")

    structural_inconclusive = bool(
        missing_baseline
        or missing_candidate
        or targets_not_failing_at_baseline
        or inconclusive_targets
        or weakened_evidence
        or invalid_guard_baseline
    )

    if regressions:
        status = "fail"
        classification = "regression"
    elif structural_inconclusive:
        status = "inconclusive"
        classification = "inconclusive"
    elif len(repaired_targets) == len(model.target_invariant_ids):
        status = "pass"
        classification = "verified_repair" if not candidate_failures else "partial_repair"
    else:
        status = "fail"
        classification = "no_effect" if not repaired_targets else "partial_repair"

    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "invariantId": model.invariant_id,
        "invariantName": INVARIANT_NAME,
        "repairId": model.repair_id,
        "modelSha256": causal_repair_model_sha256(model),
        "change": {
            "changeId": model.change.change_id,
            "description": model.change.description,
            "changedElements": list(model.change.changed_elements),
        },
        "baseline": {
            "assessmentId": model.baseline.assessment_id,
            "evidenceSha256": model.baseline.evidence_sha256,
        },
        "candidate": {
            "assessmentId": model.candidate.assessment_id,
            "evidenceSha256": model.candidate.evidence_sha256,
        },
        "targetInvariantIds": list(model.target_invariant_ids),
        "guardInvariantIds": list(model.guard_invariant_ids),
        "repairedTargetInvariantIds": repaired_targets,
        "unresolvedTargetInvariantIds": unresolved_targets,
        "regressedGuardInvariantIds": regressions,
        "weakenedGuardEvidenceInvariantIds": weakened_evidence,
        "preExistingFailureInvariantIds": pre_existing_failures,
        "newFailureInvariantIds": newly_introduced_failures,
        "missingBaselineInvariantIds": missing_baseline,
        "missingCandidateInvariantIds": missing_candidate,
        "deltas": deltas,
        "claimBoundary": (
            "Exact over the supplied reviewed before/after assessment snapshots and changed-elements declaration. "
            "PASS proves that every declared target moved from FAIL to PASS and every declared guard remained PASS. "
            "It does not prove source-level causality, global correctness, repair minimality, or completeness of the declared invariant set."
        ),
    }
