"""ASTRA transition intelligence for bounded causal QA.

This module does not replace ContractGraph-QA's deterministic explorers. It ranks
already-modelled transitions, records acceleration toward risky states, and
fails closed when the verifier itself has unresolved causal assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


class AstraTransitionError(ValueError):
    """Raised when ASTRA transition input is malformed."""


_COMPONENTS = (
    "stimulus",
    "state_complexity",
    "future_pressure",
    "witness_gap",
    "divergence",
)


@dataclass(frozen=True)
class TransitionScore:
    transition_id: str
    tps: float
    delta_tps: float | None
    phase: str
    components: dict[str, float]


def _unit_interval(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AstraTransitionError(f"{name} must be a number in [0, 1]")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise AstraTransitionError(f"{name} must be in [0, 1]")
    return number


def _phase(tps: float, delta_tps: float | None) -> str:
    if tps >= 85.0:
        return "C"
    if tps >= 60.0 and delta_tps is not None and delta_tps > 5.0:
        return "M_UP"
    if tps >= 25.0:
        return "M"
    return "A"


def transition_pressure(components: dict[str, Any]) -> float:
    """Return multiplicative Transition Pressure Score in the range [0, 100]."""
    values = [_unit_interval(name, components.get(name)) for name in _COMPONENTS]
    product = 1.0
    for value in values:
        product *= value
    return round(product * 100.0, 6)


def _verifier_reflection(raw: dict[str, Any]) -> dict[str, Any]:
    reflection = raw.get("verifier_reflection", {})
    if reflection is None:
        reflection = {}
    if not isinstance(reflection, dict):
        raise AstraTransitionError("verifier_reflection must be an object")

    supported = (
        "wrong_clock_model",
        "missing_witness",
        "stale_execution_artifact",
        "state_plane_ambiguity",
        "model_precondition_unproven",
    )
    flags: dict[str, bool] = {}
    for name in supported:
        value = reflection.get(name, False)
        if not isinstance(value, bool):
            raise AstraTransitionError(f"verifier_reflection.{name} must be boolean")
        flags[name] = value

    unresolved = [name for name, value in flags.items() if value]
    return {
        "status": "VERIFIER_FAIL" if unresolved else "TARGET_CANDIDATE",
        "unresolved": unresolved,
        "flags": flags,
    }


def analyze_transition_path(payload: dict[str, Any]) -> dict[str, Any]:
    """Score a bounded ordered path and derive its failure gradient.

    Expected input::

        {
          "transitions": [
            {
              "id": "retry-1",
              "stimulus": 0.8,
              "state_complexity": 0.9,
              "future_pressure": 0.7,
              "witness_gap": 0.8,
              "divergence": 0.6
            }
          ],
          "material_acceleration": 5.0,
          "verifier_reflection": {...}
        }
    """
    if not isinstance(payload, dict):
        raise AstraTransitionError("input must be an object")
    raw_transitions = payload.get("transitions")
    if not isinstance(raw_transitions, list) or not raw_transitions:
        raise AstraTransitionError("transitions must be a non-empty array")

    threshold_raw = payload.get("material_acceleration", 5.0)
    if isinstance(threshold_raw, bool) or not isinstance(threshold_raw, (int, float)):
        raise AstraTransitionError("material_acceleration must be a non-negative number")
    threshold = float(threshold_raw)
    if threshold < 0:
        raise AstraTransitionError("material_acceleration must be a non-negative number")

    scores: list[TransitionScore] = []
    previous: float | None = None
    seen: set[str] = set()

    for index, raw in enumerate(raw_transitions):
        if not isinstance(raw, dict):
            raise AstraTransitionError(f"transitions[{index}] must be an object")
        transition_id = raw.get("id")
        if not isinstance(transition_id, str) or not transition_id.strip():
            raise AstraTransitionError(f"transitions[{index}].id must be a non-empty string")
        if transition_id in seen:
            raise AstraTransitionError(f"duplicate transition id: {transition_id}")
        seen.add(transition_id)

        components = {name: _unit_interval(name, raw.get(name)) for name in _COMPONENTS}
        tps = transition_pressure(components)
        delta = None if previous is None else round(tps - previous, 6)
        scores.append(
            TransitionScore(
                transition_id=transition_id,
                tps=tps,
                delta_tps=delta,
                phase=_phase(tps, delta),
                components=components,
            )
        )
        previous = tps

    first_acceleration = next(
        (
            item.transition_id
            for item in scores
            if item.delta_tps is not None and item.delta_tps >= threshold
        ),
        None,
    )
    crystallization = next((item.transition_id for item in scores if item.phase == "C"), None)
    peak = max(scores, key=lambda item: item.tps)
    reflection = _verifier_reflection(payload)

    verdict = reflection["status"]
    if verdict == "TARGET_CANDIDATE" and crystallization is None:
        verdict = "NO_CRYSTALLIZED_FAILURE"

    return {
        "schema_version": "astra-transition-v0.1",
        "strategy": "bounded_pressure_overlay",
        "baseline_preserved": True,
        "scores": [
            {
                "transition_id": item.transition_id,
                "tps": item.tps,
                "delta_tps": item.delta_tps,
                "phase": item.phase,
                "components": item.components,
            }
            for item in scores
        ],
        "failure_gradient": {
            "material_acceleration_threshold": threshold,
            "first_material_acceleration": first_acceleration,
            "crystallization_transition": crystallization,
            "peak_transition": peak.transition_id,
            "peak_tps": peak.tps,
        },
        "verifier_reflection": reflection,
        "verdict": verdict,
    }
