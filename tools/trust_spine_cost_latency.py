from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SOURCE_SCHEMA = "cgqa.global-p2-1-trust-spine-source.v0.1"
MEASUREMENT_SCHEMA = "cgqa.global-p2-1-trust-spine-measurement.v0.1"
POLICY = "READ_ONLY_MEASUREMENT_NO_AUTHORITY"
EXPECTED_ROUTE = ["intent", "ProofPath", "CML", "LiminalDB", "RINSE", "ContractGraph-QA"]
EXPECTED_SOURCE_RUN_ID = 31879737027
EXPECTED_SOURCE_JOB_ID = 95000538396
EXPECTED_MEASURED_HEAD = "7fd3e744037832b74b2ee4c4c71cc8fce18fc329"
EXPECTED_ARTIFACT_ID = 9245706691
EXPECTED_GROUPS = [
    "preflight",
    "intent_cml",
    "proofpath",
    "liminaldb",
    "rinse",
    "contractgraph_qa",
    "evidence_packaging",
]


class TrustSpineMeasurementError(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_object(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrustSpineMeasurementError(f"{label} must be a non-empty string")
    return value.strip()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrustSpineMeasurementError(f"{label} must be an object")
    return value


def _list(value: object, label: str, *, min_items: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_items:
        raise TrustSpineMeasurementError(f"{label} must contain at least {min_items} item(s)")
    return value


def _false(value: object, label: str) -> None:
    if value is not False:
        raise TrustSpineMeasurementError(f"{label} must be false")


def _sha(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 40 or any(c not in "0123456789abcdef" for c in text):
        raise TrustSpineMeasurementError(f"{label} must be a 40-character lowercase git SHA")
    return text


def _sha256_ref(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 71 or not text.startswith("sha256:"):
        raise TrustSpineMeasurementError(f"{label} must be sha256:<64 hex>")
    if any(c not in "0123456789abcdef" for c in text[7:]):
        raise TrustSpineMeasurementError(f"{label} must be sha256:<64 hex>")
    return text


def _ts(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise TrustSpineMeasurementError(f"{label} must be UTC RFC3339 ending in Z")
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise TrustSpineMeasurementError(f"{label} is not valid RFC3339") from exc


def _duration_seconds(start: object, end: object, label: str) -> int:
    delta = (_ts(end, f"{label}.completed_at") - _ts(start, f"{label}.started_at")).total_seconds()
    if delta < 0:
        raise TrustSpineMeasurementError(f"{label} has negative duration")
    if int(delta) != delta:
        raise TrustSpineMeasurementError(f"{label} duration must align to source timestamp resolution")
    return int(delta)


def _verify_snapshot_digest(snapshot: dict[str, Any]) -> None:
    recorded = _sha256_ref(snapshot.get("snapshot_digest"), "snapshot.snapshot_digest")
    payload = copy.deepcopy(snapshot)
    payload.pop("snapshot_digest", None)
    expected = "sha256:" + sha256_object(payload)
    if recorded != expected:
        raise TrustSpineMeasurementError("snapshot digest mismatch")


def measure(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SOURCE_SCHEMA:
        raise TrustSpineMeasurementError("unsupported P2-1 source schema")
    _verify_snapshot_digest(snapshot)

    measured_system = _mapping(snapshot.get("measured_system"), "measured_system")
    if measured_system.get("trust_spine_route") != EXPECTED_ROUTE:
        raise TrustSpineMeasurementError("trust-spine route order mismatch")

    source = _mapping(snapshot.get("source"), "source")
    if source.get("conclusion") != "success":
        raise TrustSpineMeasurementError("source workflow job must be successful")
    head_sha = _sha(source.get("head_sha"), "source.head_sha")
    if source.get("workflow_run_id") != EXPECTED_SOURCE_RUN_ID:
        raise TrustSpineMeasurementError("source.workflow_run_id does not match frozen observation")
    if source.get("job_id") != EXPECTED_SOURCE_JOB_ID:
        raise TrustSpineMeasurementError("source.job_id does not match frozen observation")
    if head_sha != EXPECTED_MEASURED_HEAD:
        raise TrustSpineMeasurementError("source.head_sha does not match frozen measured subject")
    if source.get("run_attempt") != 1:
        raise TrustSpineMeasurementError("source.run_attempt must be 1 for the frozen observation")
    resolution = source.get("timestamp_resolution_seconds")
    if resolution != 1:
        raise TrustSpineMeasurementError("timestamp resolution must be exactly one second")

    job_elapsed = _duration_seconds(source.get("started_at"), source.get("completed_at"), "source.job")
    _ts(source.get("created_at"), "source.created_at")

    steps = _list(snapshot.get("substantive_steps"), "substantive_steps")
    numbers: list[int] = []
    groups_seen: list[str] = []
    step_rows: list[dict[str, Any]] = []
    previous_completed: datetime | None = None

    for index, raw in enumerate(steps):
        step = _mapping(raw, f"substantive_steps[{index}]")
        number = step.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise TrustSpineMeasurementError(f"substantive_steps[{index}].number must be positive")
        numbers.append(number)
        name = _text(step.get("name"), f"substantive_steps[{index}].name")
        group = _text(step.get("group"), f"substantive_steps[{index}].group")
        if group not in EXPECTED_GROUPS:
            raise TrustSpineMeasurementError(f"unsupported measurement group: {group}")
        if not groups_seen or groups_seen[-1] != group:
            groups_seen.append(group)
        if step.get("conclusion") != "success":
            raise TrustSpineMeasurementError(f"{name}: source step is not successful")

        started = _ts(step.get("started_at"), f"{name}.started_at")
        completed = _ts(step.get("completed_at"), f"{name}.completed_at")
        if completed < started:
            raise TrustSpineMeasurementError(f"{name}: negative duration")
        if previous_completed is not None and started < previous_completed:
            raise TrustSpineMeasurementError(f"{name}: step timestamps overlap or reorder")
        previous_completed = completed
        seconds = int((completed - started).total_seconds())
        step_rows.append({"number": number, "name": name, "group": group, "observed_seconds": seconds})

    if numbers != sorted(numbers) or len(numbers) != len(set(numbers)):
        raise TrustSpineMeasurementError("substantive step numbers must be strictly increasing")
    if groups_seen != EXPECTED_GROUPS:
        raise TrustSpineMeasurementError("measurement group order mismatch")

    job_start = _ts(source["started_at"], "source.started_at")
    job_end = _ts(source["completed_at"], "source.completed_at")
    first_start = _ts(steps[0]["started_at"], "first.started_at")
    last_end = _ts(steps[-1]["completed_at"], "last.completed_at")
    if first_start < job_start or last_end > job_end:
        raise TrustSpineMeasurementError("substantive window lies outside job window")

    substantive_window = int((last_end - first_start).total_seconds())
    summed_step_seconds = sum(row["observed_seconds"] for row in step_rows)
    if summed_step_seconds > substantive_window:
        raise TrustSpineMeasurementError("summed step seconds exceed substantive window")

    grouped: dict[str, int] = {group: 0 for group in EXPECTED_GROUPS}
    for row in step_rows:
        grouped[row["group"]] += row["observed_seconds"]

    artifacts = _list(snapshot.get("artifacts"), "artifacts")
    artifact_rows: list[dict[str, Any]] = []
    total_artifact_bytes = 0
    for index, raw in enumerate(artifacts):
        artifact = _mapping(raw, f"artifacts[{index}]")
        artifact_id = artifact.get("id")
        size = artifact.get("size_in_bytes")
        if not isinstance(artifact_id, int) or artifact_id < 1:
            raise TrustSpineMeasurementError("artifact.id must be positive")
        if index == 0 and artifact_id != EXPECTED_ARTIFACT_ID:
            raise TrustSpineMeasurementError("artifact.id does not match frozen source artifact")
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise TrustSpineMeasurementError("artifact.size_in_bytes must be positive")
        digest = _sha256_ref(artifact.get("digest"), f"artifacts[{index}].digest")
        if artifact.get("expired") is not False:
            raise TrustSpineMeasurementError("frozen source artifact must be unexpired at observation time")
        _ts(artifact.get("created_at"), f"artifacts[{index}].created_at")
        total_artifact_bytes += size
        artifact_rows.append({"id": artifact_id, "name": _text(artifact.get("name"), f"artifacts[{index}].name"), "size_in_bytes": size, "digest": digest})

    cost_scope = _mapping(snapshot.get("cost_scope"), "cost_scope")
    if cost_scope.get("monetary_cost_status") != "NOT_MEASURED":
        raise TrustSpineMeasurementError("monetary cost status must remain NOT_MEASURED")
    if cost_scope.get("monetary_cost_usd") is not None:
        raise TrustSpineMeasurementError("monetary cost must be null when not measured")

    authority = _mapping(snapshot.get("authority"), "authority")
    for field in ("may_authorize", "may_execute", "may_mutate", "merge_authorized", "deployment_authorized", "external_effects_authorized"):
        _false(authority.get(field), f"authority.{field}")

    payload = {
        "schema": MEASUREMENT_SCHEMA,
        "case_id": _text(snapshot.get("case_id"), "case_id"),
        "policy": POLICY,
        "decision": "PASS",
        "source": {
            "repository": _text(source.get("repository"), "source.repository"),
            "workflow_run_id": source.get("workflow_run_id"),
            "job_id": source.get("job_id"),
            "workflow_name": _text(source.get("workflow_name"), "source.workflow_name"),
            "head_sha": head_sha,
            "snapshot_digest": snapshot["snapshot_digest"],
        },
        "trust_spine_route": EXPECTED_ROUTE,
        "timestamp_resolution_seconds": resolution,
        "latency": {
            "job_elapsed_seconds": job_elapsed,
            "substantive_window_seconds": substantive_window,
            "summed_substantive_step_seconds": summed_step_seconds,
            "runner_overhead_seconds": job_elapsed - substantive_window,
            "measurement_groups": [{"group": group, "observed_seconds": grouped[group]} for group in EXPECTED_GROUPS],
            "steps": step_rows,
        },
        "structural_cost": {
            "substantive_step_count": len(step_rows),
            "artifact_count": len(artifact_rows),
            "artifact_bytes": total_artifact_bytes,
            "artifacts": artifact_rows,
        },
        "monetary_cost": {"status": "NOT_MEASURED", "amount_usd": None},
        "resolution_note": "GitHub Actions timestamps are one-second resolution in this frozen source; 0 observed seconds means below source resolution, not exact zero compute.",
        "non_claims": list(snapshot.get("non_claims", [])),
        "authority": {
            "may_authorize": False,
            "may_execute": False,
            "may_mutate": False,
            "merge_authorized": False,
            "deployment_authorized": False,
            "external_effects_authorized": False,
        },
    }
    return {**payload, "receipt_digest": "sha256:" + sha256_object(payload)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive P2-1 trust-spine cost/latency measurement")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.source.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict):
            raise TrustSpineMeasurementError("source must be a JSON object")
        result = measure(snapshot)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TrustSpineMeasurementError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
