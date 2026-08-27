from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

MODEL_KEYS = {"schemaVersion", "modelId", "invariantId", "events", "scope"}
MODEL_REQUIRED_KEYS = {"schemaVersion", "modelId", "invariantId", "events"}
EVENT_KEYS = {
    "eventId",
    "actionId",
    "effectKey",
    "occurrenceId",
    "applied",
}
EVENT_REQUIRED_KEYS = EVENT_KEYS


@dataclass(frozen=True, slots=True)
class EconomicEffectEvent:
    event_id: str
    action_id: str
    effect_key: str
    occurrence_id: str
    applied: bool


@dataclass(frozen=True, slots=True)
class EconomicCardinalityModel:
    schema_version: str
    model_id: str
    invariant_id: str
    events: tuple[EconomicEffectEvent, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _require_keys(data: dict[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    _require(not missing, f"{field} missing required fields: {', '.join(missing)}")


def economic_cardinality_model_from_dict(data: dict[str, Any]) -> EconomicCardinalityModel:
    _require(isinstance(data, dict), "economic cardinality model must be a JSON object")
    _reject_extra_keys(data, MODEL_KEYS, "economic cardinality model")
    _require_keys(data, MODEL_REQUIRED_KEYS, "economic cardinality model")

    events_raw = data["events"]
    _require(isinstance(events_raw, list), "economic cardinality model.events must be an array")

    events: list[EconomicEffectEvent] = []
    event_ids: set[str] = set()
    for index, item in enumerate(events_raw):
        field = f"economic cardinality model.events[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        _reject_extra_keys(item, EVENT_KEYS, field)
        _require_keys(item, EVENT_REQUIRED_KEYS, field)

        event_id = _text(item["eventId"], f"{field}.eventId")
        if event_id in event_ids:
            raise ValueError(f"duplicate eventId: {event_id}")
        event_ids.add(event_id)

        applied = item["applied"]
        _require(isinstance(applied, bool), f"{field}.applied must be a boolean")
        events.append(
            EconomicEffectEvent(
                event_id=event_id,
                action_id=_text(item["actionId"], f"{field}.actionId"),
                effect_key=_text(item["effectKey"], f"{field}.effectKey"),
                occurrence_id=_text(item["occurrenceId"], f"{field}.occurrenceId"),
                applied=applied,
            )
        )

    scope_raw = data.get("scope")
    scope = None if scope_raw is None else _text(scope_raw, "economic cardinality model.scope")

    return EconomicCardinalityModel(
        schema_version=_text(data["schemaVersion"], "economic cardinality model.schemaVersion"),
        model_id=_text(data["modelId"], "economic cardinality model.modelId"),
        invariant_id=_text(data["invariantId"], "economic cardinality model.invariantId"),
        events=tuple(events),
        scope=scope,
    )


def load_economic_cardinality_model(path: Path) -> EconomicCardinalityModel:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return economic_cardinality_model_from_dict(data)


def economic_cardinality_model_to_dict(model: EconomicCardinalityModel) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": model.schema_version,
        "modelId": model.model_id,
        "invariantId": model.invariant_id,
        "events": [
            {
                "eventId": event.event_id,
                "actionId": event.action_id,
                "effectKey": event.effect_key,
                "occurrenceId": event.occurrence_id,
                "applied": event.applied,
            }
            for event in model.events
        ],
    }
    if model.scope is not None:
        document["scope"] = model.scope
    return document


def economic_cardinality_model_sha256(model: EconomicCardinalityModel) -> str:
    canonical = json.dumps(
        economic_cardinality_model_to_dict(model),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_economic_cardinality_model(model: EconomicCardinalityModel) -> dict[str, object]:
    """Check at-most-once economic effects per logical action/effect slot.

    Multiple observations of the same occurrenceId are deduplicated deliberately.
    A violation requires at least two distinct applied occurrence IDs for the same
    (actionId, effectKey) pair.
    """

    groups: dict[tuple[str, str], dict[str, list[str]]] = {}
    for event in model.events:
        if not event.applied:
            continue
        key = (event.action_id, event.effect_key)
        occurrences = groups.setdefault(key, {})
        occurrences.setdefault(event.occurrence_id, []).append(event.event_id)

    violations: list[dict[str, object]] = []
    for (action_id, effect_key), occurrences in sorted(groups.items()):
        occurrence_ids = sorted(occurrences)
        if len(occurrence_ids) <= 1:
            continue

        first_two = occurrence_ids[:2]
        minimal_event_ids = [sorted(occurrences[item])[0] for item in first_two]
        violations.append(
            {
                "actionId": action_id,
                "effectKey": effect_key,
                "distinctAppliedOccurrenceCount": len(occurrence_ids),
                "occurrenceIds": occurrence_ids,
                "minimalCounterexampleEventIds": minimal_event_ids,
            }
        )

    return {
        "schemaVersion": model.schema_version,
        "modelId": model.model_id,
        "invariantId": model.invariant_id,
        "status": "fail" if violations else "pass",
        "modelSha256": economic_cardinality_model_sha256(model),
        "checkedAppliedEventCount": sum(1 for event in model.events if event.applied),
        "checkedActionEffectPairs": len(groups),
        "violations": violations,
        "semantics": {
            "countingUnit": "distinct confirmed occurrenceId per (actionId, effectKey)",
            "duplicateObservationPolicy": "same occurrenceId is deduplicated",
            "claimBoundary": "exact over declared normalized events; source-to-event completeness is external",
        },
    }
