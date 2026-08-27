"""Deterministic dormant causal pattern and temporal watchpoint evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_int,
    require_list,
    require_object,
    require_subject,
    require_text,
)

SCHEMA = "cgqa/causal-watchpoints/v0.1"
ALLOWED_STATUS = {
    "DORMANT",
    "WATCHING",
    "ACTIVATED",
    "EXPIRED",
    "RESOLVED",
    "PROMOTED_TO_REGRESSION",
}


class CausalWatchpointError(CausalTemporalError):
    """Raised when watchpoint input is malformed."""


def _resolve(payload: dict[str, Any], path: str) -> object:
    current: object = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_causal_watchpoints(data: object) -> dict[str, Any]:
    model = require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise CausalWatchpointError(f"schema must equal {SCHEMA!r}")
    _, subject_hash = require_subject(model)
    current_step = require_int(model.get("currentStep"), "currentStep")
    if current_step < 0:
        raise CausalWatchpointError("currentStep must be >= 0")

    evidence = require_list(model.get("evidence", []), "evidence")
    evidence_ids: set[str] = set()
    for index, raw in enumerate(evidence):
        item = require_object(raw, f"evidence[{index}]")
        item_id = require_text(item.get("id"), f"evidence[{index}].id")
        if item_id in evidence_ids:
            raise CausalWatchpointError(f"duplicate evidence id: {item_id}")
        evidence_ids.add(item_id)
        require_int(item.get("step"), f"evidence[{index}].step")
        require_object(item.get("facts"), f"evidence[{index}].facts")
        require_text(item.get("subjectHash"), f"evidence[{index}].subjectHash")

    watchpoints = require_list(model.get("watchpoints"), "watchpoints")
    watch_ids: set[str] = set()
    for index, raw in enumerate(watchpoints):
        watch = require_object(raw, f"watchpoints[{index}]")
        watch_id = require_text(watch.get("id"), f"watchpoints[{index}].id")
        if watch_id in watch_ids:
            raise CausalWatchpointError(f"duplicate watchpoint id: {watch_id}")
        watch_ids.add(watch_id)
        status = require_text(watch.get("status"), f"watchpoints[{index}].status")
        if status not in ALLOWED_STATUS:
            raise CausalWatchpointError(f"unsupported watchpoint status: {status}")
        start = require_int(watch.get("startStep"), f"watchpoints[{index}].startStep")
        end = require_int(watch.get("endStep"), f"watchpoints[{index}].endStep")
        if start < 0 or end < start:
            raise CausalWatchpointError(f"invalid step window for {watch_id}")
        generation = require_int(watch.get("generation"), f"watchpoints[{index}].generation")
        if generation < 0:
            raise CausalWatchpointError(f"generation must be >= 0 for {watch_id}")
        if watch.get("subjectHash") != subject_hash:
            raise CausalWatchpointError(f"watchpoint {watch_id} subjectHash mismatch")
        conditions = require_list(watch.get("conditions"), f"watchpoints[{index}].conditions")
        if not conditions:
            raise CausalWatchpointError(f"watchpoint {watch_id} requires activation conditions")
        for cindex, raw_condition in enumerate(conditions):
            condition = require_object(raw_condition, f"watchpoints[{index}].conditions[{cindex}]")
            require_text(condition.get("field"), f"watchpoints[{index}].conditions[{cindex}].field")
            if "equals" not in condition:
                raise CausalWatchpointError(
                    f"watchpoints[{index}].conditions[{cindex}].equals is required"
                )
    return model


def load_causal_watchpoints(path: Path) -> dict[str, Any]:
    return validate_causal_watchpoints(json.loads(path.read_text(encoding="utf-8")))


def evaluate_causal_watchpoints(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_causal_watchpoints(model)
    subject_hash = canonical_sha256(validated["subject"])
    current_step = validated["currentStep"]
    same_subject_evidence = [
        item for item in validated.get("evidence", []) if item["subjectHash"] == subject_hash
    ]
    foreign_evidence_ids = sorted(
        item["id"]
        for item in validated.get("evidence", [])
        if item["subjectHash"] != subject_hash
    )
    results: list[dict[str, object]] = []

    for watch in sorted(validated["watchpoints"], key=lambda item: item["id"]):
        status = watch["status"]
        matched_evidence: list[str] = []
        if status in {"RESOLVED", "PROMOTED_TO_REGRESSION"}:
            next_status = status
        elif status == "EXPIRED":
            next_status = "EXPIRED"
        elif current_step > watch["endStep"]:
            next_status = "EXPIRED"
        elif current_step < watch["startStep"]:
            next_status = "DORMANT"
        else:
            for evidence in same_subject_evidence:
                if not (watch["startStep"] <= evidence["step"] <= watch["endStep"]):
                    continue
                if all(
                    _resolve(evidence["facts"], condition["field"]) == condition["equals"]
                    for condition in watch["conditions"]
                ):
                    matched_evidence.append(evidence["id"])
            next_status = "ACTIVATED" if matched_evidence else "WATCHING"

        results.append(
            {
                "id": watch["id"],
                "generation": watch["generation"],
                "previousStatus": status,
                "status": next_status,
                "matchedEvidenceIds": sorted(matched_evidence),
                "subjectHash": subject_hash,
            }
        )

    return {
        "schema": "cgqa/causal-watchpoints-result/v0.1",
        "status": "hold" if any(row["status"] == "ACTIVATED" for row in results) else "pass",
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(validated),
        "watchpoints": results,
        "foreignEvidenceIds": foreign_evidence_ids,
        "claimBoundary": (
            "A watchpoint is conditional causal memory, not a prediction. "
            "Time/step passage alone never activates a watchpoint without matching evidence conditions."
        ),
    }
