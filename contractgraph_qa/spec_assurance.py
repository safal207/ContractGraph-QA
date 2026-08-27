"""Deterministic assurance checks for reviewed smart-contract specifications.

CGQ-SPEC-001 asks whether one declared property is demonstrably active on the
baseline and sensitive to every mutation in a reviewed fault model.

The verifier does not generate Solidity mutations, execute a fuzzer, or infer that
a fault class is complete. Activation witnesses and mutation outcomes are evidence
inputs. This keeps the result exact over the supplied challenge set without turning
a mutation score into a security certification.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "spec-assurance-v0.1"
RESULT_SCHEMA_VERSION = "spec-assurance-result-v0.1"
ASSURANCE_INVARIANT_ID = "CGQ-SPEC-001"
ASSURANCE_INVARIANT_NAME = "PROPERTY_DETECTS_REVIEWED_FAULT_MODEL"

_BASELINE_STATUSES = {"pass", "fail", "inconclusive"}
_MUTATION_RESULTS = {"detected", "survived", "inconclusive"}
_MODEL_KEYS = {
    "schemaVersion",
    "assuranceId",
    "assuranceInvariantId",
    "propertyInvariantId",
    "propertyDescription",
    "baseline",
    "activationWitness",
    "requiredFaultClasses",
    "mutations",
    "scope",
}
_BASELINE_KEYS = {"assessmentId", "evidenceSha256", "status"}
_ACTIVATION_KEYS = {"observed", "evidenceSha256", "description"}
_MUTATION_KEYS = {
    "mutationId",
    "description",
    "faultClass",
    "evidenceSha256",
    "result",
}


@dataclass(frozen=True, slots=True)
class BaselineAssessment:
    assessment_id: str
    evidence_sha256: str
    status: str


@dataclass(frozen=True, slots=True)
class ActivationWitness:
    observed: bool
    evidence_sha256: str
    description: str


@dataclass(frozen=True, slots=True)
class MutationChallenge:
    mutation_id: str
    description: str
    fault_class: str
    evidence_sha256: str
    result: str


@dataclass(frozen=True, slots=True)
class SpecAssuranceModel:
    assurance_id: str
    property_invariant_id: str
    property_description: str
    baseline: BaselineAssessment
    activation_witness: ActivationWitness
    required_fault_classes: tuple[str, ...]
    mutations: tuple[MutationChallenge, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    _require(
        len(text) == 64 and all(ch in "0123456789abcdef" for ch in text),
        f"{field} must be a 64-character hex sha256",
    )
    return text


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _unique_texts(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty array")
    items = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def spec_assurance_model_from_dict(data: dict[str, Any]) -> SpecAssuranceModel:
    _require(isinstance(data, dict), "spec assurance model must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "spec assurance model")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "spec assurance model missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")
    _require(
        data["assuranceInvariantId"] == ASSURANCE_INVARIANT_ID,
        f"assuranceInvariantId must be {ASSURANCE_INVARIANT_ID}",
    )

    raw_baseline = data["baseline"]
    _require(isinstance(raw_baseline, dict), "baseline must be an object")
    _reject_extra_keys(raw_baseline, _BASELINE_KEYS, "baseline")
    missing_baseline = sorted(_BASELINE_KEYS - set(raw_baseline))
    _require(not missing_baseline, "baseline missing required fields: " + ", ".join(missing_baseline))
    baseline_status = _text(raw_baseline["status"], "baseline.status")
    _require(baseline_status in _BASELINE_STATUSES, "baseline.status is unsupported")
    baseline = BaselineAssessment(
        assessment_id=_text(raw_baseline["assessmentId"], "baseline.assessmentId"),
        evidence_sha256=_sha256(raw_baseline["evidenceSha256"], "baseline.evidenceSha256"),
        status=baseline_status,
    )

    raw_activation = data["activationWitness"]
    _require(isinstance(raw_activation, dict), "activationWitness must be an object")
    _reject_extra_keys(raw_activation, _ACTIVATION_KEYS, "activationWitness")
    missing_activation = sorted(_ACTIVATION_KEYS - set(raw_activation))
    _require(not missing_activation, "activationWitness missing required fields: " + ", ".join(missing_activation))
    observed = raw_activation["observed"]
    _require(isinstance(observed, bool), "activationWitness.observed must be a boolean")
    activation = ActivationWitness(
        observed=observed,
        evidence_sha256=_sha256(raw_activation["evidenceSha256"], "activationWitness.evidenceSha256"),
        description=_text(raw_activation["description"], "activationWitness.description"),
    )

    required_fault_classes = _unique_texts(data["requiredFaultClasses"], "requiredFaultClasses")

    raw_mutations = data["mutations"]
    _require(isinstance(raw_mutations, list) and raw_mutations, "mutations must be a non-empty array")
    mutations: list[MutationChallenge] = []
    mutation_ids: set[str] = set()
    for index, raw in enumerate(raw_mutations):
        field = f"mutations[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _MUTATION_KEYS, field)
        missing_mutation = sorted(_MUTATION_KEYS - set(raw))
        _require(not missing_mutation, f"{field} missing required fields: {', '.join(missing_mutation)}")
        mutation_id = _text(raw["mutationId"], f"{field}.mutationId")
        _require(mutation_id not in mutation_ids, f"duplicate mutationId: {mutation_id}")
        mutation_ids.add(mutation_id)
        result = _text(raw["result"], f"{field}.result")
        _require(result in _MUTATION_RESULTS, f"{field}.result is unsupported")
        mutations.append(
            MutationChallenge(
                mutation_id=mutation_id,
                description=_text(raw["description"], f"{field}.description"),
                fault_class=_text(raw["faultClass"], f"{field}.faultClass"),
                evidence_sha256=_sha256(raw["evidenceSha256"], f"{field}.evidenceSha256"),
                result=result,
            )
        )

    scope_raw = data.get("scope")
    return SpecAssuranceModel(
        assurance_id=_text(data["assuranceId"], "assuranceId"),
        property_invariant_id=_text(data["propertyInvariantId"], "propertyInvariantId"),
        property_description=_text(data["propertyDescription"], "propertyDescription"),
        baseline=baseline,
        activation_witness=activation,
        required_fault_classes=required_fault_classes,
        mutations=tuple(mutations),
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_spec_assurance_model(path: Path) -> SpecAssuranceModel:
    with path.open("r", encoding="utf-8") as handle:
        return spec_assurance_model_from_dict(json.load(handle))


def spec_assurance_model_to_dict(model: SpecAssuranceModel) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "assuranceId": model.assurance_id,
        "assuranceInvariantId": ASSURANCE_INVARIANT_ID,
        "propertyInvariantId": model.property_invariant_id,
        "propertyDescription": model.property_description,
        "baseline": {
            "assessmentId": model.baseline.assessment_id,
            "evidenceSha256": model.baseline.evidence_sha256,
            "status": model.baseline.status,
        },
        "activationWitness": {
            "observed": model.activation_witness.observed,
            "evidenceSha256": model.activation_witness.evidence_sha256,
            "description": model.activation_witness.description,
        },
        "requiredFaultClasses": list(model.required_fault_classes),
        "mutations": [
            {
                "mutationId": item.mutation_id,
                "description": item.description,
                "faultClass": item.fault_class,
                "evidenceSha256": item.evidence_sha256,
                "result": item.result,
            }
            for item in model.mutations
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def spec_assurance_model_sha256(model: SpecAssuranceModel) -> str:
    canonical = json.dumps(
        spec_assurance_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_spec_assurance_model(model: SpecAssuranceModel) -> dict[str, object]:
    """Evaluate non-vacuity evidence and sensitivity to a reviewed mutation set."""

    required_classes = set(model.required_fault_classes)
    represented_classes = {item.fault_class for item in model.mutations}
    unrepresented_classes = sorted(required_classes - represented_classes)

    detected = sorted(item.mutation_id for item in model.mutations if item.result == "detected")
    survived = sorted(item.mutation_id for item in model.mutations if item.result == "survived")
    inconclusive = sorted(item.mutation_id for item in model.mutations if item.result == "inconclusive")

    required_mutations = [item for item in model.mutations if item.fault_class in required_classes]
    required_detected = [item for item in required_mutations if item.result == "detected"]
    required_survived = sorted(item.mutation_id for item in required_mutations if item.result == "survived")
    required_inconclusive = sorted(item.mutation_id for item in required_mutations if item.result == "inconclusive")

    mutation_score = len(required_detected) / len(required_mutations) if required_mutations else 0.0
    baseline_ready = model.baseline.status == "pass"
    activation_ready = model.activation_witness.observed

    if required_survived:
        status = "fail"
        classification = "weak_specification"
    elif not baseline_ready or not activation_ready or unrepresented_classes or required_inconclusive:
        status = "inconclusive"
        classification = "inconclusive"
    else:
        status = "pass"
        classification = "assured_over_reviewed_fault_model"

    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "assuranceInvariantId": ASSURANCE_INVARIANT_ID,
        "assuranceInvariantName": ASSURANCE_INVARIANT_NAME,
        "assuranceId": model.assurance_id,
        "propertyInvariantId": model.property_invariant_id,
        "propertyDescription": model.property_description,
        "modelSha256": spec_assurance_model_sha256(model),
        "baseline": {
            "assessmentId": model.baseline.assessment_id,
            "evidenceSha256": model.baseline.evidence_sha256,
            "status": model.baseline.status,
        },
        "activationWitness": {
            "observed": model.activation_witness.observed,
            "evidenceSha256": model.activation_witness.evidence_sha256,
            "description": model.activation_witness.description,
        },
        "requiredFaultClasses": list(model.required_fault_classes),
        "representedFaultClasses": sorted(required_classes.intersection(represented_classes)),
        "unrepresentedRequiredFaultClasses": unrepresented_classes,
        "mutationCount": len(model.mutations),
        "requiredMutationCount": len(required_mutations),
        "detectedMutationIds": detected,
        "survivedMutationIds": survived,
        "inconclusiveMutationIds": inconclusive,
        "requiredSurvivedMutationIds": required_survived,
        "requiredInconclusiveMutationIds": required_inconclusive,
        "mutationScore": mutation_score,
        "claimBoundary": (
            "Exact over the supplied baseline assessment, activation witness, reviewed fault-class declaration, "
            "and per-mutation evidence outcomes. PASS means the property was observed active on a passing baseline "
            "and detected every supplied mutation belonging to every represented required fault class. It does not "
            "prove that the fault model is complete, that mutation generation was exhaustive, or that the target "
            "contract is secure."
        ),
    }
