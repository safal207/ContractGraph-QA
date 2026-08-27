"""AST-bound semantic mutation generation for reviewed unit/decimal bindings.

Semantic Units Mutation v0.1 intentionally supports one narrow class:
`units_decimals`. A reviewer declares that a named Solidity constant represents a
specific unit with an expected decimal count. Foundry's compiler AST must confirm
that exact symbol, constant integer type, and numeric literal initializer before a
counterfactual decimal mutation is emitted.

This module does not infer units from variable names, token symbols, comments, or
business intent. It does not search for arbitrary numeric literals. The reviewed
binding supplies unit semantics; compiler AST supplies source identity and syntax.
Generated mutations are ordinary source-bound Mutation Acquisition plans, so
Foundry execution, CGQ-SPEC-001, and Fault Coverage Matrix remain the downstream
evidence authorities.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict
from contractgraph_qa.solidity_lattice import load_forge_ast

SCHEMA_VERSION = "semantic-units-mutation-v0.1"
RESULT_SCHEMA_VERSION = "semantic-units-mutation-generator-result-v0.1"
FAULT_CLASS = "units_decimals"

_MODEL_KEYS = {
    "schemaVersion",
    "generationId",
    "target",
    "sourcePath",
    "sourceSha256",
    "propertyInvariantId",
    "propertyDescription",
    "activationWitness",
    "requiredFaultClasses",
    "foundry",
    "unitBindings",
    "scope",
}
_ACTIVATION_KEYS = {"observed", "evidenceSha256", "description"}
_FOUNDRY_KEYS = {"profile", "timeoutSeconds"}
_BINDING_KEYS = {
    "symbol",
    "unitId",
    "expectedDecimals",
    "alternateDecimals",
    "matchPath",
    "matchTest",
}
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9._:-]+")
_INTEGER_TYPE_RE = re.compile(r"^u?int(?:[0-9]{1,3})?(?:\s|$)")


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
class UnitBinding:
    symbol: str
    unit_id: str
    expected_decimals: int
    alternate_decimals: tuple[int, ...]
    match_path: str
    match_test: str


@dataclass(frozen=True, slots=True)
class SemanticUnitsMutationConfig:
    generation_id: str
    target: str
    source_path: str
    source_sha256: str
    property_invariant_id: str
    property_description: str
    activation_witness: ActivationEvidence
    required_fault_classes: tuple[str, ...]
    foundry: FoundryConfig
    unit_bindings: tuple[UnitBinding, ...]
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


def _decimal(value: Any, field: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool), f"{field} must be an integer")
    _require(0 <= value <= 77, f"{field} must be between 0 and 77")
    return value


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _unique_texts(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty array")
    items = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def semantic_units_config_from_dict(data: dict[str, Any]) -> SemanticUnitsMutationConfig:
    _require(isinstance(data, dict), "semantic units mutation config must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "semantic units mutation config")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "semantic units mutation config missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")

    target = _text(data["target"], "target")
    _require(":" in target, "target must use <source.sol>:<Contract> form")
    target_source, contract_name = target.rsplit(":", 1)
    source_path = _relative_path(data["sourcePath"], "sourcePath")
    _require(Path(target_source).as_posix().lstrip("./") == source_path.lstrip("./"), "target source must equal sourcePath")
    _safe_id(contract_name, "target contract")

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

    required_fault_classes = _unique_texts(data["requiredFaultClasses"], "requiredFaultClasses")
    unsupported = sorted(set(required_fault_classes) - {FAULT_CLASS})
    _require(not unsupported, "Semantic Units Mutation v0.1 supports only units_decimals; unsupported: " + ", ".join(unsupported))
    _require(FAULT_CLASS in required_fault_classes, "requiredFaultClasses must include units_decimals")

    bindings_raw = data["unitBindings"]
    _require(isinstance(bindings_raw, list) and bindings_raw, "unitBindings must be a non-empty array")
    bindings: list[UnitBinding] = []
    symbols: set[str] = set()
    for index, raw in enumerate(bindings_raw):
        field = f"unitBindings[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _BINDING_KEYS, field)
        _require(_BINDING_KEYS <= set(raw), f"{field} missing required fields")
        symbol = _safe_id(raw["symbol"], f"{field}.symbol")
        _require(symbol not in symbols, f"duplicate unit binding symbol: {symbol}")
        symbols.add(symbol)
        expected = _decimal(raw["expectedDecimals"], f"{field}.expectedDecimals")
        alternatives_raw = raw["alternateDecimals"]
        _require(isinstance(alternatives_raw, list) and alternatives_raw, f"{field}.alternateDecimals must be non-empty")
        alternatives = tuple(_decimal(item, f"{field}.alternateDecimals[{alt_index}]") for alt_index, item in enumerate(alternatives_raw))
        _require(len(alternatives) == len(set(alternatives)), f"{field}.alternateDecimals must be unique")
        _require(expected not in alternatives, f"{field}.alternateDecimals must not contain expectedDecimals")
        bindings.append(
            UnitBinding(
                symbol=symbol,
                unit_id=_text(raw["unitId"], f"{field}.unitId"),
                expected_decimals=expected,
                alternate_decimals=alternatives,
                match_path=_relative_path(raw["matchPath"], f"{field}.matchPath"),
                match_test=_text(raw["matchTest"], f"{field}.matchTest"),
            )
        )

    scope_raw = data.get("scope")
    return SemanticUnitsMutationConfig(
        generation_id=_safe_id(data["generationId"], "generationId"),
        target=target,
        source_path=source_path,
        source_sha256=_sha256(data["sourceSha256"], "sourceSha256"),
        property_invariant_id=_text(data["propertyInvariantId"], "propertyInvariantId"),
        property_description=_text(data["propertyDescription"], "propertyDescription"),
        activation_witness=activation,
        required_fault_classes=required_fault_classes,
        foundry=foundry,
        unit_bindings=tuple(bindings),
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_semantic_units_config(path: Path) -> SemanticUnitsMutationConfig:
    with path.open("r", encoding="utf-8") as handle:
        return semantic_units_config_from_dict(json.load(handle))


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_src(value: Any, field: str) -> tuple[int, int, int]:
    text = _text(value, field)
    parts = text.split(":")
    _require(len(parts) == 3, f"{field} must use start:length:fileIndex")
    try:
        start, length, file_index = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{field} contains non-integer source coordinates") from exc
    _require(start >= 0 and length > 0 and file_index >= 0, f"{field} contains invalid source coordinates")
    return start, length, file_index


def _target_contract(ast: Mapping[str, Any], contract_name: str) -> Mapping[str, Any]:
    matches = [
        node
        for node in _walk(ast)
        if node.get("nodeType") == "ContractDefinition" and node.get("name") == contract_name
    ]
    _require(len(matches) == 1, f"expected exactly one contract definition for {contract_name}; found {len(matches)}")
    return matches[0]


def _integer_type(node: Mapping[str, Any]) -> bool:
    type_descriptions = node.get("typeDescriptions")
    if not isinstance(type_descriptions, Mapping):
        return False
    type_string = type_descriptions.get("typeString")
    return isinstance(type_string, str) and bool(_INTEGER_TYPE_RE.match(type_string))


def _line_context_mutation(original: str, mutated: str, target_line_index: int, max_radius: int = 8) -> tuple[str, str, int, int] | None:
    original_lines = original.splitlines(keepends=True)
    mutated_lines = mutated.splitlines(keepends=True)
    _require(len(original_lines) == len(mutated_lines), "semantic literal mutation unexpectedly changed line count")
    for radius in range(max_radius + 1):
        start = max(0, target_line_index - radius)
        end = min(len(original_lines), target_line_index + radius + 1)
        match = "".join(original_lines[start:end])
        if original.count(match) != 1:
            continue
        replacement = "".join(mutated_lines[start:end])
        return match, replacement, start + 1, end
    return None


def _literal_value(node: Mapping[str, Any]) -> int | None:
    if node.get("nodeType") != "Literal" or node.get("kind") != "number":
        return None
    value = node.get("value")
    if not isinstance(value, str):
        return None
    try:
        return int(value, 10)
    except ValueError:
        return None


def _binding_candidate(
    contract: Mapping[str, Any],
    binding: UnitBinding,
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    matches = [
        node
        for node in contract.get("nodes", [])
        if isinstance(node, Mapping)
        and node.get("nodeType") == "VariableDeclaration"
        and node.get("name") == binding.symbol
    ]
    if len(matches) != 1:
        return None
    declaration = matches[0]
    if declaration.get("constant") is not True or not _integer_type(declaration):
        return None
    value = declaration.get("value")
    if not isinstance(value, Mapping) or _literal_value(value) != binding.expected_decimals:
        return None
    return declaration, value


def generate_semantic_units_mutation_plan(
    config: SemanticUnitsMutationConfig,
    project_root: Path,
) -> dict[str, object]:
    """Generate compiler-AST-bound decimal counterfactuals for reviewed unit constants."""

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
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source file must be UTF-8") from exc

    ast = load_forge_ast(config.target, root)
    contract_name = config.target.rsplit(":", 1)[1]
    contract = _target_contract(ast, contract_name)
    ast_sha = _canonical_sha256(ast)

    discovered: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    generated: list[dict[str, object]] = []

    for binding in config.unit_bindings:
        candidate = _binding_candidate(contract, binding)
        if candidate is None:
            unresolved.append(
                {
                    "symbol": binding.symbol,
                    "unitId": binding.unit_id,
                    "expectedDecimals": binding.expected_decimals,
                    "reason": "binding_not_confirmed_as_unique_constant_integer_literal",
                }
            )
            continue
        declaration, literal = candidate
        literal_start, literal_length, file_index = _parse_src(literal.get("src"), f"AST literal src for {binding.symbol}")
        _require(literal_start + literal_length <= len(source_bytes), f"AST source span escapes source bytes for {binding.symbol}")
        literal_bytes = source_bytes[literal_start : literal_start + literal_length]
        try:
            literal_text = literal_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"AST literal source is not UTF-8 for {binding.symbol}") from exc
        _require(literal_text.strip() == str(binding.expected_decimals), f"AST literal bytes do not match reviewed decimals for {binding.symbol}")

        line_number = source_bytes[:literal_start].count(b"\n") + 1
        discovered.append(
            {
                "symbol": binding.symbol,
                "unitId": binding.unit_id,
                "expectedDecimals": binding.expected_decimals,
                "alternateDecimals": list(binding.alternate_decimals),
                "astNodeId": declaration.get("id"),
                "literalAstNodeId": literal.get("id"),
                "literalSource": literal_text,
                "literalSourceStart": literal_start,
                "literalSourceLength": literal_length,
                "sourceFileIndex": file_index,
                "line": line_number,
            }
        )

        for alternative in binding.alternate_decimals:
            replacement_bytes = str(alternative).encode("utf-8")
            mutated_bytes = source_bytes[:literal_start] + replacement_bytes + source_bytes[literal_start + literal_length :]
            try:
                mutated_text = mutated_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:  # pragma: no cover - ASCII replacement cannot introduce this
                raise ValueError("semantic mutation produced invalid UTF-8") from exc
            anchored = _line_context_mutation(source_text, mutated_text, line_number - 1)
            if anchored is None:
                unresolved.append(
                    {
                        "symbol": binding.symbol,
                        "unitId": binding.unit_id,
                        "expectedDecimals": binding.expected_decimals,
                        "alternateDecimals": alternative,
                        "reason": "no_unique_source_context_within_8_lines",
                    }
                )
                continue
            match, replacement, context_start, context_end = anchored
            mutation_id = f"unit-{binding.symbol.lower()}-{binding.expected_decimals}-to-{alternative}"
            generated.append(
                {
                    "mutationId": mutation_id,
                    "faultClass": FAULT_CLASS,
                    "description": (
                        f"Reviewed unit {binding.unit_id}: change {binding.symbol} decimals "
                        f"from {binding.expected_decimals} to {alternative}; compiler AST node {literal.get('id')}; "
                        f"unique source context lines {context_start}-{context_end}"
                    ),
                    "match": match,
                    "replacement": replacement,
                    "matchPath": binding.match_path,
                    "matchTest": binding.match_test,
                }
            )

    represented = [FAULT_CLASS] if generated else []
    missing_classes = [] if generated else [FAULT_CLASS]
    status = "pass" if generated and not unresolved else "inconclusive"
    classification = "generated_reviewed_semantic_mutations" if status == "pass" else "incomplete_semantic_binding"

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

    core: dict[str, object] = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "classification": classification,
        "generationId": config.generation_id,
        "target": config.target,
        "sourcePath": config.source_path,
        "sourceSha256": config.source_sha256,
        "astSha256": ast_sha,
        "propertyInvariantId": config.property_invariant_id,
        "requiredFaultClasses": list(config.required_fault_classes),
        "supportedRequiredFaultClasses": [FAULT_CLASS],
        "unsupportedRequiredFaultClasses": [],
        "representedFaultClasses": represented,
        "missingCandidateFaultClasses": missing_classes,
        "unboundFaultClasses": [],
        "discoveredCandidateCount": len(discovered),
        "generatedMutationCount": len(generated),
        "discoveredCandidates": discovered,
        "ambiguousCandidates": unresolved,
        "generatedMutationIds": [item["mutationId"] for item in generated],
        "claimBoundary": (
            "Exact over the supplied source SHA-256, reviewed unit bindings, Foundry compiler AST, constant integer "
            "literal initializers, AST source coordinates, and reviewed Foundry selectors. PASS means every reviewed "
            "binding was confirmed by compiler AST and produced the declared compile-candidate decimal counterfactuals. "
            "It does not infer units from names, prove unit semantics complete, prove mutants compile, or prove the "
            "verification suite detects them; Mutation Acquisition, CGQ-SPEC-001, and Fault Coverage Matrix establish "
            "those later evidence claims."
        ),
    }
    result = dict(core)
    result["resultSha256"] = _canonical_sha256(core)
    result["mutationPlan"] = plan
    return result
