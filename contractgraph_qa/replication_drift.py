"""Fresh temporal/external replication and drift classification over frozen targets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_bool,
    require_int,
    require_object,
    require_text,
)

SCHEMA = "cgqa/replication-drift/v0.1"
MODES = {"TEMPORAL", "EXTERNAL", "TEMPORAL_EXTERNAL"}


class ReplicationDriftError(CausalTemporalError):
    """Raised when replication/drift input is malformed."""


def _snapshot(value: object, name: str) -> dict[str, Any]:
    item = require_object(value, name)
    subject = require_object(item.get("subject"), f"{name}.subject")
    if not subject:
        raise ReplicationDriftError(f"{name}.subject must not be empty")
    require_int(item.get("generation"), f"{name}.generation")
    require_text(item.get("sourceId"), f"{name}.sourceId")
    require_text(item.get("evidenceHash"), f"{name}.evidenceHash")
    require_text(item.get("structureSignature"), f"{name}.structureSignature")
    metrics = require_object(item.get("performance", {}), f"{name}.performance")
    for key, raw in metrics.items():
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            raise ReplicationDriftError(f"{name}.performance.{key} must be numeric")
    return item


def validate_replication_drift(data: object) -> dict[str, Any]:
    model = require_object(data, "model")
    if model.get("schema") != SCHEMA:
        raise ReplicationDriftError(f"schema must equal {SCHEMA!r}")
    mode = require_text(model.get("mode"), "mode")
    if mode not in MODES:
        raise ReplicationDriftError(f"mode must be one of {sorted(MODES)}")
    target = _snapshot(model.get("target"), "target")
    replication = _snapshot(model.get("replication"), "replication")
    refit = model.get("refitOnReplication", False)
    require_bool(refit, "refitOnReplication")
    current_generation = require_int(model.get("currentGeneration"), "currentGeneration")
    thresholds = require_object(model.get("performanceThresholds", {}), "performanceThresholds")
    for key, raw in thresholds.items():
        if not isinstance(raw, (int, float)) or isinstance(raw, bool) or raw < 0:
            raise ReplicationDriftError(f"performanceThresholds.{key} must be a non-negative number")
    if target["generation"] < 0 or replication["generation"] < 0 or current_generation < 0:
        raise ReplicationDriftError("generations must be >= 0")
    return model


def load_replication_drift(path: Path) -> dict[str, Any]:
    return validate_replication_drift(json.loads(path.read_text(encoding="utf-8")))


def evaluate_replication_drift(model: dict[str, Any]) -> dict[str, object]:
    validated = validate_replication_drift(model)
    target = validated["target"]
    replication = validated["replication"]
    mode = validated["mode"]
    freshness_failures: list[str] = []

    if replication["generation"] <= target["generation"]:
        freshness_failures.append("REPLICATION_NOT_NEWER")
    if replication["evidenceHash"] == target["evidenceHash"]:
        freshness_failures.append("EVIDENCE_REUSED")
    if mode in {"EXTERNAL", "TEMPORAL_EXTERNAL"} and replication["sourceId"] == target["sourceId"]:
        freshness_failures.append("EXTERNAL_SOURCE_NOT_DISTINCT")
    if validated["refitOnReplication"]:
        freshness_failures.append("REPLICATION_DATA_USED_FOR_REFIT")
    if validated["currentGeneration"] != replication["generation"]:
        freshness_failures.append("STALE_REPLICATION_TARGET")

    target_lineage = dict(target["subject"])
    replication_lineage = dict(replication["subject"])
    for key in ("generation", "commit", "version"):
        target_lineage.pop(key, None)
        replication_lineage.pop(key, None)
    if target_lineage != replication_lineage:
        freshness_failures.append("SUBJECT_LINEAGE_MISMATCH")

    structural = target["structureSignature"] != replication["structureSignature"]
    metric_deltas: list[dict[str, object]] = []
    performance = False
    thresholds = validated["performanceThresholds"]
    for key in sorted(set(target["performance"]) | set(replication["performance"])):
        if key not in target["performance"] or key not in replication["performance"]:
            performance = True
            metric_deltas.append({"metric": key, "status": "MISSING_SIDE"})
            continue
        before = float(target["performance"][key])
        after = float(replication["performance"][key])
        delta = after - before
        threshold = float(thresholds.get(key, 0.0))
        exceeded = abs(delta) > threshold
        performance = performance or exceeded
        metric_deltas.append(
            {
                "metric": key,
                "before": before,
                "after": after,
                "delta": delta,
                "threshold": threshold,
                "thresholdExceeded": exceeded,
            }
        )

    if structural and performance:
        drift_kind = "BOTH"
    elif structural:
        drift_kind = "STRUCTURAL_DRIFT"
    elif performance:
        drift_kind = "PERFORMANCE_DRIFT"
    else:
        drift_kind = "NONE"

    if freshness_failures:
        status = "fail"
    elif drift_kind == "NONE":
        status = "pass"
    else:
        status = "hold"

    return {
        "schema": "cgqa/replication-drift-result/v0.1",
        "status": status,
        "mode": mode,
        "inputHash": canonical_sha256(validated),
        "targetSubjectHash": canonical_sha256(target["subject"]),
        "replicationSubjectHash": canonical_sha256(replication["subject"]),
        "freshness": "FRESH" if not freshness_failures else "REJECTED",
        "freshnessFailures": freshness_failures,
        "driftKind": drift_kind,
        "metricDeltas": metric_deltas,
        "remediationAuthorized": False,
        "claimBoundary": (
            "Confirmed_t != Confirmed_t+1. A drift signal is not model falsehood, "
            "and replication does not itself authorize remediation or rollback."
        ),
    }
