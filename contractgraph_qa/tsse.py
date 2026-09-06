"""Deterministic Time-Space-State-Environment transition verification.

TSSE v0.1 validates an explicitly reviewed, finite execution trace.  It keeps
time, protocol topology, state, external environment, actor/authority, and
economic value separate so a locally plausible transition cannot silently
hide a cross-boundary effect.

The evaluator is intentionally evidence-oriented.  It does not discover
transitions, infer invariants, execute target code, or claim exhaustive
verification.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any


MODEL_SCHEMA = "cgqa/tsse-transition-model/v0.1"
RESULT_SCHEMA = "cgqa/tsse-transition-result/v0.1"

DIMENSIONS = (
    "time",
    "space",
    "state",
    "environment",
    "actor",
    "authority",
    "value",
)

INVARIANT_KINDS = {
    "safety",
    "liveness",
    "conservation",
    "authorization",
    "replay",
    "temporal",
    "spatial",
    "environmental",
    "causal",
}

_TOP_LEVEL_KEYS = {
    "schema",
    "modelId",
    "exactSubject",
    "evidence",
    "nodes",
    "transitions",
    "invariants",
    "forbiddenTransitions",
    "requirements",
    "scope",
}
_SUBJECT_KEYS = {"repository", "commit", "adapter"}
_EVIDENCE_KEYS = {"id", "subjectHash", "kind", "source", "digest"}
_NODE_KEYS = {
    "id",
    "subjectHash",
    "time",
    "space",
    "state",
    "environment",
    "actor",
    "authority",
    "value",
}
_TIME_KEYS = {"block", "timestamp", "epoch", "causalStep"}
_SPACE_KEYS = {"chainId", "contract", "callFrame", "storageDomain", "protocolLocation"}
_STATE_KEYS = {"phase", "stateHash", "values"}
_ENVIRONMENT_KEYS = {
    "oracleState",
    "tokenModel",
    "feeMode",
    "implementation",
    "externalStateHash",
}
_ACTOR_KEYS = {"identity", "role"}
_AUTHORITY_KEYS = {"epoch", "status"}
_VALUE_KEYS = {"unit", "locked", "moved"}
_TRANSITION_KEYS = {
    "id",
    "sequence",
    "predecessorId",
    "sourceId",
    "targetId",
    "cause",
    "action",
    "evidenceRefs",
    "crossedBoundaries",
}
_INVARIANT_KEYS = {"id", "kind", "description"}
_FORBIDDEN_KEYS = {"id", "fromPhase", "toPhase", "invariantId"}
_REQUIREMENT_KEYS = {
    "requireMonotonicTime",
    "requireCausalContinuity",
    "requireExactSubjectBinding",
    "requireEvidenceBindings",
}

# Public schema-contract sets.  The runtime continues to use the same objects,
# so CI can detect drift between Python validation and the checked-in schema.
MODEL_KEYS = _TOP_LEVEL_KEYS
EXACT_SUBJECT_KEYS = _SUBJECT_KEYS
EVIDENCE_KEYS = _EVIDENCE_KEYS
NODE_KEYS = _NODE_KEYS
TIME_KEYS = _TIME_KEYS
SPACE_KEYS = _SPACE_KEYS
STATE_KEYS = _STATE_KEYS
ENVIRONMENT_KEYS = _ENVIRONMENT_KEYS
ACTOR_KEYS = _ACTOR_KEYS
AUTHORITY_KEYS = _AUTHORITY_KEYS
VALUE_KEYS = _VALUE_KEYS
TRANSITION_KEYS = _TRANSITION_KEYS
INVARIANT_KEYS = _INVARIANT_KEYS
FORBIDDEN_TRANSITION_KEYS = _FORBIDDEN_KEYS
REQUIREMENT_KEYS = _REQUIREMENT_KEYS


class TSSEError(ValueError):
    """Raised when a TSSE model violates the strict structural contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TSSEError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TSSEError(f"{field} must be an object")
    return value


def _strict_object(
    value: object,
    field: str,
    *,
    keys: set[str],
    required: set[str] | None = None,
) -> dict[str, Any]:
    item = _object(value, field)
    unknown = sorted(set(item) - keys)
    if unknown:
        raise TSSEError(f"{field} contains unknown fields: {', '.join(unknown)}")
    required_keys = keys if required is None else required
    missing = sorted(required_keys - set(item))
    if missing:
        raise TSSEError(f"{field} missing required fields: {', '.join(missing)}")
    return item


