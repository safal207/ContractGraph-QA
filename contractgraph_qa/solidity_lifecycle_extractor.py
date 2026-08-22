"""Extract lifecycle state transitions from Solidity compiler AST evidence.

Structural facts come from compiler AST. Economic semantics come from a reviewed
profile. Unsupported or ambiguous state writers make verification inconclusive
instead of manufacturing a PASS.
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
class SolidityLifecycleProfile:
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


def _string_tuple(value: Any, field: str, *, non_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    if non_empty:
        _require(bool(value), f"{field} must be non-empty")
    result = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(result) == len(set(result)), f"{field} must contain unique values")
    return result


def lifecycle_profile_from_dict(data: dict[str, Any]) -> SolidityLifecycleProfile:
    _require(isinstance(data, dict), "Solidity lifecycle profile must be a JSON object")
    extras = sorted(set(data) - PROFILE_KEYS)
    missing = sorted(PROFILE_KEYS - set(data))
    _require(
        not extras,
        "Solidity lifecycle profile contains unexpected fields: " + ", ".join(extras),
    )
    _require(
        not missing,
        "Solidity lifecycle profile missing required fields: " + ", ".join(missing),
    )

    selector_kind = _text(data["selectorKind"], "selectorKind")
    _require(
        selector_kind in SELECTOR_KINDS,
        "selectorKind must be identifier, member, or either",
    )

    value_states = _string_tuple(data["valueHoldingStates"], "valueHoldingStates")
    safe_terminals = _string_tuple(
        data["safeTerminalStates"],
        "safeTerminalStates",
        non_empty=True,
    )
    overlap = sorted(set(value_states) & set(safe_terminals))
    _require(
        not overlap,
        "safe terminal states cannot hold locked value: " + ", ".join(overlap),
    )

    return SolidityLifecycleProfile(
        contract_name=_text(data["contractName"], "contractName"),
        enum_name=_text(data["enumName"], "enumName"),
        state_selector=_text(data["stateSelector"], "stateSelector"),
        selector_kind=selector_kind,
        initial_state=_text(data["initialState"], "initialState"),
        value_holding_states=value_states,
        safe_terminal_states=safe_terminals,
        invariant_id=_text(data["invariantId"], "invariantId"),
    )


def load_lifecycle_profile(path: Path) -> SolidityLifecycleProfile:
    with path.open("r", encoding="utf-8") as handle:
        return lifecycle_profile_from_dict(json.load(handle))


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_contract(
    ast: dict[str, Any],
    profile: SolidityLifecycleProfile,
) -> dict[str, Any]:
    matches = [
        node
        for node in _walk(ast)
        if node.get("nodeType") == "ContractDefinition"
        and node.get("name") == profile.contract_name
    ]
    _require(bool(matches), f"contract not found in AST: {profile.contract_name}")
    _require(
        len(matches) == 1,
        f"multiple contract definitions found: {profile.contract_name}",
    )
    return matches[0]


def _enum_states(
    contract: Mapping[str, Any],
    profile: SolidityLifecycleProfile,
) -> tuple[str, ...]:
    matches = [
        node
        for node in contract.get("nodes", [])
        if isinstance(node, dict)
        and node.get("nodeType") == "EnumDefinition"
        and node.get("name") == profile.enum_name
    ]
    _require(bool(matches), f"enum not found in contract: {profile.enum_name}")
    _require(
        len(matches) == 1,
        f"multiple enum definitions found: {profile.enum_name}",
    )
    members = tuple(
        _text(member.get("name"), f"enum {profile.enum_name} member")
        for member in matches[0].get("members", [])
        if isinstance(member, dict)
    )
    _require(bool(members), f"enum has no members: {profile.enum_name}")
    _require(
        len(members) == len(set(members)),
        f"enum contains duplicate members: {profile.enum_name}",
    )
    return members


def _matches_state_expression(
    node: Any,
    profile: SolidityLifecycleProfile,
) -> bool:
    if not isinstance(node, dict):
        return False
    if profile.selector_kind in {"identifier", "either"}:
        if (
            node.get("nodeType") == "Identifier"
            and node.get("name") == profile.state_selector
        ):
            return True
    if profile.selector_kind in {"member", "either"}:
        if (
            node.get("nodeType") == "MemberAccess"
            and node.get("memberName") == profile.state_selector
        ):
            return True
    return False


def _enum_member(
    node: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> str | None:
    if not isinstance(node, dict) or node.get("nodeType") != "MemberAccess":
        return None
    member = node.get("memberName")
    if member not in enum_states:
        return None
    expression = node.get("expression")
    if isinstance(expression, dict):
        if (
            expression.get("nodeType") == "Identifier"
            and expression.get("name") == profile.enum_name
        ):
            return str(member)
        type_descriptions = expression.get("typeDescriptions", {})
        if isinstance(type_descriptions, dict):
            type_string = type_descriptions.get("typeString")
            if isinstance(type_string, str) and f".{profile.enum_name}" in type_string:
                return str(member)
    return None


def _state_comparison(
    node: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> tuple[str, str] | None:
    if not isinstance(node, dict) or node.get("nodeType") != "BinaryOperation":
        return None
    operator = node.get("operator")
    if operator not in {"==", "!="}:
        return None
    left = node.get("leftExpression")
    right = node.get("rightExpression")
    if _matches_state_expression(left, profile):
        member = _enum_member(right, profile, enum_states)
        if member is not None:
            return str(operator), member
    if _matches_state_expression(right, profile):
        member = _enum_member(left, profile, enum_states)
        if member is not None:
            return str(operator), member
    return None


def _allowed_when_true(
    node: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> set[str] | None:
    comparison = _state_comparison(node, profile, enum_states)
    if comparison is not None:
        operator, member = comparison
        return {member} if operator == "==" else None
    if not isinstance(node, dict):
        return None
    if node.get("nodeType") == "BinaryOperation" and node.get("operator") == "||":
        left = _allowed_when_true(node.get("leftExpression"), profile, enum_states)
        right = _allowed_when_true(node.get("rightExpression"), profile, enum_states)
        if left is not None and right is not None:
            return left | right
    return None


def _allowed_when_false(
    node: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> set[str] | None:
    comparison = _state_comparison(node, profile, enum_states)
    if comparison is not None:
        operator, member = comparison
        return {member} if operator == "!=" else None
    if (
        isinstance(node, dict)
        and node.get("nodeType") == "UnaryOperation"
        and node.get("operator") == "!"
    ):
        return _allowed_when_true(node.get("subExpression"), profile, enum_states)
    return None


def _contains_revert(node: Any) -> bool:
    return any(
        candidate.get("nodeType") == "RevertStatement"
        for candidate in _walk(node)
    )


def _require_guard(
    statement: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> set[str] | None:
    if not isinstance(statement, dict) or statement.get("nodeType") != "ExpressionStatement":
        return None
    expression = statement.get("expression")
    if not isinstance(expression, dict) or expression.get("nodeType") != "FunctionCall":
        return None
    callee = expression.get("expression")
    if (
        not isinstance(callee, dict)
        or callee.get("nodeType") != "Identifier"
        or callee.get("name") != "require"
    ):
        return None
    arguments = expression.get("arguments", [])
    if not arguments:
        return None
    return _allowed_when_true(arguments[0], profile, enum_states)


def _if_revert_guard(
    statement: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> set[str] | None:
    if not isinstance(statement, dict) or statement.get("nodeType") != "IfStatement":
        return None
    if statement.get("falseBody") is not None:
        return None
    if not _contains_revert(statement.get("trueBody")):
        return None
    return _allowed_when_false(statement.get("condition"), profile, enum_states)


def _assignment_target(
    node: Any,
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> str | None:
    if (
        not isinstance(node, dict)
        or node.get("nodeType") != "Assignment"
        or node.get("operator") != "="
    ):
        return None
    if not _matches_state_expression(node.get("leftHandSide"), profile):
        return None
    return _enum_member(node.get("rightHandSide"), profile, enum_states)


def _function_source_states(
    function: Mapping[str, Any],
    profile: SolidityLifecycleProfile,
    enum_states: set[str],
) -> set[str] | None:
    body = function.get("body")
    if not isinstance(body, dict):
        return None
    allowed: set[str] | None = None
    for statement in body.get("statements", []):
        if any(
            _assignment_target(node, profile, enum_states)
            for node in _walk(statement)
        ):
            break
        candidate = _require_guard(statement, profile, enum_states)
        if candidate is None:
            candidate = _if_revert_guard(statement, profile, enum_states)
        if candidate is None:
            continue
        allowed = candidate if allowed is None else allowed & candidate
    return allowed if allowed else None


def extract_lifecycle_from_ast(
    ast: dict[str, Any],
    profile: SolidityLifecycleProfile,
) -> dict[str, object]:
    """Extract one lifecycle-liveness model plus deterministic extraction evidence."""

    _require(isinstance(ast, dict), "Solidity AST must be a JSON object")
    contract = _find_contract(ast, profile)
    enum_members = _enum_states(contract, profile)
    enum_set = set(enum_members)

    semantic_states = (
        {profile.initial_state}
        | set(profile.value_holding_states)
        | set(profile.safe_terminal_states)
    )
    unknown = sorted(semantic_states - enum_set)
    _require(
        not unknown,
        "profile references states absent from enum: " + ", ".join(unknown),
    )

    states = tuple(
        LifecycleState(
            id=state,
            description=f"Extracted {profile.contract_name}.{profile.enum_name}.{state}",
            holds_value=state in profile.value_holding_states,
            safe_terminal=state in profile.safe_terminal_states,
        )
        for state in enum_members
    )

    transitions: list[LifecycleTransition] = []
    evidence: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []

    functions = [
        node
        for node in contract.get("nodes", [])
        if isinstance(node, dict)
        and node.get("nodeType") == "FunctionDefinition"
        and node.get("kind") != "constructor"
        and isinstance(node.get("body"), dict)
    ]

    for function in functions:
        targets = sorted(
            {
                target
                for node in _walk(function.get("body"))
                if (target := _assignment_target(node, profile, enum_set)) is not None
            }
        )
        if not targets:
            continue

        function_name = str(
            function.get("name") or f"function-{function.get('id', 'unknown')}"
        )
        source_states = _function_source_states(function, profile, enum_set)
        if source_states is None:
            unresolved.append(
                {
                    "function": function_name,
                    "astNodeId": function.get("id"),
                    "targetStates": targets,
                    "reason": "state_write_without_unambiguous_entry_state_guard",
                }
            )
            continue

        for source in sorted(source_states):
            for target in targets:
                transition_id = f"{function_name}:{source}->{target}"
                transitions.append(
                    LifecycleTransition(
                        id=transition_id,
                        source=source,
                        target=target,
                    )
                )
                evidence.append(
                    {
                        "transitionId": transition_id,
                        "function": function_name,
                        "astNodeId": function.get("id"),
                        "sourceState": source,
                        "targetState": target,
                    }
                )

    transition_ids = [item.id for item in transitions]
    _require(
        len(transition_ids) == len(set(transition_ids)),
        "extracted transition ids are not unique; overloaded functions require a narrower profile",
    )

    model = LifecycleLivenessModel(
        states=states,
        transitions=tuple(
            sorted(transitions, key=lambda item: (item.source, item.target, item.id))
        ),
        initial_state=profile.initial_state,
        invariant_id=profile.invariant_id,
    )
    return {
        "schemaVersion": "solidity-lifecycle-extraction-v0.1",
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
        "stateSelector": profile.state_selector,
        "enumStates": list(enum_members),
        "model": lifecycle_liveness_model_to_dict(model),
        "transitionEvidence": sorted(
            evidence,
            key=lambda item: str(item["transitionId"]),
        ),
        "unresolvedStateWriters": unresolved,
        "scopeNote": (
            "Transitions are extracted only from supported compiler-AST guard/write shapes. "
            "Economic state meaning comes from the reviewed profile, not from inference."
        ),
    }


def check_lifecycle_from_ast(
    ast: dict[str, Any],
    profile: SolidityLifecycleProfile,
) -> dict[str, object]:
    extraction = extract_lifecycle_from_ast(ast, profile)
    if not extraction["extractionComplete"]:
        return {
            "schemaVersion": "solidity-lifecycle-check-v0.1",
            "status": "inconclusive",
            "extraction": extraction,
            "verification": None,
            "reason": "incomplete_state_transition_extraction",
        }

    model_data = extraction["model"]
    assert isinstance(model_data, dict)
    model = LifecycleLivenessModel(
        states=tuple(
            LifecycleState(
                id=str(item["id"]),
                description=str(item["description"]),
                holds_value=bool(item["holdsValue"]),
                safe_terminal=bool(item["safeTerminal"]),
            )
            for item in model_data["states"]
        ),
        transitions=tuple(
            LifecycleTransition(
                id=str(item["id"]),
                source=str(item["source"]),
                target=str(item["target"]),
            )
            for item in model_data["transitions"]
        ),
        initial_state=str(model_data["initialState"]),
        invariant_id=str(model_data["invariantId"]),
    )
    verification = run_lifecycle_liveness_model(model)
    return {
        "schemaVersion": "solidity-lifecycle-check-v0.1",
        "status": verification["status"],
        "extraction": extraction,
        "verification": verification,
    }


def load_ast_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    _require(
        isinstance(data, dict),
        "Solidity AST file must contain a JSON object",
    )
    return data


def _forge_output_directory(root: Path) -> Path:
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
    _require(isinstance(out, str) and bool(out.strip()), "forge config is missing output directory")
    output = Path(out)
    return output if output.is_absolute() else root / output


def _source_matches(candidate: str, requested: str) -> bool:
    candidate_norm = candidate.replace("\\", "/").lstrip("./")
    requested_norm = requested.replace("\\", "/").lstrip("./")
    return (
        candidate_norm == requested_norm
        or candidate_norm.endswith("/" + requested_norm)
    )


def _ast_candidates_from_build_info(
    build_info_dir: Path,
    requested_source: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in sorted(build_info_dir.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid Foundry build-info JSON: {path}") from exc
        if not isinstance(document, dict):
            raise ValueError(f"Foundry build-info must be a JSON object: {path}")
        output = document.get("output")
        if not isinstance(output, dict):
            continue
        sources = output.get("sources")
        if not isinstance(sources, dict):
            continue
        for source_name, source_data in sources.items():
            if not isinstance(source_name, str) or not _source_matches(
                source_name,
                requested_source,
            ):
                continue
            if not isinstance(source_data, dict):
                continue
            ast = source_data.get("ast")
            if isinstance(ast, dict):
                candidates.append(ast)
    return candidates


def load_forge_ast(target: str, root: Path | None = None) -> dict[str, Any]:
    """Compile with Foundry AST/build-info output and return one source-unit AST.

    Foundry 1.7 no longer exposes ``ast`` as a ``forge inspect`` field. The stable
    compiler-output path is ``forge build --ast --build-info`` followed by the
    standard compiler output at ``build-info[].output.sources[<source>].ast``.
    Multiple matching build-info records are accepted only when their AST bytes
    are semantically identical; divergent candidates fail closed.
    """

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

    build_info_dir = _forge_output_directory(project_root) / "build-info"
    _require(
        build_info_dir.is_dir(),
        f"Foundry build-info directory not found after AST build: {build_info_dir}",
    )
    candidates = _ast_candidates_from_build_info(build_info_dir, source)
    _require(candidates, f"AST not found in Foundry build-info for source: {source}")

    by_digest: dict[str, dict[str, Any]] = {}
    for ast in candidates:
        by_digest.setdefault(_canonical_sha256(ast), ast)
    _require(
        len(by_digest) == 1,
        f"ambiguous Foundry AST candidates for source: {source}",
    )
    return next(iter(by_digest.values()))
