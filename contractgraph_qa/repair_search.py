"""Deterministic minimal repair selection over reviewed candidate-set evidence.

CGQ-CAUSAL-002 does not synthesize patches or infer the effect of combining changes.
Each candidate set must carry its own reviewed assessment snapshot. The verifier then
selects the smallest candidate set that repairs all declared targets without weakening
declared guards or introducing a new failure in the supplied comparable evidence.

"Minimal" therefore means minimal by repair-count among the reviewed candidate sets
supplied to this model, not globally minimal over all possible source-code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "repair-search-v0.1"
RESULT_SCHEMA_VERSION = "repair-search-result-v0.1"
INVARIANT_ID = "CGQ-CAUSAL-002"
INVARIANT_NAME = "MINIMAL_VERIFIED_REPAIR_AMONG_REVIEWED_CANDIDATES"

_STATUSES = {"pass", "fail", "inconclusive", "not_applicable"}
_MODEL_KEYS = {
    "schemaVersion",
    "searchId",
    "invariantId",
    "targetInvariantIds",
    "guardInvariantIds",
    "baseline",
    "repairs",
    "candidateSets",
    "scope",
}
_REPAIR_KEYS = {"repairId", "description", "changedElements"}
_CANDIDATE_KEYS = {"candidateSetId", "repairIds", "assessment"}
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
class RepairCandidate:
    repair_id: str
    description: str
    changed_elements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateSet:
    candidate_set_id: str
    repair_ids: tuple[str, ...]
    assessment: AssessmentSnapshot


@dataclass(frozen=True, slots=True)
class RepairSearchModel:
    search_id: str
    invariant_id: str
    target_invariant_ids: tuple[str, ...]
    guard_invariant_ids: tuple[str, ...]
    baseline: AssessmentSnapshot
    repairs: tuple[RepairCandidate, ...]
    candidate_sets: tuple[CandidateSet, ...]
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
    _require(
        len(text) == 64 and all(ch in "0123456789abcdef" for ch in text),
        f"{field} must be a 64-character hex sha256",
    )
    return text


def _assessment_from_dict(data: Any, field: str) -> AssessmentSnapshot:
    _require(isinstance(data, dict), f"{field} must be an object")
    _reject_extra_keys(data, _ASSESSMENT_KEYS, field)
    missing = sorted(_ASSESSMENT_KEYS - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
    raw_results = data["invariantResults"]
    _require(
        isinstance(raw_results, list) and raw_results,
        f"{field}.invariantResults must be a non-empty array",
    )
    results: list[InvariantResult] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_results):
        result_field = f"{field}.invariantResults[{index}]"
        _require(isinstance(raw, dict), f"{result_field} must be an object")
        _reject_extra_keys(raw, _RESULT_KEYS, result_field)
        missing_result = sorted(_RESULT_KEYS - set(raw))
        _require(
            not missing_result,
            f"{result_field} missing required fields: {', '.join(missing_result)}",
        )
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


def repair_search_model_from_dict(data: dict[str, Any]) -> RepairSearchModel:
    _require(isinstance(data, dict), "repair search model must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "repair search model")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "repair search model missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")
    invariant_id = _text(data["invariantId"], "invariantId")
    _require(invariant_id == INVARIANT_ID, f"invariantId must be {INVARIANT_ID}")

    targets = _unique_texts(data["targetInvariantIds"], "targetInvariantIds")
    guards = _unique_texts(data["guardInvariantIds"], "guardInvariantIds", allow_empty=True)
    _require(not set(targets).intersection(guards), "targetInvariantIds and guardInvariantIds must be disjoint")

    raw_repairs = data["repairs"]
    _require(isinstance(raw_repairs, list) and raw_repairs, "repairs must be a non-empty array")
    repairs: list[RepairCandidate] = []
    repair_ids: set[str] = set()
    for index, raw in enumerate(raw_repairs):
        field = f"repairs[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _REPAIR_KEYS, field)
        missing_repair = sorted(_REPAIR_KEYS - set(raw))
        _require(not missing_repair, f"{field} missing required fields: {', '.join(missing_repair)}")
        repair_id = _text(raw["repairId"], f"{field}.repairId")
        _require(repair_id not in repair_ids, f"duplicate repairId: {repair_id}")
        repair_ids.add(repair_id)
        repairs.append(
            RepairCandidate(
                repair_id=repair_id,
                description=_text(raw["description"], f"{field}.description"),
                changed_elements=_unique_texts(raw["changedElements"], f"{field}.changedElements"),
            )
        )

    raw_sets = data["candidateSets"]
    _require(isinstance(raw_sets, list) and raw_sets, "candidateSets must be a non-empty array")
    candidate_sets: list[CandidateSet] = []
    seen_set_ids: set[str] = set()
    seen_compositions: set[tuple[str, ...]] = set()
    for index, raw in enumerate(raw_sets):
        field = f"candidateSets[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _CANDIDATE_KEYS, field)
        missing_candidate = sorted(_CANDIDATE_KEYS - set(raw))
        _require(not missing_candidate, f"{field} missing required fields: {', '.join(missing_candidate)}")
        candidate_set_id = _text(raw["candidateSetId"], f"{field}.candidateSetId")
        _require(candidate_set_id not in seen_set_ids, f"duplicate candidateSetId: {candidate_set_id}")
        seen_set_ids.add(candidate_set_id)
        candidate_repair_ids = _unique_texts(raw["repairIds"], f"{field}.repairIds")
        unknown = sorted(set(candidate_repair_ids) - repair_ids)
        _require(not unknown, f"{field}.repairIds reference unknown repairs: {', '.join(unknown)}")
        composition = tuple(sorted(candidate_repair_ids))
        _require(composition not in seen_compositions, f"duplicate candidate repair composition: {composition}")
        seen_compositions.add(composition)
        candidate_sets.append(
            CandidateSet(
                candidate_set_id=candidate_set_id,
                repair_ids=candidate_repair_ids,
                assessment=_assessment_from_dict(raw["assessment"], f"{field}.assessment"),
            )
        )

    scope_raw = data.get("scope")
    return RepairSearchModel(
        search_id=_text(data["searchId"], "searchId"),
        invariant_id=invariant_id,
        target_invariant_ids=targets,
        guard_invariant_ids=guards,
        baseline=_assessment_from_dict(data["baseline"], "baseline"),
        repairs=tuple(repairs),
        candidate_sets=tuple(candidate_sets),
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_repair_search_model(path: Path) -> RepairSearchModel:
    with path.open("r", encoding="utf-8") as handle:
        return repair_search_model_from_dict(json.load(handle))


def repair_search_model_to_dict(model: RepairSearchModel) -> dict[str, object]:
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
        "searchId": model.search_id,
        "invariantId": model.invariant_id,
        "targetInvariantIds": list(model.target_invariant_ids),
        "guardInvariantIds": list(model.guard_invariant_ids),
        "baseline": assessment(model.baseline),
        "repairs": [
            {
                "repairId": item.repair_id,
                "description": item.description,
                "changedElements": list(item.changed_elements),
            }
            for item in model.repairs
        ],
        "candidateSets": [
            {
                "candidateSetId": item.candidate_set_id,
                "repairIds": list(item.repair_ids),
                "assessment": assessment(item.assessment),
            }
            for item in model.candidate_sets
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def repair_search_model_sha256(model: RepairSearchModel) -> str:
    canonical = json.dumps(
        repair_search_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _index(snapshot: AssessmentSnapshot) -> dict[str, str]:
    return {item.invariant_id: item.status for item in snapshot.invariant_results}


def run_repair_search_model(model: RepairSearchModel) -> dict[str, object]:
    """Select minimal verified repairs among explicitly assessed candidate sets."""

    before = _index(model.baseline)
    required = set(model.target_invariant_ids) | set(model.guard_invariant_ids)
    missing_baseline = sorted(required - set(before))
    invalid_target_baseline = sorted(
        invariant_id for invariant_id in model.target_invariant_ids if before.get(invariant_id) != "fail"
    )
    invalid_guard_baseline = sorted(
        invariant_id for invariant_id in model.guard_invariant_ids if before.get(invariant_id) != "pass"
    )
    baseline_valid = not (missing_baseline or invalid_target_baseline or invalid_guard_baseline)

    repair_by_id = {item.repair_id: item for item in model.repairs}
    evaluations: list[dict[str, object]] = []
    eligible: list[dict[str, object]] = []

    for candidate in sorted(model.candidate_sets, key=lambda item: item.candidate_set_id):
        after = _index(candidate.assessment)
        missing = sorted(required - set(after))
        unresolved_targets = sorted(
            invariant_id for invariant_id in model.target_invariant_ids if after.get(invariant_id) == "fail"
        )
        uncertain_targets = sorted(
            invariant_id
            for invariant_id in model.target_invariant_ids
            if after.get(invariant_id) in {None, "inconclusive", "not_applicable"}
        )
        guard_regressions = sorted(
            invariant_id
            for invariant_id in model.guard_invariant_ids
            if before.get(invariant_id) == "pass" and after.get(invariant_id) == "fail"
        )
        weakened_guards = sorted(
            invariant_id
            for invariant_id in model.guard_invariant_ids
            if before.get(invariant_id) == "pass" and after.get(invariant_id) in {None, "inconclusive", "not_applicable"}
        )
        common = set(before).intersection(after)
        new_failures = sorted(
            invariant_id
            for invariant_id in common
            if before[invariant_id] != "fail" and after[invariant_id] == "fail"
        )
        weakened_existing_passes = sorted(
            invariant_id
            for invariant_id in common
            if before[invariant_id] == "pass" and after[invariant_id] in {"inconclusive", "not_applicable"}
        )
        repaired_targets = sorted(
            invariant_id
            for invariant_id in model.target_invariant_ids
            if before.get(invariant_id) == "fail" and after.get(invariant_id) == "pass"
        )

        if not baseline_valid or missing or uncertain_targets or weakened_guards or weakened_existing_passes:
            classification = "inconclusive"
            candidate_status = "inconclusive"
        elif guard_regressions or new_failures:
            classification = "regression"
            candidate_status = "fail"
        elif unresolved_targets:
            classification = "partial_repair" if repaired_targets else "no_effect"
            candidate_status = "fail"
        elif len(repaired_targets) == len(model.target_invariant_ids):
            classification = "verified_repair"
            candidate_status = "pass"
        else:
            classification = "inconclusive"
            candidate_status = "inconclusive"

        changed_elements = sorted(
            {
                element
                for repair_id in candidate.repair_ids
                for element in repair_by_id[repair_id].changed_elements
            }
        )
        evaluation: dict[str, object] = {
            "candidateSetId": candidate.candidate_set_id,
            "repairIds": list(candidate.repair_ids),
            "repairCount": len(candidate.repair_ids),
            "changedElementCount": len(changed_elements),
            "changedElements": changed_elements,
            "assessmentId": candidate.assessment.assessment_id,
            "evidenceSha256": candidate.assessment.evidence_sha256,
            "status": candidate_status,
            "classification": classification,
            "repairedTargetInvariantIds": repaired_targets,
            "unresolvedTargetInvariantIds": unresolved_targets,
            "regressedGuardInvariantIds": guard_regressions,
            "newFailureInvariantIds": new_failures,
            "weakenedEvidenceInvariantIds": sorted(set(weakened_guards) | set(weakened_existing_passes)),
            "missingInvariantIds": missing,
        }
        evaluations.append(evaluation)
        if candidate_status == "pass":
            eligible.append(evaluation)

    if not baseline_valid:
        status = "inconclusive"
        classification = "inconclusive"
        minimum_repair_count = None
        minimal_candidates: list[dict[str, object]] = []
        selected = None
    elif not eligible:
        any_inconclusive = any(item["status"] == "inconclusive" for item in evaluations)
        status = "inconclusive" if any_inconclusive else "fail"
        classification = "inconclusive" if any_inconclusive else "no_verified_repair"
        minimum_repair_count = None
        minimal_candidates = []
        selected = None
    else:
        minimum_repair_count = min(int(item["repairCount"]) for item in eligible)
        minimal_candidates = [
            item for item in eligible if int(item["repairCount"]) == minimum_repair_count
        ]
        minimal_candidates.sort(
            key=lambda item: (int(item["changedElementCount"]), str(item["candidateSetId"]))
        )
        selected = minimal_candidates[0]
        status = "pass"
        classification = "minimal_verified_repair"

    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "invariantId": model.invariant_id,
        "invariantName": INVARIANT_NAME,
        "searchId": model.search_id,
        "modelSha256": repair_search_model_sha256(model),
        "baseline": {
            "assessmentId": model.baseline.assessment_id,
            "evidenceSha256": model.baseline.evidence_sha256,
        },
        "targetInvariantIds": list(model.target_invariant_ids),
        "guardInvariantIds": list(model.guard_invariant_ids),
        "repairCatalog": [
            {
                "repairId": item.repair_id,
                "description": item.description,
                "changedElements": list(item.changed_elements),
            }
            for item in model.repairs
        ],
        "evaluatedCandidateSetCount": len(evaluations),
        "verifiedCandidateSetCount": len(eligible),
        "minimumRepairCount": minimum_repair_count,
        "minimalVerifiedCandidates": minimal_candidates,
        "selectedRepair": selected,
        "candidateEvaluations": evaluations,
        "missingBaselineInvariantIds": missing_baseline,
        "invalidTargetBaselineInvariantIds": invalid_target_baseline,
        "invalidGuardBaselineInvariantIds": invalid_guard_baseline,
        "claimBoundary": (
            "Exact over the supplied reviewed baseline and candidate-set assessment snapshots. "
            "MINIMAL_VERIFIED_REPAIR means minimum repair-count only among candidate sets explicitly supplied and independently assessed. "
            "The verifier does not synthesize patches, infer combined effects from single-repair evidence, prove global source-level minimality, "
            "or prove completeness of the candidate search space or invariant set."
        ),
    }
