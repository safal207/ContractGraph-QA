"""Deterministic transition-order and closed-loop geometry checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "cgqa/transition-geometry/v0.1"
PAIR_CLOSED = "CLOSED"
PAIR_HISTORY_DIVERGENT = "HISTORY_DIVERGENT"
PAIR_TORSION = "TORSION_DETECTED"
LOOP_FLAT = "FLAT_LOOP"
LOOP_HOLONOMY = "HOLONOMY"
LOOP_CURVATURE = "CURVATURE_DETECTED"


class TransitionGeometryError(ValueError):
    """Raised when a transition-geometry model is malformed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransitionGeometryError(f"{name} must be an object")
    return value


def _require_non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TransitionGeometryError(f"{name} must be a non-empty string")
    return value


def _validate_endpoint(value: object, name: str) -> dict[str, Any]:
    endpoint = _require_object(value, name)
    for key in ("state", "effects", "history"):
        _require_object(endpoint.get(key), f"{name}.{key}")
    return endpoint


def _diff(left: object, right: object, prefix: str = "") -> list[dict[str, object]]:
    if isinstance(left, dict) and isinstance(right, dict):
        rows: list[dict[str, object]] = []
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left:
                rows.append({"path": path, "left": None, "right": right[key]})
            elif key not in right:
                rows.append({"path": path, "left": left[key], "right": None})
            else:
                rows.extend(_diff(left[key], right[key], path))
        return rows
    if isinstance(left, list) and isinstance(right, list):
        rows = []
        max_len = max(len(left), len(right))
        for index in range(max_len):
            path = f"{prefix}[{index}]"
            if index >= len(left):
                rows.append({"path": path, "left": None, "right": right[index]})
            elif index >= len(right):
                rows.append({"path": path, "left": left[index], "right": None})
            else:
                rows.extend(_diff(left[index], right[index], path))
        return rows
    if left != right:
        return [{"path": prefix or "$", "left": left, "right": right}]
    return []


def _compare_endpoints(left: dict[str, Any], right: dict[str, Any]) -> dict[str, object]:
    state_delta = _diff(left["state"], right["state"], "state")
    effect_delta = _diff(left["effects"], right["effects"], "effects")
    history_delta = _diff(left["history"], right["history"], "history")
    semantic_changed = bool(state_delta or effect_delta)
    if semantic_changed:
        classification = PAIR_TORSION
    elif history_delta:
        classification = PAIR_HISTORY_DIVERGENT
    else:
        classification = PAIR_CLOSED
    return {
        "classification": classification,
        "stateDelta": state_delta,
        "effectDelta": effect_delta,
        "historyDelta": history_delta,
    }


def _compare_loop(origin: dict[str, Any], returned: dict[str, Any]) -> dict[str, object]:
    comparison = _compare_endpoints(origin, returned)
    pair_classification = comparison.pop("classification")
    if pair_classification == PAIR_TORSION:
        classification = LOOP_CURVATURE
    elif pair_classification == PAIR_HISTORY_DIVERGENT:
        classification = LOOP_HOLONOMY
    else:
        classification = LOOP_FLAT
    return {"classification": classification, **comparison}


def load_transition_geometry_model(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_transition_geometry_model(data)


def validate_transition_geometry_model(data: object) -> dict[str, Any]:
    model = _require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise TransitionGeometryError(f"schema must equal {SCHEMA!r}")
    subject = _require_object(model.get("subject"), "subject")
    if not subject:
        raise TransitionGeometryError("subject must not be empty")
    operators = _require_object(model.get("operators"), "operators")
    _require_non_empty_string(operators.get("a"), "operators.a")
    _require_non_empty_string(operators.get("b"), "operators.b")
    _validate_endpoint(model.get("origin"), "origin")
    _validate_endpoint(model.get("aThenB"), "aThenB")
    _validate_endpoint(model.get("bThenA"), "bThenA")
    if "loop" in model:
        loop = _require_object(model["loop"], "loop")
        sequence = loop.get("operators")
        if not isinstance(sequence, list) or not sequence:
            raise TransitionGeometryError("loop.operators must be a non-empty list")
        for index, value in enumerate(sequence):
            _require_non_empty_string(value, f"loop.operators[{index}]")
        _validate_endpoint(loop.get("returned"), "loop.returned")
    return model


def run_transition_geometry_model(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_transition_geometry_model(model)
    pair = _compare_endpoints(validated["aThenB"], validated["bThenA"])
    loop_result: dict[str, object] | None = None
    if "loop" in validated:
        loop_result = _compare_loop(validated["origin"], validated["loop"]["returned"])
        loop_result["operators"] = list(validated["loop"]["operators"])

    hold = pair["classification"] == PAIR_TORSION or (
        loop_result is not None and loop_result["classification"] == LOOP_CURVATURE
    )
    return {
        "schema": "cgqa/transition-geometry-result/v0.1",
        "status": "hold" if hold else "pass",
        "modelHash": _sha256(validated),
        "subjectHash": _sha256(validated["subject"]),
        "operators": dict(validated["operators"]),
        "pair": pair,
        "loop": loop_result,
        "claimBoundary": (
            "Transition geometry classifies observed endpoint/path dependence. "
            "TORSION_DETECTED or CURVATURE_DETECTED is a HOLD signal, not automatic invalidity."
        ),
    }
