from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


MATRIX_SCHEMA = "cgqa.global-p2-4-maintenance-routines.v0.1"
RUN_SCHEMA = "cgqa.maintenance-routine-run.v0.1"
EVALUATION_SCHEMA = "cgqa.maintenance-routine-evaluation.v0.1"
EXPECTED_ROUTINE_COUNT = 2


class MaintenanceRoutineError(ValueError):
    """Raised when routine cargo is incomplete, stale, contradictory, or unsafe."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_object(value: object) -> str:
    return sha256_bytes(canonical_bytes(value))


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MaintenanceRoutineError(f"{label} must be a non-empty string")
    return value.strip()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MaintenanceRoutineError(f"{label} must be an object")
    return value


def _list(value: object, label: str, *, min_items: int = 1) -> list[Any]:
    if not isinstance(value, list) or len(value) < min_items:
        raise MaintenanceRoutineError(f"{label} must contain at least {min_items} item(s)")
    return value


def _false(value: object, label: str) -> None:
    if value is not False:
        raise MaintenanceRoutineError(f"{label} must be false")


def _sha256_ref(value: object, label: str) -> str:
    text = _text(value, label)
    if not text.startswith("sha256:") or len(text) != 71:
        raise MaintenanceRoutineError(f"{label} must be sha256:<64 hex>")
    if any(char not in "0123456789abcdef" for char in text[7:]):
        raise MaintenanceRoutineError(f"{label} must be sha256:<64 hex>")
    return text


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise MaintenanceRoutineError(
            f"git {' '.join(args)} failed for {root}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def verify_git_subject(root: Path, subject: dict[str, str]) -> dict[str, str]:
    revision = _text(subject.get("revision"), "subject.revision")
    path = _text(subject.get("path"), "subject.path")
    component = _text(subject.get("component"), "subject.component")
    repository = _text(subject.get("repository"), "subject.repository")
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise MaintenanceRoutineError(f"{component}: unsafe subject path")
    file_path = root / path
    if _git(root, "rev-parse", "HEAD") != revision:
        raise MaintenanceRoutineError(f"{component}: exact revision mismatch")
    if not file_path.is_file():
        raise MaintenanceRoutineError(f"{component}: missing subject path {path}")
    committed_blob = _git(root, "rev-parse", f"{revision}:{path}")
    worktree_blob = _git(root, "hash-object", "--", path)
    if committed_blob != worktree_blob:
        raise MaintenanceRoutineError(f"{component}: worktree subject differs from pinned revision")
    return {
        "component": component,
        "repository": repository,
        "revision": revision,
        "path": path,
        "git_blob": committed_blob,
        "sha256": sha256_bytes(file_path.read_bytes()),
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MaintenanceRoutineError(f"{label} is not readable JSON: {exc}") from exc
    return _mapping(value, label)


def run_payload(run: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(run)
    payload.pop("routine_run_digest", None)
    return payload


def expected_run_digest(run: dict[str, Any]) -> str:
    return "sha256:" + sha256_object(run_payload(run))


def validate_run(
    run: dict[str, Any],
    subject_heads: dict[str, str],
    *,
    verifier_revision: str,
) -> dict[str, Any]:
    if run.get("schema") != RUN_SCHEMA:
        raise MaintenanceRoutineError("unsupported routine run schema")
    run_id = _text(run.get("run_id"), "run.run_id")
    routine = _mapping(run.get("routine"), f"{run_id}.routine")
    routine_id = _text(routine.get("id"), f"{run_id}.routine.id")
    _text(routine.get("version"), f"{run_id}.routine.version")
    _sha256_ref(routine.get("rule_digest"), f"{run_id}.routine.rule_digest")

    target = _mapping(run.get("target"), f"{run_id}.target")
    repository = _text(target.get("repository"), f"{run_id}.target.repository")
    checked_subject = _text(target.get("checked_subject"), f"{run_id}.target.checked_subject")
    if subject_heads.get(repository) != checked_subject:
        raise MaintenanceRoutineError(f"{run_id}: target subject is stale or not pinned")
    _text(target.get("base_subject"), f"{run_id}.target.base_subject")
    _list(target.get("subject_paths"), f"{run_id}.target.subject_paths")

    observation = _mapping(run.get("observation"), f"{run_id}.observation")
    _text(observation.get("finding_id"), f"{run_id}.observation.finding_id")
    _sha256_ref(observation.get("scope_digest"), f"{run_id}.observation.scope_digest")
    _sha256_ref(observation.get("input_digest"), f"{run_id}.observation.input_digest")
    _text(observation.get("observed_at"), f"{run_id}.observation.observed_at")

    causal = _mapping(run.get("causal_case"), f"{run_id}.causal_case")
    for field in ("symptom", "causal", "alternatives", "fmd", "confidence"):
        if field not in causal:
            raise MaintenanceRoutineError(f"{run_id}.causal_case missing {field}")
    _text(causal.get("symptom"), f"{run_id}.causal_case.symptom")
    _text(causal.get("causal"), f"{run_id}.causal_case.causal")
    _list(causal.get("alternatives"), f"{run_id}.causal_case.alternatives")
    _text(causal.get("fmd"), f"{run_id}.causal_case.fmd")
    confidence = causal.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise MaintenanceRoutineError(f"{run_id}.causal_case.confidence must be between 0 and 1")

    patch = _mapping(run.get("patch"), f"{run_id}.patch")
    patch_digest = _sha256_ref(patch.get("patch_digest"), f"{run_id}.patch.patch_digest")
    changed_paths = _list(patch.get("changed_paths"), f"{run_id}.patch.changed_paths")
    if not all(isinstance(path, str) and path for path in changed_paths):
        raise MaintenanceRoutineError(f"{run_id}.patch.changed_paths must be non-empty strings")
    _text(patch.get("intended_invariant"), f"{run_id}.patch.intended_invariant")

    verification = _mapping(run.get("verification"), f"{run_id}.verification")
    if verification.get("result") != "PASS":
        raise MaintenanceRoutineError(f"{run_id}: independent verification is not PASS")
    if verification.get("replay") != "SAME_RESULT":
        raise MaintenanceRoutineError(f"{run_id}: routine replay is not SAME_RESULT")
    if verification.get("verifier_subject") != "WORKFLOW_EXACT_HEAD":
        raise MaintenanceRoutineError(f"{run_id}: verifier subject is not the workflow exact-head token")
    _list(verification.get("evidence_refs"), f"{run_id}.verification.evidence_refs")
    for index, evidence_ref in enumerate(verification["evidence_refs"]):
        _sha256_ref(evidence_ref, f"{run_id}.verification.evidence_refs[{index}]")
    _list(verification.get("negative_cases"), f"{run_id}.verification.negative_cases")

    outcome = _mapping(run.get("outcome"), f"{run_id}.outcome")
    if outcome.get("status") != "DRAFT_OPEN" or outcome.get("merge_state") != "NOT_MERGED":
        raise MaintenanceRoutineError(f"{run_id}: outcome is outside the bounded draft state")
    if outcome.get("routine_id") != routine_id or outcome.get("patch_digest") != patch_digest:
        raise MaintenanceRoutineError(f"{run_id}: outcome attribution does not match routine/patch")
    if not isinstance(outcome.get("pr_number"), int) or outcome["pr_number"] < 1:
        raise MaintenanceRoutineError(f"{run_id}.outcome.pr_number must be positive")

    authority = _mapping(run.get("authority"), f"{run_id}.authority")
    for field in (
        "may_authorize",
        "may_execute",
        "may_mutate",
        "side_effect_executed",
        "merge_authorized",
        "deployment_authorized",
        "external_effects_authorized",
    ):
        _false(authority.get(field), f"{run_id}.authority.{field}")

    recorded_digest = _sha256_ref(run.get("routine_run_digest"), f"{run_id}.routine_run_digest")
    if recorded_digest != expected_run_digest(run):
        raise MaintenanceRoutineError(f"{run_id}: routine run digest mismatch")

    return {
        "run_id": run_id,
        "routine_id": routine_id,
        "routine_version": routine["version"],
        "repository": repository,
        "checked_subject": checked_subject,
        "finding_id": observation["finding_id"],
        "patch_digest": patch_digest,
        "routine_run_digest": recorded_digest,
        "verifier_subject": verifier_revision,
        "outcome_status": outcome["status"],
        "authority_clear": True,
    }


def evaluate_runs(
    runs: Iterable[dict[str, Any]],
    subject_heads: dict[str, str],
    *,
    verifier_revision: str,
) -> dict[str, Any]:
    records = list(runs)
    if len(records) != EXPECTED_ROUTINE_COUNT:
        raise MaintenanceRoutineError(f"expected exactly {EXPECTED_ROUTINE_COUNT} routine runs")
    results = [
        validate_run(run, subject_heads, verifier_revision=verifier_revision)
        for run in records
    ]
    routine_ids = [result["routine_id"] for result in results]
    finding_ids = [result["finding_id"] for result in results]
    patch_digests = [result["patch_digest"] for result in results]
    for label, values in (("routine", routine_ids), ("finding", finding_ids), ("patch", patch_digests)):
        if len(values) != len(set(values)):
            raise MaintenanceRoutineError(f"duplicate {label} identity across routine runs")

    receipt_payload = {
        "schema": EVALUATION_SCHEMA,
        "policy": "QUALITY_ONLY_NO_MERGE_AUTHORITY",
        "decision": "PASS",
        "routine_count": len(results),
        "runs": results,
        "metrics": {
            "evidence_complete": len(results),
            "independent_verification_pass": len(results),
            "outcome_attribution_pass": len(results),
            "authority_boundary_pass": len(results),
            "replay_stable": len(results),
        },
        "all_authority_flags_false": all(result["authority_clear"] for result in results),
        "verifier_subject": verifier_revision,
        "non_claims": [
            "routine quality is not repository health",
            "draft outcome is not merge approval",
            "no deployment or production persistence",
            "no external-effect authorization",
        ],
        "authority": {
            "may_authorize": False,
            "may_execute": False,
            "may_mutate": False,
            "merge_authorized": False,
            "deployment_authorized": False,
            "external_effects_authorized": False,
        },
    }
    receipt = {
        **receipt_payload,
        "receipt_digest": "sha256:" + sha256_object(receipt_payload),
    }
    verify_evaluation_receipt(receipt)
    return receipt


def verify_evaluation_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != EVALUATION_SCHEMA or receipt.get("decision") != "PASS":
        raise MaintenanceRoutineError("unsupported or non-PASS evaluator receipt")
    recorded = _sha256_ref(receipt.get("receipt_digest"), "receipt.receipt_digest")
    payload = copy.deepcopy(receipt)
    payload.pop("receipt_digest", None)
    if recorded != "sha256:" + sha256_object(payload):
        raise MaintenanceRoutineError("evaluator receipt digest mismatch")
    authority = _mapping(receipt.get("authority"), "receipt.authority")
    for field in (
        "may_authorize",
        "may_execute",
        "may_mutate",
        "merge_authorized",
        "deployment_authorized",
        "external_effects_authorized",
    ):
        _false(authority.get(field), f"receipt.authority.{field}")


def build_subject_fingerprint(subjects: Iterable[dict[str, str]]) -> str:
    records = list(subjects)
    components = [record["component"] for record in records]
    if len(components) != len(set(components)):
        raise MaintenanceRoutineError("duplicate component in routine subject set")
    return sha256_object(
        {
            "schema": "cgqa.p2-4-subject-set.v0.1",
            "subjects": sorted(records, key=lambda item: item["component"]),
        }
    )


def replay(
    *,
    matrix_path: Path,
    checkout_root: Path,
    verifier_root: Path,
    verifier_revision: str,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path, "P2-4 routine matrix")
    if matrix.get("schema") != MATRIX_SCHEMA:
        raise MaintenanceRoutineError("unsupported P2-4 matrix schema")
    subject_entries = _list(matrix.get("subjects"), "matrix.subjects")
    verified_subjects: list[dict[str, str]] = []
    subject_heads: dict[str, str] = {}
    for raw in subject_entries:
        subject = _mapping(raw, "matrix.subjects[]")
        checkout_dir = _text(subject.get("checkout_dir"), "subject.checkout_dir")
        if Path(checkout_dir).is_absolute() or ".." in Path(checkout_dir).parts:
            raise MaintenanceRoutineError("unsafe subject checkout directory")
        verified = verify_git_subject(checkout_root / checkout_dir, {
            "component": _text(subject.get("component"), "subject.component"),
            "repository": _text(subject.get("repository"), "subject.repository"),
            "revision": _text(subject.get("revision"), "subject.revision"),
            "path": _text(subject.get("path"), "subject.path"),
        })
        verified_subjects.append(verified)
        subject_heads[verified["repository"]] = verified["revision"]

    self_subject = {
        "component": "contractgraph_qa",
        "repository": "safal207/ContractGraph-QA",
        "revision": verifier_revision,
        "path": "tools/maintenance_routine_evaluator.py",
    }
    verified_subjects.append(verify_git_subject(verifier_root, self_subject))

    runs = _list(matrix.get("routine_runs"), "matrix.routine_runs")
    receipt = evaluate_runs(runs, subject_heads, verifier_revision=verifier_revision)
    subject_fingerprint = build_subject_fingerprint(verified_subjects)
    witness_payload = {
        "schema": "cgqa.p2-4-maintenance-routine-replay.v0.1",
        "decision": "PASS",
        "policy": receipt["policy"],
        "routine_count": receipt["routine_count"],
        "subject_fingerprint": subject_fingerprint,
        "receipt_digest": receipt["receipt_digest"],
        "routine_run_digests": [item["routine_run_digest"] for item in receipt["runs"]],
        "outcome_attribution_pass": receipt["metrics"]["outcome_attribution_pass"],
        "all_authority_flags_false": receipt["all_authority_flags_false"],
        "side_effects_executed": False,
        "production_ledger_mutated": False,
        "verifier_revision": verifier_revision,
    }
    return {
        **witness_payload,
        "subjects": sorted(verified_subjects, key=lambda item: item["component"]),
        "evaluation_receipt": receipt,
        "witness_digest": sha256_object(witness_payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate bounded evidence-bound repository maintenance routines")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--checkout-root", type=Path, required=True)
    parser.add_argument("--verifier-root", type=Path, default=Path("."))
    parser.add_argument("--verifier-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = replay(
            matrix_path=args.matrix,
            checkout_root=args.checkout_root,
            verifier_root=args.verifier_root,
            verifier_revision=args.verifier_revision,
        )
    except (MaintenanceRoutineError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"decision": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
