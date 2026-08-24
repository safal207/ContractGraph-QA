"""Independent witness completeness and exact-object coverage checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_list,
    require_object,
    require_subject,
    require_text,
)

SCHEMA = "cgqa/independent-witness/v0.1"
LEVELS = {"COUNT_COVERAGE", "EVENT_ID_COVERAGE", "SUBJECT_OBJECT_COVERAGE"}


class IndependentWitnessError(CausalTemporalError):
    """Raised when witness evidence is malformed."""


def _event(value: object, name: str) -> dict[str, Any]:
    event = require_object(value, name)
    require_text(event.get("eventId"), f"{name}.eventId")
    if "objectId" in event and event["objectId"] is not None:
        require_text(event["objectId"], f"{name}.objectId")
    return event


def _source(value: object, name: str, subject_hash: str) -> dict[str, Any]:
    source = require_object(value, name)
    require_text(source.get("sourceId"), f"{name}.sourceId")
    require_text(source.get("failureDomain"), f"{name}.failureDomain")
    if source.get("subjectHash") != subject_hash:
        raise IndependentWitnessError(f"{name}.subjectHash does not match the exact subject")
    events = require_list(source.get("events"), f"{name}.events")
    seen: set[str] = set()
    for index, raw in enumerate(events):
        event = _event(raw, f"{name}.events[{index}]")
        event_id = event["eventId"]
        if event_id in seen:
            raise IndependentWitnessError(f"duplicate event id in {name}: {event_id}")
        seen.add(event_id)
    return source


def validate_independent_witness(data: object) -> dict[str, Any]:
    model = require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise IndependentWitnessError(f"schema must equal {SCHEMA!r}")
    _, subject_hash = require_subject(model)
    level = require_text(model.get("coverageLevel"), "coverageLevel")
    if level not in LEVELS:
        raise IndependentWitnessError(f"coverageLevel must be one of {sorted(LEVELS)}")
    observed = _source(model.get("observed"), "observed", subject_hash)
    external = _source(model.get("external"), "external", subject_hash)
    if level == "SUBJECT_OBJECT_COVERAGE":
        for source_name, source in (("observed", observed), ("external", external)):
            for index, event in enumerate(source["events"]):
                if not event.get("objectId"):
                    raise IndependentWitnessError(
                        f"{source_name}.events[{index}].objectId is required for SUBJECT_OBJECT_COVERAGE"
                    )
    return model


def load_independent_witness(path: Path) -> dict[str, Any]:
    return validate_independent_witness(json.loads(path.read_text(encoding="utf-8")))


def evaluate_independent_witness(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_independent_witness(model)
    subject_hash = canonical_sha256(validated["subject"])
    observed = validated["observed"]
    external = validated["external"]
    level = validated["coverageLevel"]
    observed_events = {event["eventId"]: event for event in observed["events"]}
    external_events = {event["eventId"]: event for event in external["events"]}

    independent = (
        observed["sourceId"] != external["sourceId"]
        and observed["failureDomain"] != external["failureDomain"]
    )
    missing_ids = sorted(set(external_events) - set(observed_events))
    unexpected_ids = sorted(set(observed_events) - set(external_events))
    object_mismatches = sorted(
        event_id
        for event_id in set(observed_events) & set(external_events)
        if observed_events[event_id].get("objectId") != external_events[event_id].get("objectId")
    )
    count_match = len(observed_events) == len(external_events)

    reasons: list[str] = []
    if not independent:
        reasons.append("WITNESS_NOT_INDEPENDENT")
    if not count_match:
        reasons.append("COUNT_MISMATCH")
    if level in {"EVENT_ID_COVERAGE", "SUBJECT_OBJECT_COVERAGE"} and (missing_ids or unexpected_ids):
        reasons.append("EVENT_ID_COVERAGE_MISMATCH")
    if level == "SUBJECT_OBJECT_COVERAGE" and object_mismatches:
        reasons.append("SUBJECT_OBJECT_MISMATCH")

    return {
        "schema": "cgqa/independent-witness-result/v0.1",
        "status": "pass" if not reasons else "fail",
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(validated),
        "coverageLevel": level,
        "independent": independent,
        "countMatch": count_match,
        "missingEventIds": missing_ids,
        "unexpectedEventIds": unexpected_ids,
        "objectMismatches": object_mismatches,
        "reasons": reasons,
        "claimBoundary": (
            "This evaluator compares declared observed and external witness sets. "
            "A passing result does not prove that the external source itself is globally complete."
        ),
    }
