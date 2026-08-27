"""Solidity -> lifecycle graph -> Contract Lattice template verification.

This module deliberately separates what static compiler evidence can establish from
what requires runtime evidence:

- Solidity compiler AST establishes enum states, supported guards and state writes.
- A reviewed profile marks initial, value-holding and safe-terminal states.
- Lifecycle liveness is verified exactly over the extracted finite graph.
- The same graph is projected into a Contract Lattice *template* with relative
  version deltas. Concrete versions, balances, authority, time witnesses and
  external effects remain runtime/provenance claims.

Unsupported state writers make the result INCONCLUSIVE instead of manufacturing a
PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

from contractgraph_qa.lifecycle_liveness import (
    LifecycleLivenessModel,
    LifecycleState,
    LifecycleTransition,
    lifecycle_liveness_model_to_dict,
    run_lifecycle_liveness_model,
)

PROFILE_KEYS = {
    "contractName",
    "enumName",
    "stateSelector",
    "selectorKind",
    "initialState",
    "valueHoldingStates",
    "safeTerminalStates",
    "invariantId",
}
SELECTOR_KINDS = {"identifier", "member", "either"}


@dataclass(frozen=True, slots=True)
class SolidityLatticeProfile:
    contract_name: str
    enum_name: str
    state_selector: str
    selector_kind: str
    initial_state: str
    value_holding_states: tuple[str, ...]
    safe_terminal_states: tuple[str, ...]
    invariant_id: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _refs(value: Any, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    if non_empty:
        _require(bool(value), f"{field} must be non-empty")
    refs = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(refs) == len(set(refs)), f"{field} must contain unique values")
    return refs


def profile_from_dict(data: dict[str, Any]) -> SolidityLatticeProfile:
    _require(isinstance(data, dict), "Solidity lattice profile must be a JSON object")
    extras = sorted(set(data) - PROFILE_KEYS)
    missing = sorted(PROFILE_KEYS - set(data))
    _require(not extras, "Solidity lattice profile contains unexpected fields: " + ", ".join(extras))
    _require(not missing, "Solidity lattice profile missing required fields: " + ", ".join(missing))

    selector_kind = _text(data["selectorKind"], "selectorKind")
    _require(selector_kind in SELECTOR_KINDS, "selectorKind must be identifier, member, or either")
    value_states = _refs(data["valueHoldingStates"], "valueHoldingStates")
    safe_states = _refs(data["safeTerminalStates"], "safeTerminalStates", non_empty=True)
    overlap = sorted(set(value_states) & set(safe_states))
    _require(not overlap, "safe terminal states cannot hold locked value: " + ", ".join(overlap))

    return SolidityLatticeProfile(
        contract_name=_text(data["contractName"], "contractName"),
        enum_name=_text(data["enumName"], "enumName"),
        state_selector=_text(data["stateSelector"], "stateSelector"),
        selector_kind=selector_kind,
        initial_state=_text(data["initialState"], "initialState"),
        value_holding_states=value_states,
        safe_terminal_states=safe_states,
        invariant_id=_text(data["invariantId"], "invariantId"),
    )


def load_profile(path: Path) -> SolidityLatticeProfile:
    with path.open("r", encoding="utf-8") as handle:
        return profile_from_dict(json.load(handle))


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_contract(ast: dict[str, Any], profile: SolidityLatticeProfile) -> dict[str, Any]:
    matches = [
        node
        for node in _walk(ast)
        if node.get("nodeType") == "ContractDefinition" and node.get("name") == profile.contract_name
    ]
    _require(matches, f"contract not found in AST: {profile.contract_name}")
    _require(len(matches) == 1, f"multiple contract definitions found: {profile.contract_name}")
    return matches[0]


def _enum_states(contract: Mapping[str, Any], profile: SolidityLatticeProfile) -> tuple[str, ...]:
    matches = [
        node
        for node in contract.get("nodes", [])
        if isinstance(node, dict)
        and node.get("nodeType") == "EnumDefinition"
        and node.get("name") == profile.enum_name
    ]
    _require(matches, f"enum not found in contract: {profile.enum_name}")
    _require(len(matches) == 1, f"multiple enum definitions found: {profile.enum_name}")
    members = tuple(
        _text(member.get("name"), f"enum {profile.enum_name} member")
        for member in matches[0].get("members", [])
        if isinstance(member, dict)
    )
    _require(members, f"enum has no members: {profile.enum_name}")
    _require(len(members) == len(set(members)), f"enum contains duplicate members: {profile.enum_name}")
    return members


def _matches_state(node: Any, profile: SolidityLatticeProfile) -> bool:
    if not isinstance(node, dict):
        return False
    if profile.selector_kind in {"identifier", "either"}:
        if node.get("nodeType") == "Identifier" and node.get("name") == profile.state_selector:
            return True
    if profile.selector_kind in {"member", "either"}:
        if node.get("nodeType") == "MemberAccess" and node.get("memberName") == profile.state_selector:
            return True
    return False


def _enum_member(node: Any, profile: SolidityLatticeProfile, states: set[str]) -> str | None:
    if not isinstance(node, dict) or node.get("nodeType") != "MemberAccess":
        return None
    member = node.get("memberName")
    if member not in states:
        return None
    expression = node.get("expression")
    if not isinstance(expression, dict):
        return None
    if expression.get("nodeType") == "Identifier" and expression.get("name") == profile.enum_name:
        return str(member)
    type_descriptions = expression.get("typeDescriptions")
    if isinstance(type_descriptions, dict):
        type_string = type_descriptions.get("typeString")
        if isinstance(type_string, str) and f".{profile.enum_name}" in type_string:
            return str(member)
    return None


def _comparison(node: Any, profile: SolidityLatticeProfile, states: set[str]) -> tuple[str, str] | None:
    if not isinstance(node, dict) or node.get("nodeType") != "BinaryOperation":
        return None
    operator = node.get("operator")
    if operator not in {"==", "!="}:
        return None
    left = node.get("leftExpression")
    right = node.get("rightExpression")
    if _matches_state(left, profile):
        member = _enum_member(right, profile, states)
        if member is not None:
            return str(operator), member
    if _matches_state(right, profile):
        member = _enum_member(left, profile, states)
        if member is not None:
            return str(operator), member
    return None


def _allowed_true(node: Any, profile: SolidityLatticeProfile, states: set[str]) -> set[str] | None:
    comparison = _comparison(node, profile, states)
    if comparison is not None:
        operator, member = comparison
        return {member} if operator == "==" else None
    if not isinstance(node, dict):
        return None
    if node.get("nodeType") == "BinaryOperation" and node.get("operator") == "||":
        left = _allowed_true(node.get("leftExpression"), profile, states)
        right = _allowed_true(node.get("rightExpression"), profile, states)
        if left is not None and right is not None:
            return left | right
    if node.get("nodeType") == "BinaryOperation" and node.get("operator") == "&&":
        left = _allowed_true(node.get("leftExpression"), profile, states)
        right = _allowed_true(node.get("rightExpression"), profile, states)
        if left is not None and right is not None:
            return left & right
    return None


def _allowed_false(node: Any, profile: SolidityLatticeProfile, states: set[str]) -> set[str] | None:
    comparison = _comparison(node, profile, states)
    if comparison is not None:
        operator, member = comparison
        return {member} if operator == "!=" else None
    if isinstance(node, dict) and node.get("nodeType") == "UnaryOperation" and node.get("operator") == "!":
        return _allowed_true(node.get("subExpression"), profile, states)
    return None


def _is_builtin_call(node: Any, name: str) -> bool:
    if not isinstance(node, dict) or node.get("nodeType") != "FunctionCall":
        return False
    callee = node.get("expression")
    return isinstance(callee, dict) and callee.get("nodeType") == "Identifier" and callee.get("name") == name


def _contains_revert(node: Any) -> bool:
    """Recognize both custom-error RevertStatement and builtin revert(...)."""

    for candidate in _walk(node):
        if candidate.get("nodeType") == "RevertStatement":
            return True
        if _is_builtin_call(candidate, "revert"):
            return True
    return False


def _require_guard(statement: Any, profile: SolidityLatticeProfile, states: set[str]) -> set[str] | None:
    if not isinstance(statement, dict) or statement.get("nodeType") != "ExpressionStatement":
        return None
    expression = statement.get("expression")
    if not _is_builtin_call(expression, "require"):
        return None
    arguments = expression.get("arguments", [])
    if not arguments:
        return None
    return _allowed_true(arguments[0], profile, states)


def _if_revert_guard(statement: Any, profile: SolidityLatticeProfile, states: set[str]) -> set[str] | None:
    if not isinstance(statement, dict) or statement.get("nodeType") != "IfStatement":
        return None
    if statement.get("falseBody") is not None or not _contains_revert(statement.get("trueBody")):
        return None
    return _allowed_false(statement.get("condition"), profile, states)


def _assignment_target(node: Any, profile: SolidityLatticeProfile, states: set[str]) -> str | None:
    if not isinstance(node, dict) or node.get("nodeType") != "Assignment" or node.get("operator") != "=":
        return None
    if not _matches_state(node.get("leftHandSide"), profile):
        return None
    return _enum_member(node.get("rightHandSide"), profile, states)


def _source_states(function: Mapping[str, Any], profile: SolidityLatticeProfile, states: set[str]) -> set[str] | None:
    body = function.get("body")
    if not isinstance(body, dict):
        return None
    allowed: set[str] | None = None
    for statement in body.get("statements", []):
        if any(_assignment_target(node, profile, states) for node in _walk(statement)):
            break
        candidate = _require_guard(statement, profile, states)
        if candidate is None:
            candidate = _if_revert_guard(statement, profile, states)
        if candidate is not None:
            allowed = candidate if allowed is None else allowed & candidate
    return allowed if allowed else None


def extract_from_ast(ast: dict[str, Any], profile: SolidityLatticeProfile) -> dict[str, object]:
    contract = _find_contract(ast, profile)
    enum_states = _enum_states(contract, profile)
    state_set = set(enum_states)
    semantic_states = {profile.initial_state} | set(profile.value_holding_states) | set(profile.safe_terminal_states)
    unknown = sorted(semantic_states - state_set)
    _require(not unknown, "profile references states absent from enum: " + ", ".join(unknown))

    transitions: list[LifecycleTransition] = []
    evidence: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []

    for function in contract.get("nodes", []):
        if not isinstance(function, dict) or function.get("nodeType") != "FunctionDefinition":
            continue
        if function.get("kind") == "constructor" or not isinstance(function.get("body"), dict):
            continue
        targets = sorted(
            {
                target
                for node in _walk(function.get("body"))
                if (target := _assignment_target(node, profile, state_set)) is not None
            }
        )
        if not targets:
            continue
        function_name = str(function.get("name") or f"function-{function.get('id', 'unknown')}")
        sources = _source_states(function, profile, state_set)
        if sources is None:
            unresolved.append(
                {
                    "function": function_name,
                    "astNodeId": function.get("id"),
                    "targetStates": targets,
                    "reason": "state_write_without_unambiguous_entry_state_guard",
                }
            )
            continue
        for source in sorted(sources):
            for target in targets:
                transition_id = f"{function_name}:{source}->{target}"
                transitions.append(LifecycleTransition(id=transition_id, source=source, target=target))
                evidence.append(
                    {
                        "transitionId": transition_id,
                        "function": function_name,
                        "astNodeId": function.get("id"),
                        "sourceState": source,
                        "targetState": target,
                    }
                )

    transition_ids = [edge.id for edge in transitions]
    _require(len(transition_ids) == len(set(transition_ids)), "extracted transition ids are not unique")

    model = LifecycleLivenessModel(
        states=tuple(
            LifecycleState(
                id=state,
                description=f"Extracted {profile.contract_name}.{profile.enum_name}.{state}",
                holds_value=state in profile.value_holding_states,
                safe_terminal=state in profile.safe_terminal_states,
            )
            for state in enum_states
        ),
        transitions=tuple(sorted(transitions, key=lambda edge: (edge.source, edge.target, edge.id))),
        initial_state=profile.initial_state,
        invariant_id=profile.invariant_id,
    )

    return {
        "schemaVersion": "solidity-lattice-extraction-v0.1",
        "extractionComplete": not unresolved,
        "astSha256": _canonical_sha256(ast),
        "profileSha256": _canonical_sha256(
            {
                "contractName": profile.contract_name,
                "enumName": profile.enum_name,
                "stateSelector": profile.state_selector,
                "selectorKind": profile.selector_kind,
                "initialState": profile.initial_state,
                "valueHoldingStates": list(profile.value_holding_states),
                "safeTerminalStates": list(profile.safe_terminal_states),
                "invariantId": profile.invariant_id,
            }
        ),
        "contractName": profile.contract_name,
        "enumName": profile.enum_name,
        "model": lifecycle_liveness_model_to_dict(model),
        "transitionEvidence": sorted(evidence, key=lambda item: str(item["transitionId"])),
        "unresolvedStateWriters": unresolved,
    }


def _lattice_template(extraction: Mapping[str, object]) -> dict[str, object]:
    model = extraction["model"]
    assert isinstance(model, dict)
    states = model["states"]
    transitions = model["transitions"]
    evidence = extraction["transitionEvidence"]
    assert isinstance(states, list) and isinstance(transitions, list) and isinstance(evidence, list)
    evidence_by_id = {str(item["transitionId"]): item for item in evidence if isinstance(item, dict)}

    return {
        "schemaVersion": "contract-lattice-template-v0.1",
        "dimensions": ["state", "relativeVersion", "valuePresence", "authority", "evidence", "timeWitness"],
        "points": [
            {
                "state": item["id"],
                "valuePresence": bool(item["holdsValue"]),
                "safeTerminal": bool(item["safeTerminal"]),
                "authority": "not_inferred_from_static_ast",
                "timeWitness": "not_inferred_from_static_ast",
            }
            for item in states
        ],
        "transitionTemplates": [
            {
                "id": edge["id"],
                "sourceState": edge["source"],
                "targetState": edge["target"],
                "versionDelta": 1,
                "sourceEvidence": evidence_by_id.get(str(edge["id"]), {}),
            }
            for edge in transitions
        ],
        "valueSemantics": "presence_only; no token/native amount is inferred from static AST",
        "versionSemantics": "relative transition delta only; concrete versions require runtime evidence",
        "claimBoundary": (
            "Static template only. Concrete balances, authority, time witnesses, transaction ordering, "
            "economic occurrences and committed state versions require normalized runtime evidence."
        ),
    }


def check_ast(ast: dict[str, Any], profile: SolidityLatticeProfile) -> dict[str, object]:
    extraction = extract_from_ast(ast, profile)
    template = _lattice_template(extraction)
    if not extraction["extractionComplete"]:
        return {
            "schemaVersion": "solidity-lattice-result-v0.1",
            "status": "inconclusive",
            "extraction": extraction,
            "lifecycleVerification": None,
            "latticeTemplate": template,
            "reason": "incomplete_state_transition_extraction",
        }

    model_data = extraction["model"]
    assert isinstance(model_data, dict)
    states = tuple(
        LifecycleState(
            id=str(item["id"]),
            description=str(item["description"]),
            holds_value=bool(item["holdsValue"]),
            safe_terminal=bool(item["safeTerminal"]),
        )
        for item in model_data["states"]
    )
    transitions = tuple(
        LifecycleTransition(id=str(item["id"]), source=str(item["source"]), target=str(item["target"]))
        for item in model_data["transitions"]
    )
    verification = run_lifecycle_liveness_model(
        LifecycleLivenessModel(
            states=states,
            transitions=transitions,
            initial_state=str(model_data["initialState"]),
            invariant_id=str(model_data["invariantId"]),
        )
    )
    return {
        "schemaVersion": "solidity-lattice-result-v0.1",
        "status": verification["status"],
        "extraction": extraction,
        "lifecycleVerification": verification,
        "latticeTemplate": template,
    }


def _forge_out(root: Path) -> Path:
    completed = subprocess.run(
        ["forge", "config", "--json"],
        cwd=str(root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "forge config failed"
        raise ValueError(detail)
    try:
        config = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("forge config did not return valid JSON") from exc
    _require(isinstance(config, dict), "forge config JSON must be an object")
    out = config.get("out")
    _require(isinstance(out, str) and out.strip(), "forge config is missing output directory")
    path = Path(out)
    return path if path.is_absolute() else root / path


def _source_matches(candidate: str, requested: str) -> bool:
    left = candidate.replace("\\", "/").lstrip("./")
    right = requested.replace("\\", "/").lstrip("./")
    return left == right or left.endswith("/" + right)


def load_forge_ast(target: str, root: Path | None = None) -> dict[str, Any]:
    target = _text(target, "target")
    _require(":" in target, "target must use <source.sol>:<Contract> form")
    source, contract_name = target.rsplit(":", 1)
    source = _text(source, "target source")
    _text(contract_name, "target contract")
    project_root = (root or Path.cwd()).resolve()

    completed = subprocess.run(
        ["forge", "build", "--ast", "--build-info"],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "forge build failed"
        raise ValueError(detail)

    build_info = _forge_out(project_root) / "build-info"
    _require(build_info.is_dir(), f"Foundry build-info directory not found: {build_info}")
    candidates: list[dict[str, Any]] = []
    for path in sorted(build_info.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid Foundry build-info JSON: {path}") from exc
        if not isinstance(document, dict):
            continue
        output = document.get("output")
        sources = output.get("sources") if isinstance(output, dict) else None
        if not isinstance(sources, dict):
            continue
        for source_name, source_data in sources.items():
            if not isinstance(source_name, str) or not _source_matches(source_name, source):
                continue
            if isinstance(source_data, dict) and isinstance(source_data.get("ast"), dict):
                candidates.append(source_data["ast"])

    _require(candidates, f"AST not found in Foundry build-info for source: {source}")
    by_digest: dict[str, dict[str, Any]] = {}
    for ast in candidates:
        by_digest.setdefault(_canonical_sha256(ast), ast)
    _require(len(by_digest) == 1, f"ambiguous Foundry AST candidates for source: {source}")
    return next(iter(by_digest.values()))


def check_target(target: str, profile: SolidityLatticeProfile, root: Path | None = None) -> dict[str, object]:
    return check_ast(load_forge_ast(target, root), profile)
