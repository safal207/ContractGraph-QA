"""Evidence-bound fault coverage matrix for Solidity mutation assurance.

This module projects one deterministic Fault-Model Mutation Generator result and
one Mutation Acquisition result into a per-fault-class coverage matrix.

Claim boundaries:
- generation and execution must bind to the exact same mutation plan SHA-256;
- mutation identities, source path/SHA-256, acquisition ID, and fault classes
  must agree exactly;
- a kill rate is emitted only when every generated mutation in that class has a
  conclusive DETECTED/SURVIVED outcome;
- unsupported, unrepresented, or execution-inconclusive classes stay
  INCONCLUSIVE rather than receiving a flattering percentage;
- coverage is exact only over the reviewed/generated mutation challenge set. It
  is not a claim that the fault model is exhaustive or that the contract is safe.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict, mutation_plan_sha256

SCHEMA_VERSION = "fault-coverage-matrix-v0.1"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    _require(len(text) == 64 and all(ch in "0123456789abcdef" for ch in text), f"{field} must be a sha256")
    return text


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _object(value: Any, field: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    _require(isinstance(value, list), f"{field} must be an array")
    return value


def load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    _require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value


def build_fault_coverage_matrix(
    generation: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, object]:
    """Bind generation to execution and summarize evidence by required fault class."""

    generation_schema = _text(generation.get("schemaVersion"), "generation.schemaVersion")
    _require(generation_schema == "fault-mutation-generator-result-v0.1", "unsupported generation schemaVersion")
    execution_schema = _text(execution.get("schemaVersion"), "execution.schemaVersion")
    _require(execution_schema == "solidity-mutation-result-v0.1", "unsupported execution schemaVersion")

    plan_raw = generation.get("mutationPlan")
    _require(isinstance(plan_raw, dict), "generation.mutationPlan must be present")
    plan = mutation_plan_from_dict(plan_raw)
    expected_plan_sha = mutation_plan_sha256(plan)
    execution_plan_sha = _sha256(execution.get("planSha256"), "execution.planSha256")
    _require(execution_plan_sha == expected_plan_sha, "generation and execution mutation-plan SHA-256 differ")

    generation_source_path = _text(generation.get("sourcePath"), "generation.sourcePath")
    execution_source_path = _text(execution.get("sourcePath"), "execution.sourcePath")
    _require(generation_source_path == plan.source_path, "generation source path differs from mutation plan")
    _require(execution_source_path == plan.source_path, "execution source path differs from mutation plan")

    generation_source_sha = _sha256(generation.get("sourceSha256"), "generation.sourceSha256")
    execution_source_sha = _sha256(execution.get("sourceSha256"), "execution.sourceSha256")
    _require(generation_source_sha == plan.source_sha256, "generation source SHA differs from mutation plan")
    _require(execution_source_sha == plan.source_sha256, "execution source SHA differs from mutation plan")

    execution_acquisition_id = _text(execution.get("acquisitionId"), "execution.acquisitionId")
    _require(execution_acquisition_id == plan.acquisition_id, "execution acquisitionId differs from mutation plan")

    generated_ids_raw = _array(generation.get("generatedMutationIds"), "generation.generatedMutationIds")
    generated_ids = [_text(value, f"generation.generatedMutationIds[{index}]") for index, value in enumerate(generated_ids_raw)]
    _require(len(generated_ids) == len(set(generated_ids)), "generation generatedMutationIds must be unique")

    plan_by_id = {item.mutation_id: item for item in plan.mutations}
    _require(set(generated_ids) == set(plan_by_id), "generation mutation IDs differ from mutation plan")

    execution_mutations_raw = _array(execution.get("mutations"), "execution.mutations")
    execution_by_id: dict[str, Mapping[str, Any]] = {}
    for index, raw in enumerate(execution_mutations_raw):
        item = _object(raw, f"execution.mutations[{index}]")
        mutation_id = _text(item.get("mutationId"), f"execution.mutations[{index}].mutationId")
        _require(mutation_id not in execution_by_id, f"duplicate execution mutationId: {mutation_id}")
        execution_by_id[mutation_id] = item
    _require(set(execution_by_id) == set(plan_by_id), "execution mutation IDs differ from mutation plan")

    allowed_results = {"detected", "survived", "inconclusive"}
    normalized: dict[str, tuple[str, str]] = {}
    for mutation_id, spec in plan_by_id.items():
        item = execution_by_id[mutation_id]
        fault_class = _text(item.get("faultClass"), f"execution mutation {mutation_id}.faultClass")
        _require(fault_class == spec.fault_class, f"fault class mismatch for mutation {mutation_id}")
        result = _text(item.get("specAssuranceResult"), f"execution mutation {mutation_id}.specAssuranceResult")
        _require(result in allowed_results, f"unsupported result for mutation {mutation_id}")
        _sha256(item.get("evidenceSha256"), f"execution mutation {mutation_id}.evidenceSha256")
        normalized[mutation_id] = (fault_class, result)

    required_classes = list(plan.required_fault_classes)
    generation_required = generation.get("requiredFaultClasses")
    _require(isinstance(generation_required, list), "generation.requiredFaultClasses must be an array")
    _require(generation_required == required_classes, "generation required fault classes differ from mutation plan")

    unsupported = set(_array(generation.get("unsupportedRequiredFaultClasses", []), "generation.unsupportedRequiredFaultClasses"))
    missing = set(_array(generation.get("missingCandidateFaultClasses", []), "generation.missingCandidateFaultClasses"))
    unbound = set(_array(generation.get("unboundFaultClasses", []), "generation.unboundFaultClasses"))

    discovered_candidates = _array(generation.get("discoveredCandidates", []), "generation.discoveredCandidates")
    discovered_by_class: dict[str, int] = {fault_class: 0 for fault_class in required_classes}
    for index, raw in enumerate(discovered_candidates):
        item = _object(raw, f"generation.discoveredCandidates[{index}]")
        fault_class = _text(item.get("faultClass"), f"generation.discoveredCandidates[{index}].faultClass")
        if fault_class in discovered_by_class:
            discovered_by_class[fault_class] += 1

    rows: list[dict[str, object]] = []
    blind_spot_classes: list[str] = []
    inconclusive_classes: list[str] = []
    covered_classes: list[str] = []

    total_generated = 0
    total_detected = 0
    total_survived = 0
    total_inconclusive = 0

    for fault_class in required_classes:
        class_ids = sorted(mutation_id for mutation_id, (fc, _result) in normalized.items() if fc == fault_class)
        detected_ids = [mutation_id for mutation_id in class_ids if normalized[mutation_id][1] == "detected"]
        survived_ids = [mutation_id for mutation_id in class_ids if normalized[mutation_id][1] == "survived"]
        inconclusive_ids = [mutation_id for mutation_id in class_ids if normalized[mutation_id][1] == "inconclusive"]

        generated_count = len(class_ids)
        detected_count = len(detected_ids)
        survived_count = len(survived_ids)
        inconclusive_count = len(inconclusive_ids)

        total_generated += generated_count
        total_detected += detected_count
        total_survived += survived_count
        total_inconclusive += inconclusive_count

        blocked = fault_class in unsupported or fault_class in missing or fault_class in unbound or generated_count == 0
        complete_execution = generated_count > 0 and inconclusive_count == 0
        kill_rate: float | None = None
        if complete_execution:
            kill_rate = detected_count / generated_count

        if survived_count:
            status = "blind_spot"
            blind_spot_classes.append(fault_class)
        elif blocked or inconclusive_count:
            status = "inconclusive"
            inconclusive_classes.append(fault_class)
            kill_rate = None
        else:
            status = "covered_over_reviewed_mutations"
            covered_classes.append(fault_class)

        rows.append(
            {
                "faultClass": fault_class,
                "status": status,
                "discoveredCandidateCount": discovered_by_class.get(fault_class, 0),
                "generatedMutationCount": generated_count,
                "detectedCount": detected_count,
                "survivedCount": survived_count,
                "inconclusiveCount": inconclusive_count,
                "killRate": kill_rate,
                "detectedMutationIds": detected_ids,
                "survivedMutationIds": survived_ids,
                "inconclusiveMutationIds": inconclusive_ids,
                "generationBlockers": sorted(
                    reason
                    for reason, present in (
                        ("unsupported", fault_class in unsupported),
                        ("no_candidate", fault_class in missing),
                        ("unbound_test", fault_class in unbound),
                    )
                    if present
                ),
            }
        )

    if blind_spot_classes:
        status = "fail"
        classification = "blind_spots_present"
    elif inconclusive_classes:
        status = "inconclusive"
        classification = "incomplete_fault_coverage_evidence"
    else:
        status = "pass"
        classification = "all_reviewed_mutations_detected"

    reviewed_kill_rate: float | None = None
    if total_generated > 0 and total_inconclusive == 0 and not inconclusive_classes:
        reviewed_kill_rate = total_detected / total_generated

    spec = execution.get("specAssurance")
    spec_status = None
    if isinstance(spec, Mapping):
        spec_status = spec.get("status")
        _require(spec_status in {"pass", "fail", "inconclusive"}, "execution.specAssurance.status is invalid")
        if status == "pass":
            _require(spec_status == "pass", "coverage matrix PASS requires CGQ-SPEC-001 PASS")
        if blind_spot_classes:
            _require(spec_status == "fail", "surviving required mutations require CGQ-SPEC-001 FAIL")

    core: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "generationId": _text(generation.get("generationId"), "generation.generationId"),
        "acquisitionId": execution_acquisition_id,
        "sourcePath": plan.source_path,
        "sourceSha256": plan.source_sha256,
        "mutationPlanSha256": expected_plan_sha,
        "requiredFaultClasses": required_classes,
        "coveredFaultClasses": covered_classes,
        "blindSpotFaultClasses": blind_spot_classes,
        "inconclusiveFaultClasses": inconclusive_classes,
        "totals": {
            "discoveredCandidateCount": sum(discovered_by_class.values()),
            "generatedMutationCount": total_generated,
            "detectedCount": total_detected,
            "survivedCount": total_survived,
            "inconclusiveCount": total_inconclusive,
            "reviewedKillRate": reviewed_kill_rate,
        },
        "matrix": rows,
        "specAssuranceStatus": spec_status,
        "claimBoundary": (
            "Exact over one source-bound generated mutation plan and the execution evidence bound to that same plan SHA-256, "
            "source path/SHA-256, acquisition ID, mutation IDs, and fault classes. A class is COVERED only when all generated "
            "reviewed mutations for that class have conclusive DETECTED outcomes. A surviving mutation is a BLIND_SPOT in the "
            "current property/test suite for that reviewed mutation. INCONCLUSIVE classes receive no kill-rate claim. This "
            "matrix does not prove exhaustive fault-model coverage or smart-contract security."
        ),
    }
    result = dict(core)
    result["matrixSha256"] = _canonical_sha256(core)
    return result


def render_fault_coverage_markdown(matrix: Mapping[str, Any]) -> str:
    rows = matrix.get("matrix")
    _require(isinstance(rows, list), "matrix.matrix must be an array")
    lines = [
        "# Fault Coverage Matrix",
        "",
        f"Overall: **{matrix.get('status')}** (`{matrix.get('classification')}`)",
        "",
        "| Fault class | Status | Discovered | Generated | Detected | Survived | Inconclusive | Kill rate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for raw in rows:
        item = _object(raw, "matrix row")
        rate = item.get("killRate")
        rate_text = "—" if rate is None else f"{float(rate) * 100:.1f}%"
        lines.append(
            "| {fault} | {status} | {disc} | {gen} | {det} | {surv} | {inc} | {rate} |".format(
                fault=item.get("faultClass"),
                status=item.get("status"),
                disc=item.get("discoveredCandidateCount"),
                gen=item.get("generatedMutationCount"),
                det=item.get("detectedCount"),
                surv=item.get("survivedCount"),
                inc=item.get("inconclusiveCount"),
                rate=rate_text,
            )
        )
    lines.extend(
        [
            "",
            f"Mutation plan SHA-256: `{matrix.get('mutationPlanSha256')}`",
            f"Matrix SHA-256: `{matrix.get('matrixSha256')}`",
            "",
            str(matrix.get("claimBoundary", "")),
            "",
        ]
    )
    return "\n".join(lines)
