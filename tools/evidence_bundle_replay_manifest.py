#!/usr/bin/env python3
"""Validate a provider-neutral evidence-bundle and replay manifest.

The validator is deliberately read-only. It binds every load-bearing bundle
member to a relative path, byte size, SHA-256, source revision, role and
bi-temporal collection fields, then checks that the declared replay can be
reconstructed without side effects.

This is a deterministic fixture verifier, not a runtime executor, sandbox,
security certification, or authorization service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA = "cgqa.p1-2-evidence-bundle-replay-manifest.v0.1"
RESULT_SCHEMA = "cgqa.p1-2-evidence-bundle-replay-result.v0.1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
TIMESTAMP_FIELDS = ("valid_time", "transaction_time", "collected_at")

COMPONENTS = {"liminaldb", "rinse", "contractgraph_qa", "ls"}
ROLES = {
    "intent",
    "authorization",
    "observation",
    "causal",
    "durable",
    "reflection",
    "recovery",
    "replay",
    "verification",
}


class EvidenceManifestError(ValueError):
    """Raised when a manifest or its evidence root is not verifiable."""


def _fail(message: str) -> None:
    raise EvidenceManifestError(message)


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{field} must be boolean")
    return value


def _exact_keys(value: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        _fail(f"{field} missing required keys: {', '.join(missing)}")
    if extra:
        _fail(f"{field} has unexpected keys: {', '.join(extra)}")


def _timestamp(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        _fail(f"{field} is not RFC3339-like: {exc}")
    if not text.endswith("Z"):
        _fail(f"{field} must use an explicit UTC Z suffix")
    return text


def _sha40(value: object, field: str) -> str:
    text = _text(value, field)
    if not SHA40.fullmatch(text):
        _fail(f"{field} must be a lowercase 40-character commit SHA")
    return text


def _sha64(value: object, field: str) -> str:
    text = _text(value, field)
    if not SHA64.fullmatch(text):
        _fail(f"{field} must be a lowercase 64-character SHA-256 hex digest")
    return text


def _safe_id(value: object, field: str) -> str:
    text = _text(value, field)
    if not SAFE_ID.fullmatch(text):
        _fail(f"{field} contains unsafe identifier characters")
    return text


def _safe_relative_path(value: object, field: str) -> str:
    text = _text(value, field)
    if "\\" in text or text.startswith("/"):
        _fail(f"{field} must be a relative POSIX path")
    parsed = PurePosixPath(text)
    if not parsed.parts or ".." in parsed.parts or "." in parsed.parts:
        _fail(f"{field} contains traversal or dot path components")
    if parsed.as_posix() != text:
        _fail(f"{field} is not normalized")
    return text


def _non_negative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{field} must be a non-negative integer")
    return value


def _load_json(path: Path, field: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot load {field}: {exc}")
    return _object(value, field), raw


def _validate_subjects(subjects: object) -> dict[str, dict[str, Any]]:
    items = _list(subjects, "subjects")
    if len(items) != len(COMPONENTS):
        _fail(f"subjects must contain exactly {len(COMPONENTS)} components")
    result: dict[str, dict[str, Any]] = {}
    required = {"id", "repository", "branch", "role", "head_sha", "observed_at"}
    for index, raw in enumerate(items):
        item = _object(raw, f"subjects[{index}]")
        _exact_keys(item, required, f"subjects[{index}]")
        component = _safe_id(item.get("id"), f"subjects[{index}].id")
        if component not in COMPONENTS:
            _fail(f"subjects[{index}].id is not an allowed component: {component}")
        if component in result:
            _fail(f"duplicate subject id: {component}")
        repository = _text(item.get("repository"), f"subjects[{index}].repository")
        branch = _text(item.get("branch"), f"subjects[{index}].branch")
        role = _text(item.get("role"), f"subjects[{index}].role")
        head_sha = _sha40(item.get("head_sha"), f"subjects[{index}].head_sha")
        observed_at = _timestamp(item.get("observed_at"), f"subjects[{index}].observed_at")
        result[component] = {
            "id": component,
            "repository": repository,
            "branch": branch,
            "role": role,
            "head_sha": head_sha,
            "observed_at": observed_at,
        }
    if set(result) != COMPONENTS:
        _fail("subjects must cover liminaldb, rinse, contractgraph_qa and ls")
    return result


def _validate_artifacts(
    artifacts: object,
    subjects: Mapping[str, Mapping[str, Any]],
    collection: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    items = _list(artifacts, "artifacts")
    if not items:
        _fail("artifacts must not be empty")
    required = {
        "artifact_id",
        "path",
        "role",
        "component",
        "source_revision",
        "bytes",
        "sha256",
        "content_type",
        "origin",
        "trust_domain",
        "valid_time",
        "transaction_time",
        "collected_at",
    }
    result: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    digests: set[str] = set()
    declared_collection = collection["collected_at"]
    for index, raw in enumerate(items):
        item = _object(raw, f"artifacts[{index}]")
        _exact_keys(item, required, f"artifacts[{index}]")
        artifact_id = _safe_id(item.get("artifact_id"), f"artifacts[{index}].artifact_id")
        if artifact_id in result:
            _fail(f"duplicate artifact_id: {artifact_id}")
        path = _safe_relative_path(item.get("path"), f"artifacts[{index}].path")
        if path in paths:
            _fail(f"duplicate artifact path: {path}")
        paths.add(path)
        role = _text(item.get("role"), f"artifacts[{index}].role")
        if role not in ROLES:
            _fail(f"artifacts[{index}].role is unsupported: {role}")
        component = _text(item.get("component"), f"artifacts[{index}].component")
        if component not in subjects:
            _fail(f"artifacts[{index}].component is not declared: {component}")
        source_revision = _sha40(
            item.get("source_revision"), f"artifacts[{index}].source_revision"
        )
        if source_revision != subjects[component]["head_sha"]:
            _fail(
                f"artifacts[{index}].source_revision does not match subject {component}"
            )
        byte_count = _non_negative_int(item.get("bytes"), f"artifacts[{index}].bytes")
        digest = _sha64(item.get("sha256"), f"artifacts[{index}].sha256")
        if digest in digests:
            _fail(f"duplicate artifact SHA-256: {digest}")
        digests.add(digest)
        _text(item.get("content_type"), f"artifacts[{index}].content_type")
        _text(item.get("origin"), f"artifacts[{index}].origin")
        _text(item.get("trust_domain"), f"artifacts[{index}].trust_domain")
        for field in TIMESTAMP_FIELDS:
            timestamp = _timestamp(item.get(field), f"artifacts[{index}].{field}")
            if field == "collected_at" and timestamp != declared_collection:
                _fail(
                    f"artifacts[{index}].collected_at must match collection.collected_at"
                )
        result[artifact_id] = {
            "artifact_id": artifact_id,
            "path": path,
            "role": role,
            "component": component,
            "source_revision": source_revision,
            "bytes": byte_count,
            "sha256": digest,
        }
    return result, paths


def _validate_replay(replay: object, artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    item = _object(replay, "replay")
    required = {
        "trace_id",
        "mode",
        "replayable",
        "expected_result",
        "side_effects_executed",
        "required_artifact_ids",
        "steps",
    }
    _exact_keys(item, required, "replay")
    _safe_id(item.get("trace_id"), "replay.trace_id")
    if _text(item.get("mode"), "replay.mode") != "deterministic_read_only":
        _fail("replay.mode must be deterministic_read_only")
    if _bool(item.get("replayable"), "replay.replayable") is not True:
        _fail("replay.replayable must be true")
    if _text(item.get("expected_result"), "replay.expected_result") != "SAME_RESULT":
        _fail("replay.expected_result must be SAME_RESULT")
    if _bool(item.get("side_effects_executed"), "replay.side_effects_executed"):
        _fail("replay.side_effects_executed must be false")

    required_ids = _list(item.get("required_artifact_ids"), "replay.required_artifact_ids")
    if len(required_ids) != len(set(required_ids)):
        _fail("replay.required_artifact_ids contains duplicates")
    normalized_required = [_safe_id(value, "replay.required_artifact_ids[]") for value in required_ids]
    if normalized_required != sorted(normalized_required):
        _fail("replay.required_artifact_ids must be sorted")
    if set(normalized_required) != set(artifacts):
        _fail("replay.required_artifact_ids must cover exactly all declared artifacts")

    steps = _list(item.get("steps"), "replay.steps")
    if not steps:
        _fail("replay.steps must not be empty")
    referenced: set[str] = set()
    step_required = {
        "sequence",
        "action",
        "input_artifact_ids",
        "output_artifact_ids",
        "side_effect_executed",
    }
    for expected_sequence, raw in enumerate(steps, start=1):
        step = _object(raw, f"replay.steps[{expected_sequence - 1}]")
        _exact_keys(step, step_required, f"replay.steps[{expected_sequence - 1}]")
        if step.get("sequence") != expected_sequence:
            _fail("replay step sequences must be contiguous starting at 1")
        _safe_id(step.get("action"), f"replay.steps[{expected_sequence - 1}].action")
        if _bool(
            step.get("side_effect_executed"),
            f"replay.steps[{expected_sequence - 1}].side_effect_executed",
        ):
            _fail("replay steps must not execute side effects")
        for field in ("input_artifact_ids", "output_artifact_ids"):
            ids = _list(step.get(field), f"replay.steps[{expected_sequence - 1}].{field}")
            for value in ids:
                artifact_id = _safe_id(value, f"replay.steps[{expected_sequence - 1}].{field}[]")
                if artifact_id not in artifacts:
                    _fail(f"replay references unknown artifact: {artifact_id}")
                referenced.add(artifact_id)
    if referenced != set(artifacts):
        _fail("every declared artifact must be referenced by the replay")


def _validate_shape(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    required = {
        "schema",
        "manifest_id",
        "bundle_root",
        "scope",
        "subjects",
        "artifacts",
        "replay",
        "authority",
        "collection",
    }
    _exact_keys(manifest, required, "manifest")
    if _text(manifest.get("schema"), "manifest.schema") != SCHEMA:
        _fail("manifest.schema is unsupported")
    _safe_id(manifest.get("manifest_id"), "manifest.manifest_id")
    if _safe_relative_path(manifest.get("bundle_root"), "manifest.bundle_root") != "bundle":
        _fail("manifest.bundle_root must be exactly bundle")

    scope = _object(manifest.get("scope"), "scope")
    _exact_keys(scope, {"operation_id", "mode", "claim_limit"}, "scope")
    _safe_id(scope.get("operation_id"), "scope.operation_id")
    if _text(scope.get("mode"), "scope.mode") != "bounded_fixture":
        _fail("scope.mode must be bounded_fixture")
    _text(scope.get("claim_limit"), "scope.claim_limit")

    authority = _object(manifest.get("authority"), "authority")
    _exact_keys(
        authority,
        {
            "mode",
            "proposal_is_not_authorization",
            "execution_authorized",
            "external_effects_authorized",
            "mutation_authorized",
        },
        "authority",
    )
    if _text(authority.get("mode"), "authority.mode") != "advisory_only":
        _fail("authority.mode must be advisory_only")
    if _bool(authority.get("proposal_is_not_authorization"), "authority.proposal_is_not_authorization") is not True:
        _fail("authority.proposal_is_not_authorization must be true")
    for field in ("execution_authorized", "external_effects_authorized", "mutation_authorized"):
        if _bool(authority.get(field), f"authority.{field}"):
            _fail(f"authority.{field} must be false")

    collection = _object(manifest.get("collection"), "collection")
    _exact_keys(
        collection,
        {"attempt_id", "started_at", "completed_at", "collected_at", "method", "environment"},
        "collection",
    )
    _safe_id(collection.get("attempt_id"), "collection.attempt_id")
    started = _timestamp(collection.get("started_at"), "collection.started_at")
    completed = _timestamp(collection.get("completed_at"), "collection.completed_at")
    collected = _timestamp(collection.get("collected_at"), "collection.collected_at")
    if started > completed:
        _fail("collection.started_at must not be after collection.completed_at")
    if collected != completed:
        _fail("collection.collected_at must equal collection.completed_at")
    _text(collection.get("method"), "collection.method")
    _text(collection.get("environment"), "collection.environment")

    subjects = _validate_subjects(manifest.get("subjects"))
    artifacts, _paths = _validate_artifacts(manifest.get("artifacts"), subjects, collection)
    _validate_replay(manifest.get("replay"), artifacts)
    return subjects


def _scan_bundle(root: Path) -> set[str]:
    if not root.exists() or not root.is_dir():
        _fail(f"bundle root is not a directory: {root}")
    if root.is_symlink():
        _fail("bundle root must not be a symlink")
    actual: set[str] = set()
    for entry in root.rglob("*"):
        if entry.is_symlink():
            _fail(f"symlink is not allowed in bundle: {entry}")
        if entry.is_file():
            actual.add(entry.relative_to(root).as_posix())
    return actual


def _verify_files(
    root: Path,
    artifacts: object,
) -> dict[str, str | int]:
    records = _list(artifacts, "artifacts")
    declared: set[str] = set()
    verified = 0
    total_bytes = 0
    for index, raw in enumerate(records):
        item = _object(raw, f"artifacts[{index}]")
        path = _safe_relative_path(item.get("path"), f"artifacts[{index}].path")
        declared.add(path)
        candidate = root / Path(*PurePosixPath(path).parts)
        try:
            raw_bytes = candidate.read_bytes()
        except OSError as exc:
            _fail(f"declared artifact is missing or unreadable: {path}: {exc}")
        byte_count = len(raw_bytes)
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if byte_count != item.get("bytes"):
            _fail(f"byte-size mismatch for {path}: expected {item.get('bytes')}, got {byte_count}")
        if digest != item.get("sha256"):
            _fail(f"SHA-256 mismatch for {path}")
        verified += 1
        total_bytes += byte_count
    actual = _scan_bundle(root)
    if actual != declared:
        missing = sorted(declared - actual)
        unlisted = sorted(actual - declared)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unlisted:
            details.append("unlisted=" + ",".join(unlisted))
        _fail("bundle membership mismatch: " + "; ".join(details))
    return {"verified_artifacts": verified, "total_bytes": total_bytes, "member_count": len(actual)}


def verify_bundle(
    manifest_path: Path,
    root: Path,
    *,
    checked_subject: str | None = None,
    expected_bundle_subject: str | None = None,
) -> dict[str, Any]:
    """Verify one bundle and return a deterministic result receipt."""

    manifest, raw_manifest = _load_json(manifest_path, "manifest")
    subjects = _validate_shape(manifest)
    if checked_subject is not None:
        checked_subject = _sha40(checked_subject, "checked_subject")
    if expected_bundle_subject is not None:
        expected_bundle_subject = _sha40(expected_bundle_subject, "expected_bundle_subject")
        actual_bundle_subject = subjects["contractgraph_qa"]["head_sha"]
        if actual_bundle_subject != expected_bundle_subject:
            _fail("bundle ContractGraph-QA subject does not match expected bundle subject")
    artifacts = _verify_files(root, manifest["artifacts"])
    replay = manifest["replay"]
    return {
        "schema": RESULT_SCHEMA,
        "decision": "PASS",
        "manifest_id": manifest["manifest_id"],
        "bundle_root": manifest["bundle_root"],
        "manifest_sha256": "sha256:" + hashlib.sha256(raw_manifest).hexdigest(),
        "checked_subject": checked_subject,
        "bundle_contractgraph_qa_subject": subjects["contractgraph_qa"]["head_sha"],
        "subject_count": len(subjects),
        "artifact_count": artifacts["verified_artifacts"],
        "member_count": artifacts["member_count"],
        "total_bytes": artifacts["total_bytes"],
        "replay_step_count": len(replay["steps"]),
        "replayable": replay["replayable"],
        "expected_replay_result": replay["expected_result"],
        "replay_stable": True,
        "side_effects_executed": False,
        "authority": {
            "execution_authorized": False,
            "external_effects_authorized": False,
            "mutation_authorized": False,
        },
        "claim_limit": manifest["scope"]["claim_limit"],
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify one evidence bundle")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--checked-subject")
    verify_parser.add_argument("--expected-bundle-subject")
    verify_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command != "verify":
            _fail(f"unsupported command: {args.command}")
        result = verify_bundle(
            args.manifest,
            args.root,
            checked_subject=args.checked_subject,
            expected_bundle_subject=args.expected_bundle_subject,
        )
    except EvidenceManifestError as exc:
        result = {
            "schema": RESULT_SCHEMA,
            "decision": "HOLD",
            "failure": str(exc),
            "side_effects_executed": False,
            "authority": {
                "execution_authorized": False,
                "external_effects_authorized": False,
                "mutation_authorized": False,
            },
        }
        _write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1

    _write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
