"""Verify that evidence and reflection cannot become execution authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


SCHEMA = "cgqa.p1-3-authority-reflection-boundary.v0.1"
RESULT_SCHEMA = "cgqa.p1-3-authority-reflection-boundary-result.v0.1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class BoundaryError(ValueError):
    """Raised when the boundary fixture is invalid or tries to escalate authority."""


def _fail(message: str) -> None:
    raise BoundaryError(message)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{label} must be an array")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty string")
    return value


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{label} must be boolean")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        _fail(f"{label} keys mismatch: " + "; ".join(details))


def _safe_id(value: object, label: str) -> str:
    result = _text(value, label)
    if not SAFE_ID.fullmatch(result):
        _fail(f"{label} is not path-safe")
    return result


def _sha40(value: object, label: str) -> str:
    result = _text(value, label)
    if not SHA40.fullmatch(result):
        _fail(f"{label} must be a lowercase 40-character SHA")
    return result


def _sha64(value: object, label: str) -> str:
    result = _text(value, label)
    if not SHA64.fullmatch(result):
        _fail(f"{label} must be a lowercase 64-character SHA")
    return result


def _timestamp(value: object, label: str) -> str:
    result = _text(value, label)
    try:
        datetime.fromisoformat(result.replace("Z", "+00:00"))
    except ValueError as exc:
        _fail(f"{label} must be RFC3339: {exc}")
    return result


def _safe_relative_path(value: object, label: str) -> str:
    result = _text(value, label)
    if "\\" in result:
        _fail(f"{label} must use POSIX separators")
    path = PurePosixPath(result)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        _fail(f"{label} contains absolute path or traversal")
    return path.as_posix()


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"cannot load {label}: {exc}")
    return _object(value, label), raw


def _validate_subjects(value: object) -> dict[str, dict[str, Any]]:
    subjects: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_list(value, "subjects")):
        subject = _object(raw, f"subjects[{index}]")
        _exact_keys(subject, {"id", "repository", "head_sha", "role", "observed_at"}, f"subjects[{index}]")
        subject_id = _safe_id(subject["id"], f"subjects[{index}].id")
        if subject_id in subjects:
            _fail(f"duplicate subject id: {subject_id}")
        subject["repository"] = _text(subject["repository"], f"subjects[{index}].repository")
        subject["head_sha"] = _sha40(subject["head_sha"], f"subjects[{index}].head_sha")
        subject["role"] = _text(subject["role"], f"subjects[{index}].role")
        subject["observed_at"] = _timestamp(subject["observed_at"], f"subjects[{index}].observed_at")
        subjects[subject_id] = subject
    required = {"contractgraph_qa", "proofpath", "liminaldb", "rinse", "ls"}
    if set(subjects) != required:
        _fail("subjects must contain exactly contractgraph_qa, proofpath, liminaldb, rinse and ls")
    return subjects


def _validate_lanes(value: object) -> None:
    lanes = _object(value, "lanes")
    _exact_keys(lanes, {"evidence", "reflection", "authority"}, "lanes")
    for name in ("evidence", "reflection", "authority"):
        lane = _object(lanes[name], f"lanes.{name}")
        _exact_keys(lane, {"authority_effect", "may_authorize", "required_record"}, f"lanes.{name}")
        _text(lane["authority_effect"], f"lanes.{name}.authority_effect")
        _text(lane["required_record"], f"lanes.{name}.required_record")
        _bool(lane["may_authorize"], f"lanes.{name}.may_authorize")
    if lanes["evidence"]["may_authorize"] or lanes["reflection"]["may_authorize"]:
        _fail("evidence and reflection lanes must not authorize")
    if lanes["evidence"]["authority_effect"] != "NONE":
        _fail("evidence lane must have authority_effect NONE")
    if lanes["reflection"]["authority_effect"] != "NONE":
        _fail("reflection lane must have authority_effect NONE")
    if not lanes["authority"]["may_authorize"]:
        _fail("authority lane must remain the only potentially authorizing lane")


def _validate_artifacts(
    value: object,
    subjects: Mapping[str, Mapping[str, Any]],
    collection: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    artifacts: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    digests: set[str] = set()
    required = {
        "artifact_id",
        "path",
        "bytes",
        "sha256",
        "source_revision",
        "component",
        "role",
        "lane",
        "content_type",
        "origin",
        "trust_domain",
        "valid_time",
        "transaction_time",
        "collected_at",
    }
    for index, raw in enumerate(_list(value, "artifacts")):
        item = _object(raw, f"artifacts[{index}]")
        _exact_keys(item, required, f"artifacts[{index}]")
        artifact_id = _safe_id(item["artifact_id"], f"artifacts[{index}].artifact_id")
        if artifact_id in artifacts:
            _fail(f"duplicate artifact id: {artifact_id}")
        path = _safe_relative_path(item["path"], f"artifacts[{index}].path")
        if path in paths:
            _fail(f"duplicate artifact path: {path}")
        paths.add(path)
        digest = _sha64(item["sha256"], f"artifacts[{index}].sha256")
        if digest in digests:
            _fail(f"duplicate artifact SHA-256: {digest}")
        digests.add(digest)
        if not isinstance(item["bytes"], int) or isinstance(item["bytes"], bool) or item["bytes"] < 0:
            _fail(f"artifacts[{index}].bytes must be a non-negative integer")
        component = _safe_id(item["component"], f"artifacts[{index}].component")
        if component not in subjects:
            _fail(f"artifact component is not declared: {component}")
        if _sha40(item["source_revision"], f"artifacts[{index}].source_revision") != subjects[component]["head_sha"]:
            _fail(f"artifact source_revision does not match subject for {component}")
        lane = _text(item["lane"], f"artifacts[{index}].lane")
        if lane not in {"authority", "evidence", "reflection"}:
            _fail(f"unsupported artifact lane: {lane}")
        for field, expected in {
            "content_type": "application/json",
            "origin": "bounded-fixture",
            "trust_domain": "fixture",
        }.items():
            if _text(item[field], f"artifacts[{index}].{field}") != expected:
                _fail(f"artifacts[{index}].{field} has an unsupported value")
        for field in ("valid_time", "transaction_time", "collected_at"):
            if _timestamp(item[field], f"artifacts[{index}].{field}") != collection["collected_at"]:
                _fail(f"artifacts[{index}].{field} must equal collection.collected_at")
        item["path"] = path
        artifacts[artifact_id] = item
    if not artifacts:
        _fail("artifacts must not be empty")
    return artifacts, paths


def _validate_record(artifact_id: str, item: Mapping[str, Any], raw: bytes) -> dict[str, Any]:
    lane = item["lane"]
    if lane == "evidence":
        required = {
            "authority_effect", "decision", "evidence_integrity", "execution_authorized",
            "external_effects_authorized", "lane", "logical_operation_id", "mutation_authorized",
            "record_id", "role", "schema",
        }
    elif lane == "reflection":
        required = {
            "authority_effect", "execution_authorized", "external_effects_authorized", "lane",
            "logical_operation_id", "mutation_authorized", "record_id", "reflection_only", "role",
            "schema", "source_mutated",
        }
    elif lane == "authority":
        required = {
            "approval_ref", "authority_effect", "decision", "execution_authorized",
            "explicit_authority_record", "external_effects_authorized", "lane", "logical_operation_id",
            "mutation_authorized", "reason", "record_id", "role", "schema",
        }
    else:
        _fail(f"unsupported record lane for {artifact_id}: {lane}")
    _exact_keys(item, required, f"record {artifact_id}")
    if _safe_id(item["record_id"], f"record {artifact_id}.record_id") != artifact_id + "-001":
        _fail(f"record id is not bound to artifact {artifact_id}")
    if _text(item["logical_operation_id"], f"record {artifact_id}.logical_operation_id") != "neo-resonance-system-007-001":
        _fail(f"record {artifact_id} has the wrong logical operation")
    if _text(item["lane"], f"record {artifact_id}.lane") != lane:
        _fail(f"record {artifact_id} lane mismatch")
    for field in ("execution_authorized", "external_effects_authorized", "mutation_authorized"):
        if _bool(item[field], f"record {artifact_id}.{field}"):
            _fail(f"record {artifact_id} escalates {field}")
    if lane == "evidence":
        if _text(item["authority_effect"], f"record {artifact_id}.authority_effect") != "NONE":
            _fail("evidence cannot carry an authority effect")
        if _text(item["decision"], f"record {artifact_id}.decision") != "PASS":
            _fail("evidence control must be PASS")
        if _text(item["evidence_integrity"], f"record {artifact_id}.evidence_integrity") != "RECOMPUTABLE":
            _fail("evidence control must be recomputable")
    elif lane == "reflection":
        if _text(item["authority_effect"], f"record {artifact_id}.authority_effect") != "NONE":
            _fail("reflection cannot carry an authority effect")
        if _bool(item["reflection_only"], f"record {artifact_id}.reflection_only") is not True:
            _fail("reflection record must be reflection_only")
        if _bool(item["source_mutated"], f"record {artifact_id}.source_mutated"):
            _fail("reflection record must not mutate source")
    else:
        if _bool(item["explicit_authority_record"], f"record {artifact_id}.explicit_authority_record") is not True:
            _fail("authority lane requires an explicit authority record")
        if _text(item["decision"], f"record {artifact_id}.decision") != "HOLD":
            _fail("bounded authority control must remain HOLD")
        if item["approval_ref"] is not None:
            _fail("bounded authority control must not contain an approval reference")
        if _text(item["reason"], f"record {artifact_id}.reason") != "NO_CURRENT_AUTHORIZATION":
            _fail("bounded authority control has an unsupported reason")
    return {"artifact_id": artifact_id, "lane": lane, "raw_sha256": hashlib.sha256(raw).hexdigest()}


def _scan_bundle(root: Path) -> set[str]:
    if not root.exists() or not root.is_dir() or root.is_symlink():
        _fail("bundle root must be a real directory")
    actual: set[str] = set()
    for entry in root.rglob("*"):
        if entry.is_symlink():
            _fail(f"symlink is not allowed in bundle: {entry}")
        if entry.is_file():
            actual.add(entry.relative_to(root).as_posix())
    return actual


def _verify_files(root: Path, artifacts: Mapping[str, Mapping[str, Any]], declared_paths: set[str]) -> dict[str, Any]:
    actual_paths = _scan_bundle(root)
    if actual_paths != declared_paths:
        missing = sorted(declared_paths - actual_paths)
        unlisted = sorted(actual_paths - declared_paths)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unlisted:
            details.append("unlisted=" + ",".join(unlisted))
        _fail("bundle membership mismatch: " + "; ".join(details))
    records: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for artifact_id, artifact in artifacts.items():
        path = root / Path(*PurePosixPath(artifact["path"]).parts)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            _fail(f"declared artifact is missing or unreadable: {artifact['path']}: {exc}")
        if len(raw) != artifact["bytes"]:
            _fail(f"byte-size mismatch for {artifact['path']}")
        if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
            _fail(f"SHA-256 mismatch for {artifact['path']}")
        record, _ = _load_json(path, f"artifact {artifact_id}")
        records[artifact_id] = _validate_record(artifact_id, record, raw)
        total_bytes += len(raw)
    return {"records": records, "total_bytes": total_bytes}


def _evaluate_case(case: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]) -> tuple[str, str]:
    transition = case["attempted_transition"]
    inputs = case["input_artifact_ids"]
    input_lanes = {records[artifact_id]["lane"] for artifact_id in inputs}
    if transition == "EVIDENCE_TO_EXECUTION":
        return "BLOCK", "EVIDENCE_NOT_AUTHORITY"
    if transition == "REFLECTION_TO_EXECUTION":
        return "BLOCK", "REFLECTION_NOT_AUTHORITY"
    if transition == "INFER_AUTHORITY_FROM_PASS":
        if input_lanes <= {"evidence", "reflection"}:
            return "BLOCK", "EXPLICIT_AUTHORITY_RECORD_REQUIRED"
        return "BLOCK", "UNEXPECTED_AUTHORITY_INPUT"
    if transition == "HOLD_TO_EXECUTION":
        if input_lanes == {"authority"}:
            return "HOLD", "AUTHORITY_REVALIDATION_REQUIRED"
        return "BLOCK", "AUTHORITY_LANE_REQUIRED"
    return "BLOCK", "UNKNOWN_TRANSITION"


def _validate_cases(value: object, records: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    cases = _list(value, "cases")
    expected_ids = {
        "EVIDENCE_PASS_NOT_AUTHORITY",
        "REFLECTION_PASS_NOT_AUTHORITY",
        "PASS_CANNOT_INFER_AUTHORITY",
        "AUTHORITY_HOLD_STOPS_EXECUTION",
    }
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    required = {"case_id", "lane", "attempted_transition", "input_artifact_ids", "expected_decision", "expected_reason", "side_effect_executed"}
    for index, raw in enumerate(cases):
        case = _object(raw, f"cases[{index}]")
        _exact_keys(case, required, f"cases[{index}]")
        case_id = _safe_id(case["case_id"], f"cases[{index}].case_id")
        if case_id in seen:
            _fail(f"duplicate case id: {case_id}")
        seen.add(case_id)
        lane = _text(case["lane"], f"cases[{index}].lane")
        if lane not in {"evidence", "reflection", "verification", "authority"}:
            _fail(f"unsupported case lane: {lane}")
        inputs = _list(case["input_artifact_ids"], f"cases[{index}].input_artifact_ids")
        if not inputs:
            _fail(f"cases[{index}] must have input artifacts")
        input_ids = [_safe_id(item, f"cases[{index}].input_artifact_ids[]") for item in inputs]
        if any(item not in records for item in input_ids):
            _fail(f"case {case_id} references an unknown artifact")
        expected_decision = _text(case["expected_decision"], f"cases[{index}].expected_decision")
        if expected_decision not in {"BLOCK", "HOLD"}:
            _fail(f"case {case_id} has an unsafe expected decision")
        expected_reason = _safe_id(case["expected_reason"], f"cases[{index}].expected_reason")
        if _bool(case["side_effect_executed"], f"cases[{index}].side_effect_executed"):
            _fail(f"case {case_id} marks a side effect")
        case_copy = dict(case)
        case_copy["input_artifact_ids"] = input_ids
        observed_decision, observed_reason = _evaluate_case(case_copy, records)
        if (observed_decision, observed_reason) != (expected_decision, expected_reason):
            _fail(f"case {case_id} expected {expected_decision}/{expected_reason} but evaluated {observed_decision}/{observed_reason}")
        results.append({
            "case_id": case_id,
            "observed_decision": observed_decision,
            "reason_code": observed_reason,
            "authorization_granted": False,
            "side_effect_executed": False,
        })
    if seen != expected_ids:
        _fail("cases must cover exactly the four P1-3 escalation controls")
    return results


def _validate_replay(value: object, cases: list[Mapping[str, Any]], records: Mapping[str, Mapping[str, Any]]) -> None:
    replay = _object(value, "replay")
    _exact_keys(replay, {"trace_id", "mode", "expected_result", "replayable", "side_effects_executed", "steps"}, "replay")
    _safe_id(replay["trace_id"], "replay.trace_id")
    if _text(replay["mode"], "replay.mode") != "deterministic_read_only":
        _fail("replay.mode must be deterministic_read_only")
    if _text(replay["expected_result"], "replay.expected_result") != "SAME_RESULT":
        _fail("replay.expected_result must be SAME_RESULT")
    if _bool(replay["replayable"], "replay.replayable") is not True or _bool(replay["side_effects_executed"], "replay.side_effects_executed"):
        _fail("replay must be replayable and side-effect free")
    case_map = {case["case_id"]: case for case in cases}
    steps = _list(replay["steps"], "replay.steps")
    if len(steps) != len(cases):
        _fail("replay must contain exactly one step per case")
    referenced: set[str] = set()
    for expected_sequence, raw in enumerate(steps, start=1):
        step = _object(raw, f"replay.steps[{expected_sequence - 1}]")
        _exact_keys(step, {"sequence", "case_id", "input_artifact_ids", "side_effect_executed"}, f"replay.steps[{expected_sequence - 1}]")
        if step["sequence"] != expected_sequence:
            _fail("replay sequences must be contiguous starting at 1")
        case_id = _safe_id(step["case_id"], f"replay.steps[{expected_sequence - 1}].case_id")
        if case_id not in case_map:
            _fail(f"replay references unknown case: {case_id}")
        input_ids = [_safe_id(item, f"replay.steps[{expected_sequence - 1}].input_artifact_ids[]") for item in _list(step["input_artifact_ids"], f"replay.steps[{expected_sequence - 1}].input_artifact_ids")]
        if input_ids != case_map[case_id]["input_artifact_ids"]:
            _fail(f"replay input references drift for case {case_id}")
        for artifact_id in input_ids:
            if artifact_id not in records:
                _fail(f"replay references unknown artifact: {artifact_id}")
            referenced.add(artifact_id)
        if _bool(step["side_effect_executed"], f"replay.steps[{expected_sequence - 1}].side_effect_executed"):
            _fail("replay steps must not execute side effects")
    if referenced != set(records):
        _fail("replay must reference every declared artifact")


def verify_boundary(
    manifest_path: Path,
    root: Path,
    *,
    checked_subject: str | None = None,
    expected_proofpath_subject: str | None = None,
) -> dict[str, Any]:
    manifest, raw_manifest = _load_json(manifest_path, "manifest")
    required = {"schema", "manifest_id", "bundle_root", "scope", "subjects", "artifacts", "lanes", "cases", "replay", "authority", "collection"}
    _exact_keys(manifest, required, "manifest")
    if _text(manifest["schema"], "manifest.schema") != SCHEMA:
        _fail("manifest.schema is unsupported")
    manifest_id = _safe_id(manifest["manifest_id"], "manifest.manifest_id")
    if _safe_relative_path(manifest["bundle_root"], "manifest.bundle_root") != "bundle":
        _fail("manifest.bundle_root must be exactly bundle")
    scope = _object(manifest["scope"], "scope")
    _exact_keys(scope, {"operation_id", "mode", "claim_limit"}, "scope")
    if _safe_id(scope["operation_id"], "scope.operation_id") != "neo-resonance-system-007-001" or _text(scope["mode"], "scope.mode") != "bounded_fixture":
        _fail("scope does not match bounded SYSTEM-007 fixture")
    _text(scope["claim_limit"], "scope.claim_limit")
    authority = _object(manifest["authority"], "authority")
    _exact_keys(authority, {"mode", "proposal_is_not_authorization", "execution_authorized", "external_effects_authorized", "mutation_authorized"}, "authority")
    if _text(authority["mode"], "authority.mode") != "advisory_only" or _bool(authority["proposal_is_not_authorization"], "authority.proposal_is_not_authorization") is not True:
        _fail("authority mode must be advisory and proposal-is-not-authorization")
    for field in ("execution_authorized", "external_effects_authorized", "mutation_authorized"):
        if _bool(authority[field], f"authority.{field}"):
            _fail(f"manifest authority escalates {field}")
    collection = _object(manifest["collection"], "collection")
    _exact_keys(collection, {"attempt_id", "started_at", "completed_at", "collected_at", "method", "environment"}, "collection")
    for field in ("started_at", "completed_at", "collected_at"):
        _timestamp(collection[field], f"collection.{field}")
    if collection["started_at"] > collection["completed_at"] or collection["completed_at"] != collection["collected_at"]:
        _fail("collection timestamps are not ordered")
    _safe_id(collection["attempt_id"], "collection.attempt_id")
    _text(collection["method"], "collection.method")
    _text(collection["environment"], "collection.environment")
    subjects = _validate_subjects(manifest["subjects"])
    if checked_subject is not None:
        checked_subject = _sha40(checked_subject, "checked_subject")
        if subjects["contractgraph_qa"]["head_sha"] != checked_subject:
            _fail("checked_subject does not match ContractGraph-QA subject")
    if expected_proofpath_subject is not None:
        expected_proofpath_subject = _sha40(expected_proofpath_subject, "expected_proofpath_subject")
        if subjects["proofpath"]["head_sha"] != expected_proofpath_subject:
            _fail("ProofPath subject does not match expected subject")
    _validate_lanes(manifest["lanes"])
    artifacts, declared_paths = _validate_artifacts(manifest["artifacts"], subjects, collection)
    file_result = _verify_files(root, artifacts, declared_paths)
    cases = _list(manifest["cases"], "cases")
    case_results = _validate_cases(cases, file_result["records"])
    _validate_replay(manifest["replay"], cases, file_result["records"])
    blocked = sum(result["observed_decision"] == "BLOCK" for result in case_results)
    held = sum(result["observed_decision"] == "HOLD" for result in case_results)
    return {
        "schema": RESULT_SCHEMA,
        "decision": "PASS",
        "manifest_id": manifest_id,
        "manifest_sha256": "sha256:" + hashlib.sha256(raw_manifest).hexdigest(),
        "checked_subject": checked_subject,
        "proofpath_subject": subjects["proofpath"]["head_sha"],
        "subject_count": len(subjects),
        "artifact_count": len(artifacts),
        "member_count": len(artifacts),
        "total_bytes": file_result["total_bytes"],
        "case_count": len(case_results),
        "blocked_cases": blocked,
        "hold_cases": held,
        "executed_cases": 0,
        "evidence_cannot_authorize": True,
        "reflection_cannot_authorize": True,
        "explicit_authority_required": True,
        "replayable": True,
        "replay_stable": True,
        "side_effects_executed": False,
        "case_results": case_results,
        "authority": {
            "execution_authorized": False,
            "external_effects_authorized": False,
            "mutation_authorized": False,
        },
        "claim_limit": scope["claim_limit"],
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="verify the P1-3 boundary fixture")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--checked-subject")
    verify_parser.add_argument("--expected-proofpath-subject")
    verify_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_boundary(
            args.manifest,
            args.root,
            checked_subject=args.checked_subject,
            expected_proofpath_subject=args.expected_proofpath_subject,
        )
    except BoundaryError as exc:
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
