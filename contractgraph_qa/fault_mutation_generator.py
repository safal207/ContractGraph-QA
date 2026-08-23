"""Deterministic Solidity fault-model mutation generation.

The generator scans exact reviewed source bytes with a deliberately small set of
syntax-local operators and emits a source-bound Mutation Acquisition v0.1 plan.
It does not infer vulnerabilities, business intent, or fault-model completeness.

v0.1 supports four classes with compile-preserving line mutations:
- authorization: remove msg.sender deny guards;
- state_transition: remove state guards or state writes;
- time_boundary: remove block.timestamp deny guards;
- accounting: remove amount/balance/share/supply/debt/fee/reserve writes.

Replay/version and units/decimals are intentionally reported unsupported in v0.1;
those require semantic/AST-aware operators rather than unsafe regex guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict

SCHEMA_VERSION = "fault-mutation-generator-v0.1"
RESULT_SCHEMA_VERSION = "fault-mutation-generator-result-v0.1"

SUPPORTED_FAULT_CLASSES = (
    "authorization",
    "state_transition",
    "time_boundary",
    "accounting",
)
KNOWN_UNSUPPORTED_FAULT_CLASSES = (
    "replay_version",
    "units_decimals",
)

_MODEL_KEYS = {
    "schemaVersion",
    "generationId",
    "sourcePath",
    "sourceSha256",
    "propertyInvariantId",
    "propertyDescription",
    "activationWitness",
    "requiredFaultClasses",
    "foundry",
    "testBindings",
    "maxMutationsPerFaultClass",
    "scope",
}
_ACTIVATION_KEYS = {"observed", "evidenceSha256", "description"}
_FOUNDRY_KEYS = {"profile", "timeoutSeconds"}
_BINDING_KEYS = {"faultClass", "function", "matchPath", "matchTest"}
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9._-]+")
_FUNCTION_RE = re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_AUTH_GUARD_RE = re.compile(r"^\s*if\s*\(\s*msg\.sender\s*!=.+\)\s*revert\s+[^;]+;\s*(?://.*)?$")
_STATE_GUARD_RE = re.compile(r"^\s*if\s*\(\s*state\s*!=.+\)\s*revert\s+[^;]+;\s*(?://.*)?$")
_TIME_GUARD_RE = re.compile(r"^\s*if\s*\([^\n]*block\.timestamp[^\n]*\)\s*revert\s+[^;]+;\s*(?://.*)?$")
_STATE_WRITE_RE = re.compile(r"^\s*state\s*=\s*State\.[A-Za-z_][A-Za-z0-9_]*\s*;\s*(?://.*)?$")
_ACCOUNTING_WRITE_RE = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*(?:Amount|Balance|Shares|Supply|Debt|Fee|Reserve)[A-Za-z0-9_]*\s*=\s*.+;\s*(?://.*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ActivationEvidence:
    observed: bool
    evidence_sha256: str
    description: str


@dataclass(frozen=True, slots=True)
class FoundryConfig:
    profile: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class TestBinding:
    fault_class: str
    function: str
    match_path: str
    match_test: str


@dataclass(frozen=True, slots=True)
class FaultMutationGeneratorConfig:
    generation_id: str
    source_path: str
    source_sha256: str
    property_invariant_id: str
    property_description: str
    activation_witness: ActivationEvidence
    required_fault_classes: tuple[str, ...]
    foundry: FoundryConfig
    test_bindings: tuple[TestBinding, ...]
    max_mutations_per_fault_class: int
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _safe_id(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_SAFE_ID_RE.fullmatch(text)), f"{field} contains unsafe characters")
    return text


def _relative_path(value: Any, field: str) -> str:
    text = _text(value, field)
    path = Path(text)
    _require(not path.is_absolute(), f"{field} must be relative")
    _require(".." not in path.parts, f"{field} must not traverse parent directories")
    return path.as_posix()


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    _require(len(text) == 64 and all(ch in "0123456789abcdef" for ch in text), f"{field} must be a 64-character hex sha256")
    return text


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _unique_texts(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty array")
    items = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def generator_config_from_dict(data: dict[str, Any]) -> FaultMutationGeneratorConfig:
    _require(isinstance(data, dict), "fault mutation generator config must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "fault mutation generator config")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "fault mutation generator config missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")

    activation_raw = data["activationWitness"]
    _require(isinstance(activation_raw, dict), "activationWitness must be an object")
    _reject_extra_keys(activation_raw, _ACTIVATION_KEYS, "activationWitness")
    _require(_ACTIVATION_KEYS <= set(activation_raw), "activationWitness missing required fields")
    observed = activation_raw["observed"]
    _require(isinstance(observed, bool), "activationWitness.observed must be a boolean")
    activation = ActivationEvidence(
        observed=observed,
        evidence_sha256=_sha256(activation_raw["evidenceSha256"], "activationWitness.evidenceSha256"),
        description=_text(activation_raw["description"], "activationWitness.description"),
    )

    foundry_raw = data["foundry"]
    _require(isinstance(foundry_raw, dict), "foundry must be an object")
    _reject_extra_keys(foundry_raw, _FOUNDRY_KEYS, "foundry")
    _require(_FOUNDRY_KEYS <= set(foundry_raw), "foundry missing required fields")
    timeout = foundry_raw["timeoutSeconds"]
    _require(isinstance(timeout, int) and not isinstance(timeout, bool) and 1 <= timeout <= 3600, "foundry.timeoutSeconds must be an integer from 1 to 3600")
    foundry = FoundryConfig(
        profile=_safe_id(foundry_raw["profile"], "foundry.profile"),
        timeout_seconds=timeout,
    )

    bindings_raw = data["testBindings"]
    _require(isinstance(bindings_raw, list) and bindings_raw, "testBindings must be a non-empty array")
    bindings: list[TestBinding] = []
    binding_keys: set[tuple[str, str]] = set()
    for index, raw in enumerate(bindings_raw):
        field = f"testBindings[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _BINDING_KEYS, field)
        _require(_BINDING_KEYS <= set(raw), f"{field} missing required fields")
        binding = TestBinding(
            fault_class=_text(raw["faultClass"], f"{field}.faultClass"),
            function=_text(raw["function"], f"{field}.function"),
            match_path=_relative_path(raw["matchPath"], f"{field}.matchPath"),
            match_test=_text(raw["matchTest"], f"{field}.matchTest"),
        )
        key = (binding.fault_class, binding.function)
        _require(key not in binding_keys, f"duplicate test binding for {binding.fault_class}/{binding.function}")
        binding_keys.add(key)
        bindings.append(binding)

    max_mutations = data["maxMutationsPerFaultClass"]
    _require(isinstance(max_mutations, int) and not isinstance(max_mutations, bool) and 1 <= max_mutations <= 50, "maxMutationsPerFaultClass must be an integer from 1 to 50")

    scope_raw = data.get("scope")
    return FaultMutationGeneratorConfig(
        generation_id=_safe_id(data["generationId"], "generationId"),
        source_path=_relative_path(data["sourcePath"], "sourcePath"),
        source_sha256=_sha256(data["sourceSha256"], "sourceSha256"),
        property_invariant_id=_text(data["propertyInvariantId"], "propertyInvariantId"),
        property_description=_text(data["propertyDescription"], "propertyDescription"),
        activation_witness=activation,
        required_fault_classes=_unique_texts(data["requiredFaultClasses"], "requiredFaultClasses"),
        foundry=foundry,
        test_bindings=tuple(bindings),
        max_mutations_per_fault_class=max_mutations,
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_generator_config(path: Path) -> FaultMutationGeneratorConfig:
    with path.open("r", encoding="utf-8") as handle:
        return generator_config_from_dict(json.load(handle))


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _binding_for(config: FaultMutationGeneratorConfig, fault_class: str, function_name: str) -> TestBinding | None:
    exact = [item for item in config.test_bindings if item.fault_class == fault_class and item.function == function_name]
    if exact:
        return exact[0]
    wildcard = [item for item in config.test_bindings if item.fault_class == fault_class and item.function == "*"]
    return wildcard[0] if wildcard else None


def _comment_replacement(line: str, operator_id: str) -> str:
    indent = line[: len(line) - len(line.lstrip())]
    newline = "\n" if line.endswith("\n") else ""
    return f"{indent}// CGQA auto-mutation {operator_id}: removed reviewed statement{newline}"


def _operator_for_line(line: str) -> tuple[str, str, str] | None:
    bare = line.rstrip("\n")
    if _TIME_GUARD_RE.match(bare):
        return ("TIME_GUARD_REMOVE", "time_boundary", "Remove a block.timestamp deny guard")
    if _AUTH_GUARD_RE.match(bare):
        return ("AUTH_GUARD_REMOVE", "authorization", "Remove a msg.sender authorization deny guard")
    if _STATE_GUARD_RE.match(bare):
        return ("STATE_GUARD_REMOVE", "state_transition", "Remove a state-transition deny guard")
    if _STATE_WRITE_RE.match(bare):
        return ("STATE_WRITE_DROP", "state_transition", "Remove a state transition write")
    if _ACCOUNTING_WRITE_RE.match(bare):
        return ("ACCOUNTING_WRITE_DROP", "accounting", "Remove an economic/accounting state write")
    return None


def _function_by_line(source: str) -> list[str]:
    lines = source.splitlines(keepends=True)
    current = "<contract>"
    depth = 0
    function_depth: int | None = None
    result: list[str] = []
    for line in lines:
        function_match = _FUNCTION_RE.search(line)
        if function_match and function_depth is None:
            current = function_match.group(1)
            function_depth = depth + line.count("{") - line.count("}")
        result.append(current)
        depth += line.count("{") - line.count("}")
        if function_depth is not None and depth < function_depth:
            current = "<contract>"
            function_depth = None
    return result


def generate_fault_mutation_plan(config: FaultMutationGeneratorConfig, project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    _require(root.is_dir(), "project root must be a directory")
    source_path = (root / config.source_path).resolve()
    try:
        source_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("sourcePath escapes project root") from exc
    _require(source_path.is_file(), f"source file not found: {config.source_path}")
    source_bytes = source_path.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    _require(actual_sha == config.source_sha256, "sourceSha256 does not match exact source bytes")
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source file must be UTF-8") from exc

    lines = source.splitlines(keepends=True)
    functions = _function_by_line(source)
    required = set(config.required_fault_classes)
    supported_required = sorted(required.intersection(SUPPORTED_FAULT_CLASSES))
    unsupported_required = sorted(required - set(SUPPORTED_FAULT_CLASSES))

    discovered: list[dict[str, object]] = []
    ambiguous: list[dict[str, object]] = []
    generated: list[dict[str, object]] = []
    per_class_count: dict[str, int] = {item: 0 for item in required}
    unbound_classes: set[str] = set()

    for index, line in enumerate(lines, start=1):
        operator = _operator_for_line(line)
        if operator is None:
            continue
        operator_id, fault_class, description = operator
        if fault_class not in required:
            continue
        function_name = functions[index - 1]
        candidate_id = f"auto-{operator_id.lower().replace('_', '-')}-L{index}"
        candidate = {
            "mutationId": candidate_id,
            "operatorId": operator_id,
            "faultClass": fault_class,
            "function": function_name,
            "line": index,
            "description": description,
        }
        discovered.append(candidate)
        if source.count(line) != 1:
            ambiguous.append({**candidate, "reason": "exact source line is not unique"})
            continue
        if per_class_count.get(fault_class, 0) >= config.max_mutations_per_fault_class:
            continue
        binding = _binding_for(config, fault_class, function_name)
        if binding is None:
            unbound_classes.add(fault_class)
            continue
        per_class_count[fault_class] = per_class_count.get(fault_class, 0) + 1
        generated.append(
            {
                "mutationId": candidate_id,
                "faultClass": fault_class,
                "description": f"{description} in {function_name}() at line {index}",
                "match": line,
                "replacement": _comment_replacement(line, operator_id),
                "matchPath": binding.match_path,
                "matchTest": binding.match_test,
            }
        )

    represented = sorted({item["faultClass"] for item in generated})
    missing_candidate_classes = sorted(set(supported_required) - set(represented))

    plan: dict[str, object] | None = None
    if generated:
        plan = {
            "schemaVersion": "solidity-mutation-plan-v0.1",
            "acquisitionId": f"{config.generation_id}-acquisition",
            "sourcePath": config.source_path,
            "sourceSha256": config.source_sha256,
            "propertyInvariantId": config.property_invariant_id,
            "propertyDescription": config.property_description,
            "activationWitness": {
                "observed": config.activation_witness.observed,
                "evidenceSha256": config.activation_witness.evidence_sha256,
                "description": config.activation_witness.description,
            },
            "requiredFaultClasses": list(config.required_fault_classes),
            "foundry": {
                "profile": config.foundry.profile,
                "timeoutSeconds": config.foundry.timeout_seconds,
            },
            "mutations": generated,
        }
        if config.scope is not None:
            plan["scope"] = config.scope
        mutation_plan_from_dict(plan)

    blockers = bool(unsupported_required or missing_candidate_classes or unbound_classes or not generated)
    status = "inconclusive" if blockers else "pass"
    classification = "incomplete_generation" if blockers else "generated_complete_review_set"
    result_core = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "generationId": config.generation_id,
        "sourcePath": config.source_path,
        "sourceSha256": config.source_sha256,
        "propertyInvariantId": config.property_invariant_id,
        "requiredFaultClasses": list(config.required_fault_classes),
        "supportedRequiredFaultClasses": supported_required,
        "unsupportedRequiredFaultClasses": unsupported_required,
        "representedFaultClasses": represented,
        "missingCandidateFaultClasses": missing_candidate_classes,
        "unboundFaultClasses": sorted(unbound_classes),
        "maxMutationsPerFaultClass": config.max_mutations_per_fault_class,
        "discoveredCandidateCount": len(discovered),
        "generatedMutationCount": len(generated),
        "discoveredCandidates": discovered,
        "ambiguousCandidates": ambiguous,
        "generatedMutationIds": [item["mutationId"] for item in generated],
        "claimBoundary": (
            "Exact over the supplied source bytes, required fault classes, deterministic v0.1 syntax-local operators, "
            "and reviewed test bindings. PASS means every declared required class is supported by this generator and "
            "has at least one executable generated mutation. It does not mean the generated set is exhaustive, that "
            "the fault model is complete, or that any generated mutant is detected; Mutation Acquisition and "
            "CGQ-SPEC-001 establish those later evidence claims."
        ),
    }
    result = dict(result_core)
    result["resultSha256"] = _canonical_sha256(result_core)
    result["mutationPlan"] = plan
    return result
