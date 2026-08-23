"""Deterministic verification for protective-action ordering races.

CGQ-RACE-001 checks a narrow business-semantic property that successor consistency
cannot express: two actions may both be legal from one parent state/version and EVM
serialization may allow only one to commit, while the *economic right* protected by
one action is still defeatable solely by transaction ordering.

The verifier is exact over a reviewed two-order counterfactual model. It does not
infer that both actions are actually enabled in external Solidity, nor that the
business guarantee is the intended product policy; those remain evidence claims.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "protective-ordering-v0.1"
RESULT_SCHEMA_VERSION = "protective-ordering-result-v0.1"
INVARIANT_ID = "CGQ-RACE-001"

_MODEL_KEYS = {
    "schemaVersion",
    "modelId",
    "invariantId",
    "parentState",
    "parentVersion",
    "protectiveAction",
    "competingAction",
    "bothEnabledAtParent",
    "protectiveActionMustRemainEffectiveAcrossOrdering",
    "orderings",
    "scope",
}
_ORDERING_KEYS = {
    "sequence",
    "finalState",
    "protectiveActionResult",
    "competingActionResult",
    "economicOutcome",
    "protectiveRightPreserved",
}
_ACTION_RESULTS = {"committed", "reverted", "not_executed"}


@dataclass(frozen=True, slots=True)
class OrderingOutcome:
    sequence: tuple[str, str]
    final_state: str
    protective_action_result: str
    competing_action_result: str
    economic_outcome: str
    protective_right_preserved: bool


@dataclass(frozen=True, slots=True)
class ProtectiveOrderingModel:
    model_id: str
    invariant_id: str
    parent_state: str
    parent_version: int
    protective_action: str
    competing_action: str
    both_enabled_at_parent: bool
    protective_action_must_remain_effective: bool
    orderings: tuple[OrderingOutcome, OrderingOutcome]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _version(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def protective_ordering_model_from_dict(data: dict[str, Any]) -> ProtectiveOrderingModel:
    _require(isinstance(data, dict), "protective ordering model must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "protective ordering model")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "protective ordering model missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")

    invariant_id = _text(data["invariantId"], "invariantId")
    _require(invariant_id == INVARIANT_ID, f"invariantId must be {INVARIANT_ID}")
    protective_action = _text(data["protectiveAction"], "protectiveAction")
    competing_action = _text(data["competingAction"], "competingAction")
    _require(protective_action != competing_action, "protectiveAction and competingAction must differ")

    enabled = data["bothEnabledAtParent"]
    guarantee = data["protectiveActionMustRemainEffectiveAcrossOrdering"]
    _require(isinstance(enabled, bool), "bothEnabledAtParent must be a boolean")
    _require(isinstance(guarantee, bool), "protectiveActionMustRemainEffectiveAcrossOrdering must be a boolean")

    raw_orderings = data["orderings"]
    _require(isinstance(raw_orderings, list) and len(raw_orderings) == 2, "orderings must contain exactly two permutations")
    orderings: list[OrderingOutcome] = []
    seen_sequences: set[tuple[str, str]] = set()
    expected_sequences = {
        (protective_action, competing_action),
        (competing_action, protective_action),
    }
    for index, raw in enumerate(raw_orderings):
        field = f"orderings[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _ORDERING_KEYS, field)
        missing_ordering = sorted(_ORDERING_KEYS - set(raw))
        _require(not missing_ordering, f"{field} missing required fields: {', '.join(missing_ordering)}")
        sequence_raw = raw["sequence"]
        _require(isinstance(sequence_raw, list) and len(sequence_raw) == 2, f"{field}.sequence must contain two actions")
        sequence = tuple(_text(item, f"{field}.sequence") for item in sequence_raw)
        _require(sequence in expected_sequences, f"{field}.sequence must be one permutation of the declared actions")
        _require(sequence not in seen_sequences, f"duplicate ordering sequence: {sequence}")
        seen_sequences.add(sequence)
        protective_result = _text(raw["protectiveActionResult"], f"{field}.protectiveActionResult")
        competing_result = _text(raw["competingActionResult"], f"{field}.competingActionResult")
        _require(protective_result in _ACTION_RESULTS, f"{field}.protectiveActionResult is unsupported")
        _require(competing_result in _ACTION_RESULTS, f"{field}.competingActionResult is unsupported")
        preserved = raw["protectiveRightPreserved"]
        _require(isinstance(preserved, bool), f"{field}.protectiveRightPreserved must be a boolean")
        orderings.append(
            OrderingOutcome(
                sequence=sequence,
                final_state=_text(raw["finalState"], f"{field}.finalState"),
                protective_action_result=protective_result,
                competing_action_result=competing_result,
                economic_outcome=_text(raw["economicOutcome"], f"{field}.economicOutcome"),
                protective_right_preserved=preserved,
            )
        )

    _require(seen_sequences == expected_sequences, "orderings must cover both action permutations")
    scope_raw = data.get("scope")
    return ProtectiveOrderingModel(
        model_id=_text(data["modelId"], "modelId"),
        invariant_id=invariant_id,
        parent_state=_text(data["parentState"], "parentState"),
        parent_version=_version(data["parentVersion"], "parentVersion"),
        protective_action=protective_action,
        competing_action=competing_action,
        both_enabled_at_parent=enabled,
        protective_action_must_remain_effective=guarantee,
        orderings=tuple(orderings),  # type: ignore[arg-type]
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_protective_ordering_model(path: Path) -> ProtectiveOrderingModel:
    with path.open("r", encoding="utf-8") as handle:
        return protective_ordering_model_from_dict(json.load(handle))


def protective_ordering_model_to_dict(model: ProtectiveOrderingModel) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "modelId": model.model_id,
        "invariantId": model.invariant_id,
        "parentState": model.parent_state,
        "parentVersion": model.parent_version,
        "protectiveAction": model.protective_action,
        "competingAction": model.competing_action,
        "bothEnabledAtParent": model.both_enabled_at_parent,
        "protectiveActionMustRemainEffectiveAcrossOrdering": model.protective_action_must_remain_effective,
        "orderings": [
            {
                "sequence": list(item.sequence),
                "finalState": item.final_state,
                "protectiveActionResult": item.protective_action_result,
                "competingActionResult": item.competing_action_result,
                "economicOutcome": item.economic_outcome,
                "protectiveRightPreserved": item.protective_right_preserved,
            }
            for item in model.orderings
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def protective_ordering_model_sha256(model: ProtectiveOrderingModel) -> str:
    canonical = json.dumps(
        protective_ordering_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_protective_ordering_model(model: ProtectiveOrderingModel) -> dict[str, object]:
    """Evaluate whether a declared protective right is defeatable by ordering alone."""

    ordered = sorted(model.orderings, key=lambda item: item.sequence)
    violations: list[dict[str, object]] = []

    if model.both_enabled_at_parent and model.protective_action_must_remain_effective:
        for item in ordered:
            if not item.protective_right_preserved:
                violations.append(
                    {
                        "kind": "protective_right_defeated_by_ordering",
                        "sequence": list(item.sequence),
                        "finalState": item.final_state,
                        "economicOutcome": item.economic_outcome,
                        "protectiveActionResult": item.protective_action_result,
                        "protectiveRightPreserved": item.protective_right_preserved,
                    }
                )

    economic_outcomes = sorted({item.economic_outcome for item in ordered})
    final_states = sorted({item.final_state for item in ordered})
    ordering_sensitive = len(economic_outcomes) > 1 or len(final_states) > 1

    if not model.both_enabled_at_parent or not model.protective_action_must_remain_effective:
        status = "inconclusive"
    else:
        status = "fail" if violations else "pass"

    counterexample = violations[0] if violations else None
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": status,
        "invariantId": model.invariant_id,
        "modelId": model.model_id,
        "modelSha256": protective_ordering_model_sha256(model),
        "parent": {"state": model.parent_state, "version": model.parent_version},
        "protectiveAction": model.protective_action,
        "competingAction": model.competing_action,
        "bothEnabledAtParent": model.both_enabled_at_parent,
        "orderingSensitiveOutcome": ordering_sensitive,
        "economicOutcomes": economic_outcomes,
        "finalStates": final_states,
        "violations": violations,
        "counterexample": counterexample,
        "claimBoundary": (
            "Exact over the reviewed two-order counterfactual model. Joint enablement of the actions, "
            "the modeled transaction outcomes, and the business requirement that the protective right "
            "remain effective are independent source/specification evidence claims."
        ),
    }
