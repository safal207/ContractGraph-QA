#!/usr/bin/env python3
"""Fail closed when ContractGraph-QA JSON Schemas drift from runtime contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.engagement import (  # noqa: E402
    CHECK_KEYS,
    ENGAGEMENT_RESULT_KEYS,
    SAFE_ARTIFACT_ID,
    STATUSES,
)
from contractgraph_qa.finding import (  # noqa: E402
    ACTION_KEYS,
    INVARIANT_KEYS,
    MANIFEST_KEYS,
    RESULT_KEYS,
    SCOPE_KEYS,
    SEARCH_KEYS,
    SEVERITIES,
    STEP_KEYS,
)
from contractgraph_qa.reachability import (  # noqa: E402
    ASSUMPTION_KEYS,
    CAPABILITY_KEYS,
    CAPABILITY_REQUIRED_KEYS,
    REACHABILITY_MODEL_KEYS,
    REACHABILITY_REQUIRED_KEYS,
    TRANSITION_KEYS,
    TRANSITION_REQUIRED_KEYS,
)
from contractgraph_qa.tsse import (  # noqa: E402
    ACTOR_KEYS as TSSE_ACTOR_KEYS,
    AUTHORITY_KEYS as TSSE_AUTHORITY_KEYS,
    DIMENSIONS as TSSE_DIMENSIONS,
    ENVIRONMENT_KEYS as TSSE_ENVIRONMENT_KEYS,
    EVIDENCE_KEYS as TSSE_EVIDENCE_KEYS,
    EXACT_SUBJECT_KEYS as TSSE_EXACT_SUBJECT_KEYS,
    FORBIDDEN_TRANSITION_KEYS as TSSE_FORBIDDEN_TRANSITION_KEYS,
    INVARIANT_KEYS as TSSE_INVARIANT_KEYS,
    INVARIANT_KINDS as TSSE_INVARIANT_KINDS,
    MODEL_KEYS as TSSE_MODEL_KEYS,
    MODEL_SCHEMA as TSSE_MODEL_SCHEMA,
    NODE_KEYS as TSSE_NODE_KEYS,
    REQUIREMENT_KEYS as TSSE_REQUIREMENT_KEYS,
    SPACE_KEYS as TSSE_SPACE_KEYS,
    STATE_KEYS as TSSE_STATE_KEYS,
    TIME_KEYS as TSSE_TIME_KEYS,
    TRANSITION_KEYS as TSSE_TRANSITION_KEYS,
    VALUE_KEYS as TSSE_VALUE_KEYS,
    run_tsse_model,
    validate_tsse_model,
)
from contractgraph_qa.tsse_adapters import (  # noqa: E402
    ACTOR_KEYS as TOOL_ACTOR_KEYS,
    AUTHORITY_KEYS as TOOL_AUTHORITY_KEYS,
    BOUND_KEYS as TOOL_BOUND_KEYS,
    CAPTURE_SCHEMA as TOOL_CAPTURE_SCHEMA_ID,
    ENVIRONMENT_KEYS as TOOL_ENVIRONMENT_KEYS,
    FORBIDDEN_TRANSITION_KEYS as TOOL_FORBIDDEN_TRANSITION_KEYS,
    INCOMING_KEYS as TOOL_INCOMING_KEYS,
    INVARIANT_KEYS as TOOL_INVARIANT_KEYS,
    NATIVE_BINDING_KEYS as TOOL_NATIVE_BINDING_KEYS,
    OBSERVATION_KEYS as TOOL_OBSERVATION_KEYS,
    PROFILE_KEYS as TOOL_PROFILE_KEYS,
    PROFILE_SCHEMA as TOOL_PROFILE_SCHEMA_ID,
    PRIMARY_ARTIFACT_KINDS as TOOL_PRIMARY_ARTIFACT_KINDS,
    RESULT_SCHEMA as TOOL_ADAPTER_RESULT_SCHEMA_ID,
    RUN_KEYS as TOOL_RUN_KEYS,
    RUN_TERMINATIONS as TOOL_RUN_TERMINATIONS,
    SPACE_KEYS as TOOL_SPACE_KEYS,
    STATE_KEYS as TOOL_STATE_KEYS,
    STATIC_SEED_KEYS as TOOL_STATIC_SEED_KEYS,
    SUBJECT_ARTIFACT_KEYS as TOOL_SUBJECT_ARTIFACT_KEYS,
    SUBJECT_KEYS as TOOL_SUBJECT_KEYS,
    TIME_KEYS as TOOL_TIME_KEYS,
    TOOLS as TOOL_NAMES,
    TOOL_ARTIFACT_KEYS,
    TOP_LEVEL_KEYS as TOOL_CAPTURE_KEYS,
    VALUE_KEYS as TOOL_VALUE_KEYS,
    SOURCE_LOCATION_KEYS as TOOL_SOURCE_LOCATION_KEYS,
    adapt_tool_capture_file,
    validate_tool_capture,
    validate_tool_profile,
)
from contractgraph_qa.graph_layers import (  # noqa: E402
    DIMENSIONS as GRAPH_DIMENSIONS,
    DIFF_SCHEMA as GRAPH_DIFF_SCHEMA_ID,
    EDGE_KEYS as GRAPH_EDGE_KEYS,
    EDGE_STATUSES as GRAPH_EDGE_STATUSES,
    LAYER_KEYS as GRAPH_LAYER_KEYS,
    LAYER_STATUSES as GRAPH_LAYER_STATUSES,
    ROOT_KEYS as GRAPH_ROOT_KEYS,
    SCHEMA as GRAPH_SCHEMA_ID,
)
from contractgraph_qa.action_guard import (  # noqa: E402
    ACTION_KEYS as ACTION_GUARD_ACTION_KEYS,
    ACTOR_KEYS as ACTION_GUARD_ACTOR_KEYS,
    AUTHORIZATION_KEYS as ACTION_GUARD_AUTHORIZATION_KEYS,
    CANARY_KEYS as ACTION_GUARD_CANARY_KEYS,
    CAPABILITY_LADDER as ACTION_GUARD_CAPABILITY_LADDER,
    DECISION_KEYS as ACTION_GUARD_DECISION_KEYS,
    HISTORY_KEYS as ACTION_GUARD_HISTORY_KEYS,
    RESULT_SCHEMA as ACTION_GUARD_RESULT_SCHEMA_ID,
    ROOT_KEYS as ACTION_GUARD_ROOT_KEYS,
    SCHEMA as ACTION_GUARD_SCHEMA_ID,
    WITNESS_KEYS as ACTION_GUARD_WITNESS_KEYS,
    evaluate_action_guard,
    validate_action_guard,
)

MANIFEST_SCHEMA = ROOT / "graph" / "schema" / "adapter-manifest.schema.json"
RESULT_SCHEMA = ROOT / "graph" / "schema" / "explorer-result.schema.json"
ENGAGEMENT_RESULT_SCHEMA = ROOT / "graph" / "schema" / "engagement-result.schema.json"
REACHABILITY_SCHEMA = ROOT / "graph" / "schema" / "adversarial-reachability.schema.json"
TSSE_SCHEMA = ROOT / "graph" / "schema" / "tsse-transition.schema.json"
TSSE_FIXTURE = ROOT / "scenarios" / "tsse-payment-lifecycle.json"
TSSE_TOOL_CAPTURE_SCHEMA = ROOT / "graph" / "schema" / "tsse-tool-capture.schema.json"
TSSE_TOOL_PROFILE_SCHEMA = ROOT / "graph" / "schema" / "tsse-tool-profile.schema.json"
TSSE_TOOL_RESULT_SCHEMA = ROOT / "graph" / "schema" / "tsse-tool-adapter-result.schema.json"
GRAPH_LAYERS_SCHEMA = ROOT / "graph" / "schema" / "graph-layers.schema.json"
GRAPH_LAYER_DIFF_SCHEMA = ROOT / "graph" / "schema" / "graph-layer-diff.schema.json"
ACTION_GUARD_SCHEMA = ROOT / "graph" / "schema" / "action-guard.schema.json"
ACTION_GUARD_RESULT_SCHEMA = ROOT / "graph" / "schema" / "action-guard-result.schema.json"
TSSE_FOUNDRY_CAPTURE = ROOT / "scenarios" / "tsse-tools" / "foundry-capture.json"
TSSE_FOUNDRY_PROFILE = ROOT / "scenarios" / "tsse-tools" / "foundry-profile.json"
TSSE_SOROBAN_CAPTURE = ROOT / "scenarios" / "tsse-tools" / "soroban-capture.json"
TSSE_SOROBAN_PROFILE = ROOT / "scenarios" / "tsse-tools" / "soroban-profile.json"
TSSE_SLITHER_CAPTURE = ROOT / "scenarios" / "tsse-tools" / "slither-capture.json"
TSSE_SLITHER_PROFILE = ROOT / "scenarios" / "tsse-tools" / "slither-profile.json"
NON_WHITESPACE_PATTERN = r"\S"
TSSE_TRIMMED_NON_WHITESPACE_PATTERN = r"^(?:\S|\S[\s\S]*\S)$"


class SchemaContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaContractError(message)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(data, dict), f"schema must be an object: {path}")
    return data


def _keys(schema: dict[str, Any], field: str) -> set[str]:
    props = schema.get("properties")
    _require(isinstance(props, dict), f"{field}.properties missing")
    return set(props)


def _required(schema: dict[str, Any], field: str) -> set[str]:
    required = schema.get("required")
    _require(isinstance(required, list), f"{field}.required missing")
    return set(required)


def _strict_object(schema: dict[str, Any], field: str) -> None:
    _require(schema.get("type") == "object", f"{field} must be type object")
    _require(schema.get("additionalProperties") is False, f"{field} must reject extra fields")


def _non_blank_string(schema: dict[str, Any], field: str) -> None:
    _require(schema.get("type") == "string", f"{field} must be a string")
    _require(schema.get("minLength") == 1, f"{field}.minLength must equal 1")
    _require(schema.get("pattern") == NON_WHITESPACE_PATTERN, f"{field}.pattern must equal \\S")


def _unique_string_array(
    schema: dict[str, Any], field: str, *, min_items: int | None = None
) -> None:
    _require(schema.get("type") == "array", f"{field} must be an array")
    _require(schema.get("uniqueItems") is True, f"{field} must require uniqueItems")
    if min_items is not None:
        _require(schema.get("minItems") == min_items, f"{field}.minItems drift")
    _non_blank_string(schema["items"], f"{field}[]")


def _nullable_non_blank_string(schema: dict[str, Any], field: str) -> None:
    one_of = schema.get("oneOf")
    _require(isinstance(one_of, list) and len(one_of) == 2, f"{field}.oneOf drift")
    null_entries = [entry for entry in one_of if isinstance(entry, dict) and entry.get("type") == "null"]
    string_entries = [entry for entry in one_of if isinstance(entry, dict) and entry.get("type") == "string"]
    _require(len(null_entries) == 1 and len(string_entries) == 1, f"{field} nullable type drift")
    _non_blank_string(string_entries[0], field)


def _non_blank_ref(schema: dict[str, Any], field: str, definition: str = "nonBlank") -> None:
    _require(
        schema == {"$ref": f"#/$defs/{definition}"},
        f"{field} must reference $defs.{definition}",
    )


def _step_contract(step: dict[str, Any], field: str) -> None:
    _strict_object(step, field)
    _require(_keys(step, field) == STEP_KEYS, f"{field} property set drift")
    _require(_required(step, field) == STEP_KEYS - {"parameter"}, f"{field} required set drift")
    for name in ("actionId", "preState", "postState", "effect"):
        _non_blank_string(step["properties"][name], f"{field}.{name}")
    parameter = step["properties"]["parameter"]
    one_of = parameter.get("oneOf")
    _require(isinstance(one_of, list), f"{field}.parameter.oneOf missing")
    _require(
        {entry.get("type") for entry in one_of if isinstance(entry, dict)} == {"integer", "string"},
        f"{field}.parameter type drift",
    )


def _reachability_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "reachabilityModel")
    _require(
        _keys(schema, "reachabilityModel") == REACHABILITY_MODEL_KEYS,
        "reachability model property set drift",
    )
    _require(
        _required(schema, "reachabilityModel") == REACHABILITY_REQUIRED_KEYS,
        "reachability model required set drift",
    )

    assumptions = schema["properties"]["assumptions"]
    _require(assumptions.get("type") == "array", "reachability assumptions must be array")
    assumption = schema["$defs"]["assumption"]
    _strict_object(assumption, "reachabilityModel.assumptions[]")
    _require(
        _keys(assumption, "reachabilityModel.assumptions[]") == ASSUMPTION_KEYS,
        "reachability assumption property set drift",
    )
    _require(
        _required(assumption, "reachabilityModel.assumptions[]") == ASSUMPTION_KEYS,
        "reachability assumption required set drift",
    )
    for name in sorted(ASSUMPTION_KEYS):
        _non_blank_string(
            assumption["properties"][name],
            f"reachabilityModel.assumptions[].{name}",
        )

    capabilities = schema["properties"]["capabilities"]
    _require(capabilities.get("type") == "array", "reachability capabilities must be array")
    _require(capabilities.get("minItems") == 1, "reachability capabilities.minItems drift")
    capability = schema["$defs"]["capability"]
    _strict_object(capability, "reachabilityModel.capabilities[]")
    _require(
        _keys(capability, "reachabilityModel.capabilities[]") == CAPABILITY_KEYS,
        "reachability capability property set drift",
    )
    _require(
        _required(capability, "reachabilityModel.capabilities[]") == CAPABILITY_REQUIRED_KEYS,
        "reachability capability required set drift",
    )
    for name in ("id", "description"):
        _non_blank_string(
            capability["properties"][name],
            f"reachabilityModel.capabilities[].{name}",
        )
    _require(
        capability["properties"]["forbidden"] == {"type": "boolean", "default": False},
        "reachability capability.forbidden drift",
    )

    transitions = schema["properties"]["transitions"]
    _require(transitions.get("type") == "array", "reachability transitions must be array")
    transition = schema["$defs"]["transition"]
    _strict_object(transition, "reachabilityModel.transitions[]")
    _require(
        _keys(transition, "reachabilityModel.transitions[]") == TRANSITION_KEYS,
        "reachability transition property set drift",
    )
    _require(
        _required(transition, "reachabilityModel.transitions[]") == TRANSITION_REQUIRED_KEYS,
        "reachability transition required set drift",
    )
    for name in ("id", "source", "target"):
        _non_blank_string(
            transition["properties"][name],
            f"reachabilityModel.transitions[].{name}",
        )
    _unique_string_array(
        transition["properties"]["requiresViolations"],
        "reachabilityModel.transitions[].requiresViolations",
    )
    for name in ("invariantId", "boundary", "impact"):
        _nullable_non_blank_string(
            transition["properties"][name],
            f"reachabilityModel.transitions[].{name}",
        )

    _unique_string_array(
        schema["properties"]["initialCapabilities"],
        "reachabilityModel.initialCapabilities",
        min_items=1,
    )
    _unique_string_array(
        schema["properties"]["targetCapabilities"],
        "reachabilityModel.targetCapabilities",
        min_items=1,
    )
    _unique_string_array(
        schema["properties"]["violatedAssumptions"],
        "reachabilityModel.violatedAssumptions",
    )
    _require(
        schema["properties"]["maxDepth"]
        == {"type": "integer", "minimum": 0, "default": 8},
        "reachability maxDepth schema drift",
    )


def _tsse_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "tsseModel")
    _require(_keys(schema, "tsseModel") == TSSE_MODEL_KEYS, "TSSE model property set drift")
    _require(_required(schema, "tsseModel") == TSSE_MODEL_KEYS, "TSSE model required set drift")
    _require(
        schema["properties"]["schema"].get("const") == TSSE_MODEL_SCHEMA,
        "TSSE schema identifier drift",
    )

    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "TSSE $defs missing")
    object_contracts = {
        "exactSubject": TSSE_EXACT_SUBJECT_KEYS,
        "evidence": TSSE_EVIDENCE_KEYS,
        "time": TSSE_TIME_KEYS,
        "space": TSSE_SPACE_KEYS,
        "state": TSSE_STATE_KEYS,
        "environment": TSSE_ENVIRONMENT_KEYS,
        "actor": TSSE_ACTOR_KEYS,
        "authority": TSSE_AUTHORITY_KEYS,
        "value": TSSE_VALUE_KEYS,
        "node": TSSE_NODE_KEYS,
        "transition": TSSE_TRANSITION_KEYS,
        "invariant": TSSE_INVARIANT_KEYS,
        "forbiddenTransition": TSSE_FORBIDDEN_TRANSITION_KEYS,
        "requirements": TSSE_REQUIREMENT_KEYS,
    }
    for name, expected_keys in object_contracts.items():
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"TSSE $defs.{name} missing")
        _strict_object(definition, f"tsseModel.{name}")
        _require(
            _keys(definition, f"tsseModel.{name}") == expected_keys,
            f"TSSE {name} property set drift",
        )
        _require(
            _required(definition, f"tsseModel.{name}") == expected_keys,
            f"TSSE {name} required set drift",
        )

    boundary = definitions.get("boundary")
    _require(isinstance(boundary, dict), "TSSE boundary definition missing")
    _require(
        boundary.get("enum") == list(TSSE_DIMENSIONS),
        "TSSE boundary enum/order drift",
    )
    invariant = definitions["invariant"]["properties"]["kind"]
    _require(
        set(invariant.get("enum", [])) == TSSE_INVARIANT_KINDS,
        "TSSE invariant kind enum drift",
    )
    _require(
        definitions.get("sha256") == {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "TSSE SHA-256 contract drift",
    )
    _require(
        definitions.get("nonBlank")
        == {
            "type": "string",
            "minLength": 1,
            "pattern": TSSE_TRIMMED_NON_WHITESPACE_PATTERN,
        },
        "TSSE trimmed non-blank string contract drift",
    )

    fixture = json.loads(TSSE_FIXTURE.read_text(encoding="utf-8"))
    validate_tsse_model(fixture)
    fixture_result = run_tsse_model(fixture)
    _require(fixture_result.get("status") == "pass", "TSSE fixture must remain a passing trace")


def _tsse_tool_capture_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "tsseToolCapture")
    _require(
        _keys(schema, "tsseToolCapture") == TOOL_CAPTURE_KEYS,
        "TSSE tool capture property set drift",
    )
    _require(
        _required(schema, "tsseToolCapture") == TOOL_CAPTURE_KEYS,
        "TSSE tool capture required set drift",
    )
    _require(
        schema["properties"]["schema"].get("const") == TOOL_CAPTURE_SCHEMA_ID,
        "TSSE tool capture schema identifier drift",
    )
    _require(
        set(schema["properties"]["tool"].get("enum", [])) == set(TOOL_NAMES),
        "TSSE tool enum drift",
    )

    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "TSSE tool capture $defs missing")
    object_contracts = {
        "subject": TOOL_SUBJECT_KEYS,
        "subjectArtifact": TOOL_SUBJECT_ARTIFACT_KEYS,
        "toolArtifact": TOOL_ARTIFACT_KEYS,
        "run": TOOL_RUN_KEYS,
        "bounds": TOOL_BOUND_KEYS,
        "observation": TOOL_OBSERVATION_KEYS,
        "incoming": TOOL_INCOMING_KEYS,
        "time": TOOL_TIME_KEYS,
        "space": TOOL_SPACE_KEYS,
        "state": TOOL_STATE_KEYS,
        "environment": TOOL_ENVIRONMENT_KEYS,
        "actor": TOOL_ACTOR_KEYS,
        "authority": TOOL_AUTHORITY_KEYS,
        "value": TOOL_VALUE_KEYS,
        "invariant": TOOL_INVARIANT_KEYS,
        "forbiddenTransition": TOOL_FORBIDDEN_TRANSITION_KEYS,
    }
    for name, expected_keys in object_contracts.items():
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"TSSE tool capture $defs.{name} missing")
        _strict_object(definition, f"tsseToolCapture.{name}")
        _require(
            _keys(definition, f"tsseToolCapture.{name}") == expected_keys,
            f"TSSE tool capture {name} property set drift",
        )
        _require(
            _required(definition, f"tsseToolCapture.{name}") == expected_keys,
            f"TSSE tool capture {name} required set drift",
        )

    _require(
        set(definitions["run"]["properties"]["termination"].get("enum", []))
        == set(TOOL_RUN_TERMINATIONS),
        "TSSE tool termination enum drift",
    )
    _require(
        set(definitions["invariant"]["properties"]["kind"].get("enum", []))
        == TSSE_INVARIANT_KINDS,
        "TSSE tool invariant kind enum drift",
    )

    branches = schema.get("allOf")
    _require(isinstance(branches, list), "TSSE tool capture allOf policy missing")
    for tool, artifact_kind in TOOL_PRIMARY_ARTIFACT_KINDS.items():
        matching = []
        for branch in branches:
            branch_tool = (
                branch.get("if", {})
                .get("properties", {})
                .get("tool", {})
                .get("const")
            )
            declared_kind = (
                branch.get("then", {})
                .get("properties", {})
                .get("toolArtifacts", {})
                .get("contains", {})
                .get("properties", {})
                .get("kind", {})
                .get("const")
            )
            if branch_tool == tool and declared_kind == artifact_kind:
                matching.append(branch)
        _require(
            len(matching) == 1,
            f"TSSE tool capture primary artifact policy drift for {tool}",
        )

    foundry_fixture = json.loads(TSSE_FOUNDRY_CAPTURE.read_text(encoding="utf-8"))
    soroban_fixture = json.loads(TSSE_SOROBAN_CAPTURE.read_text(encoding="utf-8"))
    slither_fixture = json.loads(TSSE_SLITHER_CAPTURE.read_text(encoding="utf-8"))
    validate_tool_capture(foundry_fixture)
    validate_tool_capture(soroban_fixture)
    validate_tool_capture(slither_fixture)
    foundry_result = adapt_tool_capture_file(TSSE_FOUNDRY_CAPTURE, TSSE_FOUNDRY_PROFILE)
    soroban_result = adapt_tool_capture_file(TSSE_SOROBAN_CAPTURE, TSSE_SOROBAN_PROFILE)
    slither_result = adapt_tool_capture_file(TSSE_SLITHER_CAPTURE, TSSE_SLITHER_PROFILE)
    _require(foundry_result.get("status") == "ready", "Foundry adapter fixture must be ready")
    _require(
        foundry_result.get("scanVerdict") == "NOT_ASSESSED",
        "Foundry adapter fixture must not emit a scan verdict",
    )
    _require(
        soroban_result.get("status") == "ready",
        "Soroban adapter fixture must be ready",
    )
    _require(
        soroban_result.get("scanVerdict") == "NOT_ASSESSED",
        "Soroban adapter fixture must not emit a scan verdict",
    )
    _require(
        soroban_result.get("nativeEvidence", {}).get("framework") == "soroban",
        "Soroban adapter fixture must bind Soroban-native evidence",
    )
    _require(
        slither_result.get("status") == "inconclusive",
        "Slither adapter fixture must remain inconclusive",
    )
    _require("tsseModel" not in slither_result, "Slither must not emit a TSSE model")


def _tsse_tool_profile_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "tsseToolProfile")
    _require(
        _keys(schema, "tsseToolProfile") == TOOL_PROFILE_KEYS,
        "TSSE tool profile property set drift",
    )
    _require(
        _required(schema, "tsseToolProfile") == TOOL_PROFILE_KEYS,
        "TSSE tool profile required set drift",
    )
    _require(
        schema["properties"]["schema"].get("const") == TOOL_PROFILE_SCHEMA_ID,
        "TSSE tool profile schema identifier drift",
    )
    _require(
        set(schema["properties"]["tool"].get("enum", [])) == set(TOOL_NAMES),
        "TSSE tool profile tool enum drift",
    )

    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "TSSE tool profile $defs missing")
    _require(
        definitions.get("nonBlank")
        == {
            "type": "string",
            "minLength": 1,
            "pattern": TSSE_TRIMMED_NON_WHITESPACE_PATTERN,
        },
        "TSSE tool profile nonBlank drift",
    )
    _require(
        definitions.get("sha256") == {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "TSSE tool profile SHA-256 drift",
    )
    object_contracts = {
        "subject": TOOL_SUBJECT_KEYS,
        "subjectArtifact": TOOL_SUBJECT_ARTIFACT_KEYS,
        "invariant": TOOL_INVARIANT_KEYS,
        "forbiddenTransition": TOOL_FORBIDDEN_TRANSITION_KEYS,
    }
    for name, expected_keys in object_contracts.items():
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"TSSE tool profile $defs.{name} missing")
        _strict_object(definition, f"tsseToolProfile.{name}")
        _require(
            _keys(definition, f"tsseToolProfile.{name}") == expected_keys,
            f"TSSE tool profile {name} property set drift",
        )
        _require(
            _required(definition, f"tsseToolProfile.{name}") == expected_keys,
            f"TSSE tool profile {name} required set drift",
        )

    versions = schema["properties"]["acceptedToolVersions"]
    _require(versions.get("type") == "array", "acceptedToolVersions must be an array")
    _require(versions.get("minItems") == 1, "acceptedToolVersions.minItems drift")
    _require(versions.get("uniqueItems") is True, "acceptedToolVersions uniqueness drift")
    _require(
        versions.get("items") == {"$ref": "#/$defs/nonBlank"},
        "acceptedToolVersions item contract drift",
    )

    exit_codes = schema["properties"]["acceptedExitCodes"]
    _require(exit_codes.get("type") == "array", "acceptedExitCodes must be an array")
    _require(exit_codes.get("minItems") == 1, "acceptedExitCodes.minItems drift")
    _require(exit_codes.get("uniqueItems") is True, "acceptedExitCodes uniqueness drift")
    _require(
        exit_codes.get("items") == {"type": "integer", "minimum": 0},
        "acceptedExitCodes item contract drift",
    )
    observation_hash = schema["properties"]["observationHash"]
    _require(
        observation_hash.get("oneOf")
        == [{"$ref": "#/$defs/sha256"}, {"type": "null"}],
        "TSSE tool profile observationHash contract drift",
    )
    _require(
        set(definitions["invariant"]["properties"]["kind"].get("enum", []))
        == TSSE_INVARIANT_KINDS,
        "TSSE tool profile invariant kind enum drift",
    )

    foundry_profile = json.loads(TSSE_FOUNDRY_PROFILE.read_text(encoding="utf-8"))
    soroban_profile = json.loads(TSSE_SOROBAN_PROFILE.read_text(encoding="utf-8"))
    slither_profile = json.loads(TSSE_SLITHER_PROFILE.read_text(encoding="utf-8"))
    validate_tool_profile(foundry_profile)
    validate_tool_profile(soroban_profile)
    validate_tool_profile(slither_profile)


def _tsse_tool_result_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "tsseToolResult")
    _require(
        schema["properties"]["schema"].get("const")
        == TOOL_ADAPTER_RESULT_SCHEMA_ID,
        "TSSE tool result schema identifier drift",
    )
    _require(
        set(schema["properties"]["tool"].get("enum", [])) == set(TOOL_NAMES),
        "TSSE tool result tool enum drift",
    )
    _require(
        schema["properties"]["scanVerdict"].get("const") == "NOT_ASSESSED",
        "TSSE tool result scan-verdict boundary drift",
    )

    foundry_result = adapt_tool_capture_file(TSSE_FOUNDRY_CAPTURE, TSSE_FOUNDRY_PROFILE)
    slither_result = adapt_tool_capture_file(TSSE_SLITHER_CAPTURE, TSSE_SLITHER_PROFILE)
    foundry_keys = set(foundry_result)
    slither_keys = set(slither_result)
    _require(
        _keys(schema, "tsseToolResult") == foundry_keys | slither_keys,
        "TSSE tool result property set drift",
    )
    _require(
        _required(schema, "tsseToolResult") == foundry_keys & slither_keys,
        "TSSE tool result common required set drift",
    )
    _require(
        foundry_keys - slither_keys == {"nativeBindings", "tsseModel", "tsseResult"},
        "TSSE dynamic result branch drift",
    )
    _require(
        slither_keys - foundry_keys == {"slitherSuccess", "toolError", "staticSeeds"},
        "TSSE static result branch drift",
    )

    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "TSSE tool result $defs missing")
    _require(
        definitions.get("sha256") == {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "TSSE tool result SHA-256 drift",
    )
    object_contracts = {
        "nativeBinding": TOOL_NATIVE_BINDING_KEYS,
        "staticSeed": TOOL_STATIC_SEED_KEYS,
        "sourceLocation": TOOL_SOURCE_LOCATION_KEYS,
        "run": TOOL_RUN_KEYS,
        "bounds": TOOL_BOUND_KEYS,
    }
    for name, expected_keys in object_contracts.items():
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"TSSE tool result $defs.{name} missing")
        _strict_object(definition, f"tsseToolResult.{name}")
        _require(
            _keys(definition, f"tsseToolResult.{name}") == expected_keys,
            f"TSSE tool result {name} property set drift",
        )
        _require(
            _required(definition, f"tsseToolResult.{name}") == expected_keys,
            f"TSSE tool result {name} required set drift",
        )


def _graph_layers_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "graphLayers")
    _require(
        _keys(schema, "graphLayers") == GRAPH_ROOT_KEYS,
        "graph layers property set drift",
    )
    _require(
        _required(schema, "graphLayers") == GRAPH_ROOT_KEYS,
        "graph layers required set drift",
    )
    _require(
        schema["properties"]["schema"].get("const") == GRAPH_SCHEMA_ID,
        "graph layers schema identifier drift",
    )
    _non_blank_ref(schema["properties"]["graphId"], "graphLayers.graphId")

    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "graph layers $defs missing")
    for layer_name in ("idea", "plan", "fact"):
        definition_name = f"{layer_name}Layer"
        layer = definitions.get(definition_name)
        _require(isinstance(layer, dict), f"graph layers $defs.{definition_name} missing")
        _strict_object(layer, f"graphLayers.{layer_name}")
        _require(
            _keys(layer, f"graphLayers.{layer_name}") == GRAPH_LAYER_KEYS,
            f"graph {layer_name} layer property set drift",
        )
        _require(
            _required(layer, f"graphLayers.{layer_name}") == GRAPH_LAYER_KEYS,
            f"graph {layer_name} layer required set drift",
        )
        _require(
            schema["properties"][layer_name]
            == {"$ref": f"#/$defs/{definition_name}"},
            f"graph {layer_name} layer ref drift",
        )
        edges = layer["properties"]["edges"]
        _require(edges.get("type") == "array", f"graph {layer_name} edges must be an array")
        policy = edges.get("items", {}).get("allOf")
        _require(
            isinstance(policy, list) and len(policy) == 2,
            f"graph {layer_name} edge status policy missing",
        )
        _require(policy[0] == {"$ref": "#/$defs/edge"}, f"graph {layer_name} edge ref drift")
        declared_status = policy[1].get("properties", {}).get("status", {})
        allowed_statuses = GRAPH_LAYER_STATUSES[layer_name]
        if len(allowed_statuses) == 1:
            _require(
                declared_status.get("const") == next(iter(allowed_statuses)),
                f"graph {layer_name} status policy drift",
            )
        else:
            _require(
                set(declared_status.get("enum", [])) == set(allowed_statuses),
                f"graph {layer_name} status policy drift",
            )
    edge = definitions.get("edge")
    _require(isinstance(edge, dict), "graph layers $defs.edge missing")
    _strict_object(edge, "graphLayers.edge")
    _require(_keys(edge, "graphLayers.edge") == GRAPH_EDGE_KEYS, "graph edge property set drift")
    _require(_required(edge, "graphLayers.edge") == GRAPH_EDGE_KEYS, "graph edge required set drift")
    for name in ("id", "from", "to", "evidence"):
        _non_blank_ref(edge["properties"][name], f"graphLayers.edge.{name}")
    dimensions = edge["properties"]["dimensions"]
    _require(dimensions.get("type") == "array", "graph edge dimensions must be an array")
    _require(dimensions.get("minItems") == 1, "graph edge dimensions.minItems drift")
    _require(dimensions.get("uniqueItems") is True, "graph edge dimensions uniqueness drift")
    dimension = definitions.get("dimension")
    _require(isinstance(dimension, dict), "graph layers $defs.dimension missing")
    _require(set(dimension.get("enum", [])) == set(GRAPH_DIMENSIONS), "graph dimensions enum drift")
    status = edge["properties"]["status"]
    _require(set(status.get("enum", [])) == set(GRAPH_EDGE_STATUSES), "graph edge status enum drift")


def _graph_layer_diff_contract(schema: dict[str, Any]) -> None:
    _strict_object(schema, "graphLayerDiff")
    expected_keys = {
        "schema",
        "graphId",
        "status",
        "ideaEdgeCount",
        "plannedEdgeCount",
        "factEdgeCount",
        "unplannedIdeaEdgeIds",
        "missingFactEdgeIds",
        "unexpectedFactEdgeIds",
        "unevidencedFactEdgeIds",
        "geometryMismatches",
        "claimBoundary",
    }
    _require(_keys(schema, "graphLayerDiff") == expected_keys, "graph layer diff property set drift")
    _require(_required(schema, "graphLayerDiff") == expected_keys, "graph layer diff required set drift")
    _require(
        schema["properties"]["schema"].get("const") == GRAPH_DIFF_SCHEMA_ID,
        "graph layer diff schema identifier drift",
    )
    _non_blank_ref(schema["properties"]["graphId"], "graphLayerDiff.graphId")
    _require(
        set(schema["properties"]["status"].get("enum", [])) == {"aligned", "drift_detected"},
        "graph layer diff status enum drift",
    )
    for name in ("ideaEdgeCount", "plannedEdgeCount", "factEdgeCount"):
        _require(
            schema["properties"][name] == {"type": "integer", "minimum": 0},
            f"graph layer diff {name} contract drift",
        )
    for name in (
        "unplannedIdeaEdgeIds",
        "missingFactEdgeIds",
        "unexpectedFactEdgeIds",
        "unevidencedFactEdgeIds",
    ):
        ids = schema["properties"][name]
        _require(ids.get("$ref") == "#/$defs/idList", f"graph layer diff {name} ref drift")
    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "graph layer diff $defs missing")
    id_list = definitions.get("idList")
    _require(isinstance(id_list, dict), "graph layer diff $defs.idList missing")
    _require(id_list.get("type") == "array", "graph layer diff idList type drift")
    _require(id_list.get("uniqueItems") is True, "graph layer diff idList uniqueness drift")
    _require(id_list.get("items") == {"$ref": "#/$defs/nonBlank"}, "graph layer diff idList item drift")
    mismatch = definitions.get("geometryMismatch")
    _require(isinstance(mismatch, dict), "graph layer diff $defs.geometryMismatch missing")
    _strict_object(mismatch, "graphLayerDiff.geometryMismatch")
    _require(
        _keys(mismatch, "graphLayerDiff.geometryMismatch")
        == {"edgeId", "boundary", "expected", "actual"},
        "graph layer diff mismatch property set drift",
    )
    _require(
        _required(mismatch, "graphLayerDiff.geometryMismatch")
        == {"edgeId", "boundary", "expected", "actual"},
        "graph layer diff mismatch required set drift",
    )
    _non_blank_ref(mismatch["properties"]["edgeId"], "graphLayerDiff.geometryMismatch.edgeId")
    _require(
        set(mismatch["properties"]["boundary"].get("enum", []))
        == {"idea-plan", "plan-fact"},
        "graph layer diff mismatch boundary enum drift",
    )
    for name in ("expected", "actual"):
        _require(
            mismatch["properties"][name].get("$ref") == "#/$defs/geometry",
            f"graph layer diff {name} geometry ref drift",
        )
    geometry = definitions.get("geometry")
    _require(isinstance(geometry, dict), "graph layer diff $defs.geometry missing")
    _require(geometry.get("type") == "array", "graph layer diff geometry type drift")
    _require(geometry.get("minItems") == 3 and geometry.get("maxItems") == 3, "graph layer diff geometry arity drift")
    _require(geometry.get("items") is False, "graph layer diff geometry must reject extra items")
    prefix = geometry.get("prefixItems")
    _require(isinstance(prefix, list) and len(prefix) == 3, "graph layer diff geometry tuple drift")
    _require(prefix[0] == {"$ref": "#/$defs/nonBlank"}, "graph layer diff geometry.from drift")
    _require(prefix[1] == {"$ref": "#/$defs/nonBlank"}, "graph layer diff geometry.to drift")
    _require(prefix[2].get("type") == "array", "graph layer diff geometry dimensions drift")


def _action_guard_contract(schema: dict[str, Any], result_schema: dict[str, Any]) -> None:
    """Keep the strict Action Guard JSON contracts aligned with its evaluator."""

    _strict_object(schema, "actionGuard")
    _require(_keys(schema, "actionGuard") == set(ACTION_GUARD_ROOT_KEYS), "action guard property set drift")
    _require(_required(schema, "actionGuard") == set(ACTION_GUARD_ROOT_KEYS), "action guard required set drift")
    _require(
        schema["properties"]["schema"].get("const") == ACTION_GUARD_SCHEMA_ID,
        "action guard schema identifier drift",
    )
    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "action guard $defs missing")
    for name, expected_keys in (
        ("actor", ACTION_GUARD_ACTOR_KEYS),
        ("authorization", ACTION_GUARD_AUTHORIZATION_KEYS),
        ("canaries", ACTION_GUARD_CANARY_KEYS),
        ("history", ACTION_GUARD_HISTORY_KEYS),
        ("action", ACTION_GUARD_ACTION_KEYS),
        ("decision", ACTION_GUARD_DECISION_KEYS),
        ("witness", ACTION_GUARD_WITNESS_KEYS),
    ):
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"action guard $defs.{name} missing")
        _strict_object(definition, f"actionGuard.{name}")
        _require(
            _keys(definition, f"actionGuard.{name}") == set(expected_keys),
            f"action guard {name} property set drift",
        )
        _require(
            _required(definition, f"actionGuard.{name}") == set(expected_keys),
            f"action guard {name} required set drift",
        )
    _require(
        set(definitions["authorization"]["properties"]["maxCapability"].get("enum", []))
        == set(ACTION_GUARD_CAPABILITY_LADDER),
        "action guard capability ladder drift",
    )
    _require(
        definitions["action"]["properties"]["pathAccess"].get("enum")
        == ["NONE", "READ", "WRITE"],
        "action guard path access drift",
    )
    _require(
        definitions["decision"]["properties"]["decision"].get("enum")
        == ["ALLOW", "DENY"],
        "action guard decision drift",
    )

    _strict_object(result_schema, "actionGuardResult")
    result_keys = {
        "schema",
        "status",
        "guardStatus",
        "agentConformance",
        "evidenceStatus",
        "subjectHash",
        "authorizationRef",
        "authorizationHash",
        "inputHash",
        "history",
        "actionResults",
        "findings",
        "metrics",
        "claimBoundary",
        "resultHash",
    }
    _require(_keys(result_schema, "actionGuardResult") == result_keys, "action guard result property set drift")
    _require(_required(result_schema, "actionGuardResult") == result_keys, "action guard result required set drift")
    _require(
        result_schema["properties"]["schema"].get("const") == ACTION_GUARD_RESULT_SCHEMA_ID,
        "action guard result schema identifier drift",
    )
    result_defs = result_schema.get("$defs")
    _require(isinstance(result_defs, dict), "action guard result $defs missing")
    for name in ("history", "actionResult", "finding", "metrics"):
        definition = result_defs.get(name)
        _require(isinstance(definition, dict), f"action guard result $defs.{name} missing")
        _strict_object(definition, f"actionGuardResult.{name}")
    _require(
        _keys(result_defs["history"], "actionGuardResult.history")
        == {"previousResultHash", "declaredPriorDeniedSemanticActionIds", "effectiveDeniedSemanticActionIds", "independentlyVerified"},
        "action guard result history property set drift",
    )
    _require(
        _required(result_defs["history"], "actionGuardResult.history")
        == {"previousResultHash", "declaredPriorDeniedSemanticActionIds", "effectiveDeniedSemanticActionIds", "independentlyVerified"},
        "action guard result history required set drift",
    )
    _require(
        result_defs["history"]["properties"]["independentlyVerified"].get("const") is False,
        "action guard result history verification claim drift",
    )


def _action_guard_runtime_contract(
    schema: dict[str, Any], result_schema: dict[str, Any]
) -> None:
    """Keep the process-execution boundary aligned with its JSON schemas."""

    _strict_object(schema, "actionGuardRuntime")
    _require(
        _keys(schema, "actionGuardRuntime") == set(ACTION_GUARD_RUNTIME_ROOT_KEYS),
        "action guard runtime property set drift",
    )
    _require(
        _required(schema, "actionGuardRuntime") == set(ACTION_GUARD_RUNTIME_ROOT_KEYS),
        "action guard runtime required set drift",
    )
    _require(
        schema["properties"]["schema"].get("const") == ACTION_GUARD_RUNTIME_SCHEMA_ID,
        "action guard runtime schema identifier drift",
    )
    _require(
        schema["properties"]["guard"].get("$ref") == "action-guard.schema.json",
        "action guard runtime guard reference drift",
    )
    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "action guard runtime $defs missing")
    for name, expected_keys in (
        ("command", ACTION_GUARD_RUNTIME_COMMAND_KEYS),
        ("execution", ACTION_GUARD_RUNTIME_EXECUTION_KEYS),
    ):
        definition = definitions.get(name)
        _require(isinstance(definition, dict), f"action guard runtime $defs.{name} missing")
        _strict_object(definition, f"actionGuardRuntime.{name}")
        _require(
            _keys(definition, f"actionGuardRuntime.{name}") == set(expected_keys),
            f"action guard runtime {name} property set drift",
        )
        _require(
            _required(definition, f"actionGuardRuntime.{name}") == set(expected_keys),
            f"action guard runtime {name} required set drift",
        )
    _require(
        definitions["execution"]["properties"]["mode"].get("enum")
        == list(ACTION_GUARD_RUNTIME_EXECUTION_MODES),
        "action guard runtime execution mode drift",
    )
    _require(
        definitions["command"]["properties"]["bindingHash"].get("$ref")
        == "#/$defs/sha256",
        "action guard runtime binding hash reference drift",
    )

    _strict_object(result_schema, "actionGuardRuntimeResult")
    result_keys = {
        "schema",
        "requestId",
        "status",
        "executionStatus",
        "containmentStatus",
        "requestHash",
        "preflightHash",
        "preflight",
        "postflight",
        "commandReceipts",
        "findings",
        "claimBoundary",
        "resultHash",
    }
    _require(
        _keys(result_schema, "actionGuardRuntimeResult") == result_keys,
        "action guard runtime result property set drift",
    )
    _require(
        _required(result_schema, "actionGuardRuntimeResult") == result_keys,
        "action guard runtime result required set drift",
    )
    _require(
        result_schema["properties"]["schema"].get("const")
        == ACTION_GUARD_RUNTIME_RESULT_SCHEMA_ID,
        "action guard runtime result schema identifier drift",
    )
    result_defs = result_schema.get("$defs")
    _require(isinstance(result_defs, dict), "action guard runtime result $defs missing")
    for name, expected_keys in (
        ("finding", {"code", "severity", "actionId"}),
        ("receipt", ACTION_GUARD_RUNTIME_RECEIPT_KEYS),
    ):
        definition = result_defs.get(name)
        _require(isinstance(definition, dict), f"action guard runtime result $defs.{name} missing")
        _strict_object(definition, f"actionGuardRuntimeResult.{name}")
        _require(
            _keys(definition, f"actionGuardRuntimeResult.{name}") == set(expected_keys),
            f"action guard runtime result {name} property set drift",
        )
        _require(
            _required(definition, f"actionGuardRuntimeResult.{name}") == set(expected_keys),
            f"action guard runtime result {name} required set drift",
        )


def _action_guard_witness_contract(schema: dict[str, Any]) -> None:
    """Keep the independent witness input aligned with its JSON schema."""

    _strict_object(schema, "actionGuardWitness")
    _require(
        _keys(schema, "actionGuardWitness") == set(ACTION_GUARD_WITNESS_ROOT_KEYS),
        "action guard witness property set drift",
    )
    _require(
        _required(schema, "actionGuardWitness") == set(ACTION_GUARD_WITNESS_ROOT_KEYS),
        "action guard witness required set drift",
    )
    _require(
        schema["properties"]["schema"].get("const") == ACTION_GUARD_WITNESS_SCHEMA_ID,
        "action guard witness schema identifier drift",
    )
    definitions = schema.get("$defs")
    _require(isinstance(definitions, dict), "action guard witness $defs missing")
    witness = definitions.get("witness")
    _require(isinstance(witness, dict), "action guard witness $defs.witness missing")
    _strict_object(witness, "actionGuardWitness.witness")
    _require(
        _keys(witness, "actionGuardWitness.witness") == set(ACTION_GUARD_WITNESS_KEYS),
        "action guard witness witness property set drift",
    )
    _require(
        _required(witness, "actionGuardWitness.witness") == set(ACTION_GUARD_WITNESS_KEYS),
        "action guard witness witness required set drift",
    )
    _require(
        witness["properties"]["outcome"].get("enum")
        == ["NOT_EXECUTED", "STOPPED", "EXECUTED"],
        "action guard witness outcome drift",
    )


def check_schema_contract() -> dict[str, Any]:
    manifest = _load(MANIFEST_SCHEMA)
    result = _load(RESULT_SCHEMA)
    engagement_result = _load(ENGAGEMENT_RESULT_SCHEMA)
    reachability = _load(REACHABILITY_SCHEMA)
    tsse = _load(TSSE_SCHEMA)
    tsse_tool_capture = _load(TSSE_TOOL_CAPTURE_SCHEMA)
    tsse_tool_profile = _load(TSSE_TOOL_PROFILE_SCHEMA)
    tsse_tool_result = _load(TSSE_TOOL_RESULT_SCHEMA)
    graph_layers = _load(GRAPH_LAYERS_SCHEMA)
    graph_layer_diff = _load(GRAPH_LAYER_DIFF_SCHEMA)
    action_guard = _load(ACTION_GUARD_SCHEMA)
    action_guard_result = _load(ACTION_GUARD_RESULT_SCHEMA)

    _strict_object(manifest, "manifest")
    _require(_keys(manifest, "manifest") == MANIFEST_KEYS, "manifest property set drift")
    _require(_required(manifest, "manifest") == MANIFEST_KEYS, "manifest required set drift")
    _require(manifest["properties"]["schemaVersion"].get("const") == 1, "manifest schemaVersion drift")
    for name in ("adapterId", "contract", "network"):
        _non_blank_string(manifest["properties"][name], f"manifest.{name}")

    scope = manifest["properties"]["scope"]
    _strict_object(scope, "manifest.scope")
    _require(_keys(scope, "manifest.scope") == SCOPE_KEYS, "manifest.scope property set drift")
    _require(_required(scope, "manifest.scope") == SCOPE_KEYS, "manifest.scope required set drift")
    for name in sorted(SCOPE_KEYS):
        _non_blank_string(scope["properties"][name], f"manifest.scope.{name}")

    search = manifest["properties"]["search"]
    _strict_object(search, "manifest.search")
    _require(_keys(search, "manifest.search") == SEARCH_KEYS, "manifest.search property set drift")
    _require(_required(search, "manifest.search") == SEARCH_KEYS, "manifest.search required set drift")
    _require(search["properties"]["maxDepth"] == {"type": "integer", "minimum": 1}, "maxDepth schema drift")

    state_fields = manifest["properties"]["stateFields"]
    _require(state_fields.get("type") == "array", "stateFields must be an array")
    _require(state_fields.get("minItems") == 1, "stateFields.minItems drift")
    _require(state_fields.get("uniqueItems") is True, "stateFields must require uniqueItems")
    _non_blank_string(state_fields["items"], "manifest.stateFields[]")

    action = manifest["properties"]["actions"]["items"]
    _strict_object(action, "manifest.actions[]")
    _require(_keys(action, "manifest.actions[]") == ACTION_KEYS, "action property set drift")
    _require(_required(action, "manifest.actions[]") == ACTION_KEYS, "action required set drift")
    for name in sorted(ACTION_KEYS):
        _non_blank_string(action["properties"][name], f"manifest.actions[].{name}")

    invariant = manifest["properties"]["invariants"]["items"]
    _strict_object(invariant, "manifest.invariants[]")
    _require(_keys(invariant, "manifest.invariants[]") == INVARIANT_KEYS, "invariant property set drift")
    _require(_required(invariant, "manifest.invariants[]") == INVARIANT_KEYS, "invariant required set drift")
    for name in sorted(INVARIANT_KEYS - {"severity"}):
        _non_blank_string(invariant["properties"][name], f"manifest.invariants[].{name}")
    severity = invariant["properties"]["severity"]
    _non_blank_string(severity, "manifest.invariants[].severity")
    _require(set(severity.get("enum", [])) == SEVERITIES, "severity enum drift")

    _strict_object(result, "result")
    _require(_keys(result, "result") == RESULT_KEYS, "result property set drift")
    expected_result_required = RESULT_KEYS - {"exploredCandidates", "notes"}
    _require(_required(result, "result") == expected_result_required, "result required set drift")
    for name in ("adapterId", "scopeId", "findingId", "invariantId", "replay"):
        _non_blank_string(result["properties"][name], f"result.{name}")
    fingerprint = result["properties"]["manifestSha256"]
    _require(fingerprint.get("type") == "string", "result.manifestSha256 must be string")
    _require(fingerprint.get("pattern") == "^[0-9a-f]{64}$", "manifestSha256 pattern drift")
    _non_blank_string(result["properties"]["notes"], "result.notes")
    _require(
        result["properties"]["exploredCandidates"] == {"type": "integer", "minimum": 0},
        "exploredCandidates schema drift",
    )
    path = result["properties"]["path"]
    _require(path.get("type") == "array", "result.path must be an array")
    _require(path.get("minItems") == 1, "result.path.minItems drift")
    _step_contract(path["items"], "result.path[]")

    _strict_object(engagement_result, "engagementResult")
    _require(
        _keys(engagement_result, "engagementResult") == ENGAGEMENT_RESULT_KEYS,
        "engagement result property set drift",
    )
    _require(
        _required(engagement_result, "engagementResult") == ENGAGEMENT_RESULT_KEYS,
        "engagement result required set drift",
    )
    _require(
        engagement_result["properties"]["schemaVersion"].get("const") == 1,
        "engagement result schemaVersion drift",
    )
    engagement_id = engagement_result["properties"]["engagementId"]
    _require(engagement_id.get("type") == "string", "engagementId must be string")
    _require(engagement_id.get("minLength") == 1, "engagementId minLength drift")
    _require(engagement_id.get("pattern") == SAFE_ARTIFACT_ID.pattern, "engagementId safe pattern drift")
    for name in ("adapterId", "scopeId", "searchRunId", "replay"):
        _non_blank_string(engagement_result["properties"][name], f"engagementResult.{name}")
    engagement_fingerprint = engagement_result["properties"]["manifestSha256"]
    _require(engagement_fingerprint.get("type") == "string", "engagement manifestSha256 must be string")
    _require(
        engagement_fingerprint.get("pattern") == "^[0-9a-f]{64}$",
        "engagement manifestSha256 pattern drift",
    )

    checks = engagement_result["properties"]["checks"]
    _require(checks.get("type") == "array", "engagementResult.checks must be array")
    _require(checks.get("minItems") == 1, "engagementResult.checks.minItems drift")
    check = checks["items"]
    _strict_object(check, "engagementResult.checks[]")
    _require(_keys(check, "engagementResult.checks[]") == CHECK_KEYS, "engagement check property set drift")
    expected_check_required = {"invariantId", "status", "exploredCandidates", "notes"}
    _require(
        _required(check, "engagementResult.checks[]") == expected_check_required,
        "engagement check required set drift",
    )
    _non_blank_string(check["properties"]["invariantId"], "engagementResult.checks[].invariantId")
    status = check["properties"]["status"]
    _require(status.get("type") == "string", "engagement status must be string")
    _require(set(status.get("enum", [])) == STATUSES, "engagement status enum drift")
    finding_id = check["properties"]["findingId"]
    _require(finding_id.get("type") == "string", "engagement findingId must be string")
    _require(finding_id.get("minLength") == 1, "engagement findingId minLength drift")
    _require(finding_id.get("pattern") == SAFE_ARTIFACT_ID.pattern, "engagement findingId safe pattern drift")
    _require(
        check["properties"]["exploredCandidates"] == {"type": "integer", "minimum": 0},
        "engagement exploredCandidates schema drift",
    )
    _non_blank_string(check["properties"]["notes"], "engagementResult.checks[].notes")
    engagement_path = check["properties"]["path"]
    _require(engagement_path.get("type") == "array", "engagement path must be array")
    _require(engagement_path.get("minItems") == 1, "engagement path minItems drift")
    _step_contract(engagement_path["items"], "engagementResult.checks[].path[]")
    all_of = check.get("allOf")
    _require(isinstance(all_of, list) and len(all_of) == 1, "engagement status conditional drift")

    _reachability_contract(reachability)
    _tsse_contract(tsse)
    _tsse_tool_capture_contract(tsse_tool_capture)
    _tsse_tool_profile_contract(tsse_tool_profile)
    _tsse_tool_result_contract(tsse_tool_result)
    _graph_layers_contract(graph_layers)
    _graph_layer_diff_contract(graph_layer_diff)
    _action_guard_contract(action_guard, action_guard_result)

    return {
        "ok": True,
        "manifestSchema": str(MANIFEST_SCHEMA.relative_to(ROOT)),
        "resultSchema": str(RESULT_SCHEMA.relative_to(ROOT)),
        "engagementResultSchema": str(ENGAGEMENT_RESULT_SCHEMA.relative_to(ROOT)),
        "reachabilitySchema": str(REACHABILITY_SCHEMA.relative_to(ROOT)),
        "tsseSchema": str(TSSE_SCHEMA.relative_to(ROOT)),
        "tsseToolCaptureSchema": str(TSSE_TOOL_CAPTURE_SCHEMA.relative_to(ROOT)),
        "tsseToolProfileSchema": str(TSSE_TOOL_PROFILE_SCHEMA.relative_to(ROOT)),
        "tsseToolResultSchema": str(TSSE_TOOL_RESULT_SCHEMA.relative_to(ROOT)),
        "graphLayersSchema": str(GRAPH_LAYERS_SCHEMA.relative_to(ROOT)),
        "graphLayerDiffSchema": str(GRAPH_LAYER_DIFF_SCHEMA.relative_to(ROOT)),
        "actionGuardSchema": str(ACTION_GUARD_SCHEMA.relative_to(ROOT)),
        "actionGuardResultSchema": str(ACTION_GUARD_RESULT_SCHEMA.relative_to(ROOT)),
        "severityValues": sorted(SEVERITIES),
        "engagementStatuses": sorted(STATUSES),
    }


def main() -> int:
    print(json.dumps(check_schema_contract(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
