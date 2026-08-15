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
VERIFICATION_SCHEMA = "cgqa.global-p2-1-trust-spine-verification.v0.1"
POLICY = "READ_ONLY_MEASUREMENT_NO_AUTHORITY"
EXPECTED_ROUTE = ["intent", "ProofPath", "CML", "LiminalDB", "RINSE", "ContractGraph-QA"]
EXPECTED_SOURCE_RUN_ID = 31879737027
EXPECTED_SOURCE_JOB_ID = 95000538396
EXPECTED_MEASURED_HEAD = "7fd3e744037832b74b2ee4c4c71cc8fce18fc329"
EXPECTED_ARTIFACT_ID = 9245706691
EXPECTED_GROUPS = ["preflight", "intent_cml", "proofpath", "liminaldb", "rinse", "contractgraph_qa", "evidence_packaging"]


class TrustSpineVerificationError(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_object(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrustSpineVerificationError(f"{label} must be an object")
    return value


def _list(value: object, label: str, *, min_items: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_items:
        raise TrustSpineVerificationError(f"{label} must contain at least {min_items} item(s)")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TrustSpineVerificationError(f"{label} must be a non-empty string")
    return value.strip()


def _false(value: object, label: str) -> None:
    if value is not False:
        raise TrustSpineVerificationError(f"{label} must be false")


def _sha256_ref(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 71 or not text.startswith("sha256:") or any(c not in "0123456789abcdef" for c in text[7:]):
        raise TrustSpineVerificationError(f"{label} must be sha256:<64 hex>")
    return text


def _git_sha(value: object, label: str) -> str:
    text = _text(value, label)
    if len(text) != 40 or any(c not in "0123456789abcdef" for c in text):
        raise TrustSpineVerificationError(f"{label} must be a 40-character lowercase git SHA")
    return text


def _ts(value: object, label: str) -> datetime:
    text = _text(value, label)
    if not text.endswith("Z"):
        raise TrustSpineVerificationError(f"{label} must end in Z")
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise TrustSpineVerificationError(f"{label} is not valid RFC3339") from exc


def _verify_digest(record: dict[str, Any], field: str, label: str) -> None:
    recorded = _sha256_ref(record.get(field), f"{label}.{field}")
    payload = copy.deepcopy(record)
    payload.pop(field, None)
    if recorded != "sha256:" + sha256_object(payload):
        raise TrustSpineVerificationError(f"{label} digest mismatch")


def recompute_source(snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("schema") != SOURCE_SCHEMA:
        raise TrustSpineVerificationError("unsupported source schema")
    _verify_digest(snapshot, "snapshot_digest", "snapshot")
    measured = _mapping(snapshot.get("measured_system"), "measured_system")
    if measured.get("trust_spine_route") != EXPECTED_ROUTE:
        raise TrustSpineVerificationError("source route order mismatch")
    source = _mapping(snapshot.get("source"), "source")
    if source.get("conclusion") != "success":
        raise TrustSpineVerificationError("source conclusion must be success")
    head_sha = _git_sha(source.get("head_sha"), "source.head_sha")
    if source.get("workflow_run_id") != EXPECTED_SOURCE_RUN_ID:
        raise TrustSpineVerificationError("source workflow run does not match frozen observation")
    if source.get("job_id") != EXPECTED_SOURCE_JOB_ID:
        raise TrustSpineVerificationError("source job does not match frozen observation")
    if head_sha != EXPECTED_MEASURED_HEAD:
        raise TrustSpineVerificationError("source head does not match frozen measured subject")
    if source.get("timestamp_resolution_seconds") != 1:
        raise TrustSpineVerificationError("source timestamp resolution must be one second")
    job_start = _ts(source.get("started_at"), "source.started_at")
    job_end = _ts(source.get("completed_at"), "source.completed_at")
    if job_end < job_start:
        raise TrustSpineVerificationError("source job has negative duration")
    job_elapsed = int((job_end - job_start).total_seconds())

    raw_steps = _list(snapshot.get("substantive_steps"), "substantive_steps")
    step_rows, numbers, group_sequence = [], [], []
    previous_end = None
    for index, raw in enumerate(raw_steps):
        step = _mapping(raw, f"step[{index}]")
        number = step.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise TrustSpineVerificationError("step number must be positive")
        numbers.append(number)
        name = _text(step.get("name"), f"step[{index}].name")
        group = _text(step.get("group"), f"step[{index}].group")
        if group not in EXPECTED_GROUPS:
            raise TrustSpineVerificationError(f"unsupported group {group}")
        if not group_sequence or group_sequence[-1] != group:
            group_sequence.append(group)
        if step.get("conclusion") != "success":
            raise TrustSpineVerificationError(f"{name}: source step is not success")
        start = _ts(step.get("started_at"), f"{name}.started_at")
        end = _ts(step.get("completed_at"), f"{name}.completed_at")
        if end < start:
            raise TrustSpineVerificationError(f"{name}: negative duration")
        if previous_end is not None and start < previous_end:
            raise TrustSpineVerificationError(f"{name}: reordered or overlapping timestamp")
        previous_end = end
        step_rows.append({"number": number, "name": name, "group": group, "observed_seconds": int((end - start).total_seconds())})
    if numbers != sorted(numbers) or len(numbers) != len(set(numbers)):
        raise TrustSpineVerificationError("step numbers must be strictly increasing")
    if group_sequence != EXPECTED_GROUPS:
        raise TrustSpineVerificationError("measurement group order mismatch")
    first = _ts(raw_steps[0]["started_at"], "first.started_at")
    last = _ts(raw_steps[-1]["completed_at"], "last.completed_at")
    if first < job_start or last > job_end:
        raise TrustSpineVerificationError("substantive timestamps outside job")
    window = int((last - first).total_seconds())
    summed = sum(row["observed_seconds"] for row in step_rows)
    if summed > window:
        raise TrustSpineVerificationError("summed duration exceeds window")
    grouped = {group: 0 for group in EXPECTED_GROUPS}
    for row in step_rows:
        grouped[row["group"]] += row["observed_seconds"]

    artifacts = _list(snapshot.get("artifacts"), "artifacts")
    artifact_rows, total_bytes = [], 0
    for index, raw in enumerate(artifacts):
        artifact = _mapping(raw, f"artifact[{index}]")
        artifact_id = artifact.get("id")
        size = artifact.get("size_in_bytes")
        if not isinstance(artifact_id, int) or artifact_id < 1:
            raise TrustSpineVerificationError("artifact id must be positive")
        if index == 0 and artifact_id != EXPECTED_ARTIFACT_ID:
            raise TrustSpineVerificationError("artifact id does not match frozen source artifact")
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            raise TrustSpineVerificationError("artifact size must be positive")
        digest = _sha256_ref(artifact.get("digest"), f"artifact[{index}].digest")
        if artifact.get("expired") is not False:
            raise TrustSpineVerificationError("source artifact must be unexpired in frozen observation")
        total_bytes += size
        artifact_rows.append({"id": artifact_id, "name": _text(artifact.get("name"), f"artifact[{index}].name"), "size_in_bytes": size, "digest": digest})
    scope = _mapping(snapshot.get("cost_scope"), "cost_scope")
    if scope.get("monetary_cost_status") != "NOT_MEASURED" or scope.get("monetary_cost_usd") is not None:
        raise TrustSpineVerificationError("source must not fabricate monetary cost")
    authority = _mapping(snapshot.get("authority"), "authority")
    for field in ("may_authorize", "may_execute", "may_mutate", "merge_authorized", "deployment_authorized", "external_effects_authorized"):
        _false(authority.get(field), f"source.authority.{field}")
    return {
        "job_elapsed_seconds": job_elapsed,
        "substantive_window_seconds": window,
        "summed_substantive_step_seconds": summed,
        "runner_overhead_seconds": job_elapsed - window,
        "steps": step_rows,
        "groups": [{"group": g, "observed_seconds": grouped[g]} for g in EXPECTED_GROUPS],
        "artifact_bytes": total_bytes,
        "artifact_count": len(artifact_rows),
        "artifacts": artifact_rows,
    }


def verify(snapshot: dict[str, Any], receipt: dict[str, Any], *, verifier_subject: str) -> dict[str, Any]:
    recomputed = recompute_source(snapshot)
    _git_sha(verifier_subject, "verifier_subject")
    if receipt.get("schema") != MEASUREMENT_SCHEMA:
        raise TrustSpineVerificationError("unsupported measurement receipt schema")
    if receipt.get("policy") != POLICY or receipt.get("decision") != "PASS":
        raise TrustSpineVerificationError("measurement receipt policy/decision mismatch")
    _verify_digest(receipt, "receipt_digest", "measurement receipt")
    source = _mapping(snapshot.get("source"), "source")
    receipt_source = _mapping(receipt.get("source"), "receipt.source")
    expected_source = {"repository": source.get("repository"), "workflow_run_id": source.get("workflow_run_id"), "job_id": source.get("job_id"), "workflow_name": source.get("workflow_name"), "head_sha": source.get("head_sha"), "snapshot_digest": snapshot.get("snapshot_digest")}
    if receipt_source != expected_source:
        raise TrustSpineVerificationError("measurement source identity mismatch")
    if receipt.get("trust_spine_route") != EXPECTED_ROUTE:
        raise TrustSpineVerificationError("receipt route order mismatch")
    if receipt.get("timestamp_resolution_seconds") != 1:
        raise TrustSpineVerificationError("receipt timestamp resolution mismatch")
    latency = _mapping(receipt.get("latency"), "receipt.latency")
    expected_latency = {"job_elapsed_seconds": recomputed["job_elapsed_seconds"], "substantive_window_seconds": recomputed["substantive_window_seconds"], "summed_substantive_step_seconds": recomputed["summed_substantive_step_seconds"], "runner_overhead_seconds": recomputed["runner_overhead_seconds"], "measurement_groups": recomputed["groups"], "steps": recomputed["steps"]}
    if latency != expected_latency:
        raise TrustSpineVerificationError("latency aggregate or step measurement mismatch")
    structural = _mapping(receipt.get("structural_cost"), "receipt.structural_cost")
    expected_structural = {"substantive_step_count": len(recomputed["steps"]), "artifact_count": recomputed["artifact_count"], "artifact_bytes": recomputed["artifact_bytes"], "artifacts": recomputed["artifacts"]}
    if structural != expected_structural:
        raise TrustSpineVerificationError("structural cost mismatch")
    monetary = _mapping(receipt.get("monetary_cost"), "receipt.monetary_cost")
    if monetary != {"status": "NOT_MEASURED", "amount_usd": None}:
        raise TrustSpineVerificationError("monetary cost must remain explicitly unmeasured")
    authority = _mapping(receipt.get("authority"), "receipt.authority")
    for field in ("may_authorize", "may_execute", "may_mutate", "merge_authorized", "deployment_authorized", "external_effects_authorized"):
        _false(authority.get(field), f"receipt.authority.{field}")
    payload = {
        "schema": VERIFICATION_SCHEMA,
        "policy": POLICY,
        "decision": "PASS",
        "source_measurement_digest": receipt["receipt_digest"],
        "source_snapshot_digest": snapshot["snapshot_digest"],
        "measured_subject": source["head_sha"],
        "verifier_subject": verifier_subject,
        "recomputed": {"job_elapsed_seconds": recomputed["job_elapsed_seconds"], "substantive_window_seconds": recomputed["substantive_window_seconds"], "summed_substantive_step_seconds": recomputed["summed_substantive_step_seconds"], "runner_overhead_seconds": recomputed["runner_overhead_seconds"], "substantive_step_count": len(recomputed["steps"]), "artifact_count": recomputed["artifact_count"], "artifact_bytes": recomputed["artifact_bytes"]},
        "dominant_measurement_group": max(recomputed["groups"], key=lambda item: (item["observed_seconds"], item["group"])),
        "producer_imported": False,
        "measurement_recomputed": True,
        "monetary_cost_status": "NOT_MEASURED",
        "timestamp_resolution_seconds": 1,
        "authority": {"may_authorize": False, "may_execute": False, "may_mutate": False, "merge_authorized": False, "deployment_authorized": False, "external_effects_authorized": False},
        "non_claims": ["observed CI latency is not a production latency SLA", "zero-second source steps are below timestamp resolution, not proven zero compute", "artifact bytes are not total system cost", "monetary provider cost remains unknown", "verification receipt grants no execution or merge authority"],
    }
    return {**payload, "verification_digest": "sha256:" + sha256_object(payload)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify P2-1 trust-spine measurement")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, required=True)
    parser.add_argument("--verifier-subject", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.source.read_text(encoding="utf-8"))
        receipt = json.loads(args.measurement.read_text(encoding="utf-8"))
        if not isinstance(snapshot, dict) or not isinstance(receipt, dict):
            raise TrustSpineVerificationError("source and measurement must be JSON objects")
        result = verify(snapshot, receipt, verifier_subject=args.verifier_subject)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TrustSpineVerificationError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