def _array(value: object, field: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        raise TSSEError(f"{field} must be an array")
    if non_empty and not value:
        raise TSSEError(f"{field} must not be empty")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TSSEError(f"{field} must be a non-empty string")
    if value != value.strip():
        raise TSSEError(f"{field} must not contain leading or trailing whitespace")
    return value


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise TSSEError(f"{field} must be a boolean")
    return value


def _non_negative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TSSEError(f"{field} must be a non-negative integer")
    return value


def _digest(value: object, field: str) -> str:
    text = _text(value, field)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise TSSEError(f"{field} must be a 64-character lowercase SHA-256 digest")
    return text


def _text_array(
    value: object,
    field: str,
    *,
    allowed: set[str] | None = None,
) -> list[str]:
    raw = _array(value, field)
    result: list[str] = []
    for index, item in enumerate(raw):
        normalized = _text(item, f"{field}[{index}]")
        if allowed is not None and normalized not in allowed:
            raise TSSEError(f"{field}[{index}] has unsupported value {normalized!r}")
        result.append(normalized)
    if len(result) != len(set(result)):
        raise TSSEError(f"{field} must not contain duplicates")
    return result


def _json_value(value: object, field: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TSSEError(f"{field} must not contain NaN or infinity")
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, f"{field}[{index}]")
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TSSEError(f"{field} object keys must be strings")
            _json_value(item, f"{field}.{key}")
        return value
    raise TSSEError(f"{field} contains a non-JSON value")


def _unique_id(item_id: str, ids: set[str], field: str) -> None:
    if item_id in ids:
        raise TSSEError(f"duplicate {field} {item_id}")
    ids.add(item_id)


def validate_tsse_model(data: object) -> dict[str, Any]:
    """Validate and return a defensive copy of one strict TSSE v0.1 model."""

    model = copy.deepcopy(
        _strict_object(data, "model", keys=_TOP_LEVEL_KEYS)
    )
    if model["schema"] != MODEL_SCHEMA:
        raise TSSEError(f"model.schema must equal {MODEL_SCHEMA!r}")
    _text(model["modelId"], "model.modelId")
    _text(model["scope"], "model.scope")

    subject = _strict_object(
        model["exactSubject"], "model.exactSubject", keys=_SUBJECT_KEYS
    )
    for key in sorted(_SUBJECT_KEYS):
        _text(subject[key], f"model.exactSubject.{key}")

    evidence_ids: set[str] = set()
    evidence = _array(model["evidence"], "model.evidence")
    for index, raw in enumerate(evidence):
        field = f"model.evidence[{index}]"
        item = _strict_object(raw, field, keys=_EVIDENCE_KEYS)
        item_id = _text(item["id"], f"{field}.id")
        _unique_id(item_id, evidence_ids, "evidence id")
        _digest(item["subjectHash"], f"{field}.subjectHash")
        _text(item["kind"], f"{field}.kind")
        _text(item["source"], f"{field}.source")
        _digest(item["digest"], f"{field}.digest")

    node_ids: set[str] = set()
    nodes = _array(model["nodes"], "model.nodes", non_empty=True)
    for index, raw in enumerate(nodes):
        field = f"model.nodes[{index}]"
        node = _strict_object(raw, field, keys=_NODE_KEYS)
        node_id = _text(node["id"], f"{field}.id")
        _unique_id(node_id, node_ids, "node id")
        _digest(node["subjectHash"], f"{field}.subjectHash")

        time = _strict_object(node["time"], f"{field}.time", keys=_TIME_KEYS)
        for key in sorted(_TIME_KEYS):
            _non_negative_int(time[key], f"{field}.time.{key}")

        space = _strict_object(node["space"], f"{field}.space", keys=_SPACE_KEYS)
        for key in sorted(_SPACE_KEYS):
            _text(space[key], f"{field}.space.{key}")

        state = _strict_object(node["state"], f"{field}.state", keys=_STATE_KEYS)
        _text(state["phase"], f"{field}.state.phase")
        _digest(state["stateHash"], f"{field}.state.stateHash")
        _json_value(_object(state["values"], f"{field}.state.values"), f"{field}.state.values")

        environment = _strict_object(
            node["environment"], f"{field}.environment", keys=_ENVIRONMENT_KEYS
        )
        for key in sorted(_ENVIRONMENT_KEYS - {"externalStateHash"}):
            _text(environment[key], f"{field}.environment.{key}")
        _digest(environment["externalStateHash"], f"{field}.environment.externalStateHash")

        actor = _strict_object(node["actor"], f"{field}.actor", keys=_ACTOR_KEYS)
        for key in sorted(_ACTOR_KEYS):
            _text(actor[key], f"{field}.actor.{key}")

        authority = _strict_object(
            node["authority"], f"{field}.authority", keys=_AUTHORITY_KEYS
        )
        _non_negative_int(authority["epoch"], f"{field}.authority.epoch")
        _text(authority["status"], f"{field}.authority.status")

        value = _strict_object(node["value"], f"{field}.value", keys=_VALUE_KEYS)
        _text(value["unit"], f"{field}.value.unit")
        _non_negative_int(value["locked"], f"{field}.value.locked")
        _non_negative_int(value["moved"], f"{field}.value.moved")

    invariant_ids: set[str] = set()
    invariants = _array(model["invariants"], "model.invariants", non_empty=True)
    for index, raw in enumerate(invariants):
        field = f"model.invariants[{index}]"
        invariant = _strict_object(raw, field, keys=_INVARIANT_KEYS)
        invariant_id = _text(invariant["id"], f"{field}.id")
        _unique_id(invariant_id, invariant_ids, "invariant id")
        kind = _text(invariant["kind"], f"{field}.kind")
        if kind not in INVARIANT_KINDS:
            raise TSSEError(f"{field}.kind has unsupported value {kind!r}")
        _text(invariant["description"], f"{field}.description")

    forbidden_ids: set[str] = set()
    forbidden = _array(model["forbiddenTransitions"], "model.forbiddenTransitions")
    for index, raw in enumerate(forbidden):
        field = f"model.forbiddenTransitions[{index}]"
        item = _strict_object(raw, field, keys=_FORBIDDEN_KEYS)
        forbidden_id = _text(item["id"], f"{field}.id")
        _unique_id(forbidden_id, forbidden_ids, "forbidden transition id")
        _text(item["fromPhase"], f"{field}.fromPhase")
        _text(item["toPhase"], f"{field}.toPhase")
        invariant_id = _text(item["invariantId"], f"{field}.invariantId")
        if invariant_id not in invariant_ids:
            raise TSSEError(f"{field}.invariantId references unknown invariant {invariant_id}")

    transition_ids: set[str] = set()
    transitions = _array(model["transitions"], "model.transitions", non_empty=True)
    transition_predecessors: list[tuple[str, str | None]] = []
    for index, raw in enumerate(transitions):
        field = f"model.transitions[{index}]"
        transition = _strict_object(raw, field, keys=_TRANSITION_KEYS)
        transition_id = _text(transition["id"], f"{field}.id")
        _unique_id(transition_id, transition_ids, "transition id")
        _non_negative_int(transition["sequence"], f"{field}.sequence")
        predecessor = transition["predecessorId"]
        if predecessor is not None:
            predecessor = _text(predecessor, f"{field}.predecessorId")
        transition_predecessors.append((transition_id, predecessor))
        for key in ("sourceId", "targetId"):
            node_id = _text(transition[key], f"{field}.{key}")
            if node_id not in node_ids:
                raise TSSEError(f"{field}.{key} references unknown node {node_id}")
        _text(transition["cause"], f"{field}.cause")
        _text(transition["action"], f"{field}.action")
        refs = _text_array(transition["evidenceRefs"], f"{field}.evidenceRefs")
        unknown_evidence = sorted(set(refs) - evidence_ids)
        if unknown_evidence:
            raise TSSEError(
                f"{field}.evidenceRefs references unknown evidence: {', '.join(unknown_evidence)}"
            )
        declared_boundaries = _text_array(
            transition["crossedBoundaries"],
            f"{field}.crossedBoundaries",
            allowed=set(DIMENSIONS),
        )
        canonical_boundaries = [
            dimension for dimension in DIMENSIONS if dimension in declared_boundaries
        ]
        transition["crossedBoundaries"] = canonical_boundaries

    for transition_id, predecessor in transition_predecessors:
        if predecessor is not None and predecessor not in transition_ids:
            raise TSSEError(
                f"transition {transition_id} predecessorId references unknown transition {predecessor}"
            )

    requirements = _strict_object(
        model["requirements"], "model.requirements", keys=_REQUIREMENT_KEYS
    )
    for key in sorted(_REQUIREMENT_KEYS):
        _boolean(requirements[key], f"model.requirements.{key}")

    return model


def load_tsse_model(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON model and enforce the TSSE structural contract."""

    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise TSSEError(f"failed to load TSSE model {path}: {exc}") from exc
    return validate_tsse_model(data)


def _violation(code: str, message: str, **context: object) -> dict[str, object]:
    return {"code": code, "message": message, **context}


def _changed_dimensions(source: dict[str, Any], target: dict[str, Any]) -> list[str]:
    return [
        dimension
        for dimension in DIMENSIONS
        if _canonical_bytes(source[dimension]) != _canonical_bytes(target[dimension])
    ]


def run_tsse_model(model: dict[str, Any]) -> dict[str, object]:
    """Evaluate one reviewed finite trace and return deterministic bounded evidence."""

    validated = validate_tsse_model(model)
    subject_hash = _sha256(validated["exactSubject"])
    requirements = validated["requirements"]
    nodes = {node["id"]: node for node in validated["nodes"]}
    evidence = {item["id"]: item for item in validated["evidence"]}
    forbidden = list(validated["forbiddenTransitions"])

    violations: list[dict[str, object]] = []

    if requirements["requireExactSubjectBinding"]:
        for node in validated["nodes"]:
            if node["subjectHash"] != subject_hash:
                violations.append(
                    _violation(
                        "EXACT_SUBJECT_MISMATCH",
                        "node subjectHash does not match exactSubject",
                        nodeId=node["id"],
                        expectedSubjectHash=subject_hash,
                        observedSubjectHash=node["subjectHash"],
                    )
                )
        for item in validated["evidence"]:
            if item["subjectHash"] != subject_hash:
                violations.append(
                    _violation(
                        "EXACT_SUBJECT_MISMATCH",
                        "evidence subjectHash does not match exactSubject",
                        evidenceId=item["id"],
                        expectedSubjectHash=subject_hash,
                        observedSubjectHash=item["subjectHash"],
                    )
                )

    boundary_counts = {dimension: 0 for dimension in DIMENSIONS}
    phase_transitions: list[dict[str, object]] = []
    previous_transition: dict[str, Any] | None = None

    for index, transition in enumerate(validated["transitions"]):
        source = nodes[transition["sourceId"]]
        target = nodes[transition["targetId"]]

        if requirements["requireCausalContinuity"]:
            if transition["sequence"] != index:
                violations.append(
                    _violation(
                        "CAUSAL_STEP_DISCONTINUITY",
                        "transition sequence is not contiguous from zero",
                        transitionId=transition["id"],
                        expectedSequence=index,
                        observedSequence=transition["sequence"],
                    )
                )
            expected_predecessor = None if previous_transition is None else previous_transition["id"]
            if transition["predecessorId"] != expected_predecessor:
                violations.append(
                    _violation(
                        "PREDECESSOR_DISCONTINUITY",
                        "predecessorId does not identify the previous transition",
                        transitionId=transition["id"],
                        expectedPredecessorId=expected_predecessor,
                        observedPredecessorId=transition["predecessorId"],
                    )
                )
            if previous_transition is not None and previous_transition["targetId"] != transition["sourceId"]:
                violations.append(
                    _violation(
                        "PATH_CONTINUITY_BROKEN",
                        "transition source does not continue from the previous target",
                        transitionId=transition["id"],
                        expectedSourceId=previous_transition["targetId"],
                        observedSourceId=transition["sourceId"],
                    )
                )
            expected_causal_step = source["time"]["causalStep"] + 1
            if target["time"]["causalStep"] != expected_causal_step:
                violations.append(
                    _violation(
                        "CAUSAL_STEP_DISCONTINUITY",
                        "target causalStep must advance exactly once from the source",
                        transitionId=transition["id"],
                        expectedCausalStep=expected_causal_step,
                        observedCausalStep=target["time"]["causalStep"],
                    )
                )

        if requirements["requireMonotonicTime"]:
            regressions = [
                key
                for key in ("block", "timestamp", "epoch")
                if target["time"][key] < source["time"][key]
            ]
            if regressions:
                violations.append(
                    _violation(
                        "NON_MONOTONIC_TIME",
                        "target time regresses relative to the source",
                        transitionId=transition["id"],
                        regressedFields=regressions,
                    )
                )

        if requirements["requireEvidenceBindings"] and not transition["evidenceRefs"]:
            violations.append(
                _violation(
                    "EVIDENCE_BINDING_MISSING",
                    "transition has no evidenceRefs under a required evidence-binding policy",
                    transitionId=transition["id"],
                )
            )

        if requirements["requireExactSubjectBinding"]:
            for evidence_id in transition["evidenceRefs"]:
                if evidence[evidence_id]["subjectHash"] != subject_hash:
                    violations.append(
                        _violation(
                            "EXACT_SUBJECT_MISMATCH",
                            "transition references evidence bound to another subject",
                            transitionId=transition["id"],
                            evidenceId=evidence_id,
                            expectedSubjectHash=subject_hash,
                            observedSubjectHash=evidence[evidence_id]["subjectHash"],
                        )
                    )

        changed_dimensions = _changed_dimensions(source, target)
        for dimension in changed_dimensions:
            boundary_counts[dimension] += 1
        declared = list(transition["crossedBoundaries"])
        if set(declared) != set(changed_dimensions):
            violations.append(
                _violation(
                    "BOUNDARY_DECLARATION_MISMATCH",
                    "declared crossedBoundaries do not match the observed node delta",
                    transitionId=transition["id"],
                    expectedBoundaries=changed_dimensions,
                    declaredBoundaries=declared,
                )
            )

        from_phase = source["state"]["phase"]
        to_phase = target["state"]["phase"]
        matched_forbidden = [
            item
            for item in forbidden
            if item["fromPhase"] == from_phase and item["toPhase"] == to_phase
        ]
        for item in matched_forbidden:
            violations.append(
                _violation(
                    "FORBIDDEN_PHASE_TRANSITION",
                    "trace reaches a declared forbidden phase transition",
                    transitionId=transition["id"],
                    forbiddenTransitionId=item["id"],
                    invariantId=item["invariantId"],
                    fromPhase=from_phase,
                    toPhase=to_phase,
                )
            )

        phase_transitions.append(
            {
                "transitionId": transition["id"],
                "fromPhase": from_phase,
                "toPhase": to_phase,
                "phaseChanged": from_phase != to_phase,
                "changedDimensions": changed_dimensions,
                "classification": "+".join(changed_dimensions) if changed_dimensions else "no_change",
                "declaredBoundaries": declared,
                "forbiddenTransitionIds": [item["id"] for item in matched_forbidden],
            }
        )
        previous_transition = transition

    return {
        "schema": RESULT_SCHEMA,
        "modelId": validated["modelId"],
        "status": "hold" if violations else "pass",
        "modelHash": _sha256(validated),
        "subjectHash": subject_hash,
        "requirements": dict(requirements),
        "disabledRequirements": sorted(
            key for key, enabled in requirements.items() if not enabled
        ),
        "counts": {
            "nodes": len(validated["nodes"]),
            "transitions": len(validated["transitions"]),
            "evidence": len(validated["evidence"]),
            "violations": len(violations),
        },
        "phaseTransitions": phase_transitions,
        "crossedBoundaryCounts": boundary_counts,
        "violations": violations,
        "claimBoundary": (
            "TSSE validates one explicit finite trace against declared subject, continuity, boundary, "
            "evidence, and forbidden-phase requirements. PASS is bounded by the reviewed nodes, "
            "transitions, environment representation, invariants, and supplied evidence. Only the "
            "exact-subject hash is recomputed; referenced evidence/state artifacts are not reopened. "
            "PASS is not proof of system security or exhaustive reachability."
        ),
    }


__all__ = [
    "ACTOR_KEYS",
    "AUTHORITY_KEYS",
    "DIMENSIONS",
    "ENVIRONMENT_KEYS",
    "EVIDENCE_KEYS",
    "EXACT_SUBJECT_KEYS",
    "FORBIDDEN_TRANSITION_KEYS",
    "INVARIANT_KINDS",
    "INVARIANT_KEYS",
    "MODEL_SCHEMA",
    "MODEL_KEYS",
    "NODE_KEYS",
    "REQUIREMENT_KEYS",
    "RESULT_SCHEMA",
    "SPACE_KEYS",
    "STATE_KEYS",
    "TIME_KEYS",
    "TRANSITION_KEYS",
    "TSSEError",
    "VALUE_KEYS",
    "load_tsse_model",
    "run_tsse_model",
    "validate_tsse_model",
]
