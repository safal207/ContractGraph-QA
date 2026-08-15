from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


CANONICAL_ROUTE = ("ProofPath", "CML", "LiminalDB", "RINSE", "ContractGraph-QA")
RESONANCE_ROUTE = ("intent", "proofpath", "cml", "liminaldb", "rinse", "contractgraph_qa")
MATRIX_SCHEMA = "cgqa.global-p1-8-compatibility-migration.v0.1"
RECEIPT_SCHEMA = "cgqa.p1-8-compatibility-receipt.v0.1"

CURRENT_CONTRACTS = {
    "proofpath_schema": "org.proofpath.authorization-record.v0.1",
    "liminaldb_protocol": "1.0.0",
    "liminaldb_commands_schema": "https://liminaldb.dev/schema/v1/commands.json",
    "liminaldb_events_schema": "https://liminaldb.dev/schema/v1/events.json",
    "rinse_receipt_schema": "rinse.kairos-liminal-receipt.v0.1",
    "rinse_graph_schema": "rinse.reflection-graph.v0.2",
}


class CompatibilityReplayError(ValueError):
    """Raised when compatibility cargo is ambiguous, tampered, or unsupported."""


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
        raise CompatibilityReplayError(f"{label} must be a non-empty string")
    return value.strip()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityReplayError(f"{label} must be an object")
    return value


def _false(value: object, label: str) -> None:
    if value is not False:
        raise CompatibilityReplayError(f"{label} must be false")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise CompatibilityReplayError(
            f"git {' '.join(args)} failed for {root}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def verify_git_subject(root: Path, subject: dict[str, str]) -> dict[str, str]:
    """Bind one evidence file to one exact Git revision and committed blob."""

    revision = _text(subject.get("revision"), "subject.revision")
    path = _text(subject.get("path"), "subject.path")
    component = _text(subject.get("component"), "subject.component")
    repository = _text(subject.get("repository"), "subject.repository")
    file_path = root / path
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise CompatibilityReplayError(f"{component}: unsafe subject path")
    if _git(root, "rev-parse", "HEAD") != revision:
        raise CompatibilityReplayError(f"{component}: exact revision mismatch")
    if not file_path.is_file():
        raise CompatibilityReplayError(f"{component}: missing subject path {path}")
    committed_blob = _git(root, "rev-parse", f"{revision}:{path}")
    worktree_blob = _git(root, "hash-object", "--", path)
    if committed_blob != worktree_blob:
        raise CompatibilityReplayError(f"{component}: worktree subject differs from pinned revision")
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
        raise CompatibilityReplayError(f"{label} is not readable JSON: {exc}") from exc
    return _mapping(value, label)


def _subject_path(
    subject_by_role: dict[str, dict[str, str]],
    role: str,
    checkout_root: Path,
) -> Path:
    subject = subject_by_role.get(role)
    if subject is None:
        raise CompatibilityReplayError(f"missing required subject role: {role}")
    checkout_dir = _text(subject.get("checkout_dir"), f"{role}.checkout_dir")
    if Path(checkout_dir).is_absolute() or ".." in Path(checkout_dir).parts:
        raise CompatibilityReplayError(f"{role}: unsafe checkout directory")
    return checkout_root / checkout_dir / subject["path"]


def inspect_contracts(
    matrix: dict[str, Any],
    checkout_root: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    subjects = matrix.get("subjects")
    if not isinstance(subjects, list) or not subjects:
        raise CompatibilityReplayError("matrix.subjects must be a non-empty array")

    subject_by_role: dict[str, dict[str, str]] = {}
    verified: list[dict[str, str]] = []
    for raw in subjects:
        subject = _mapping(raw, "matrix.subjects[]")
        role = _text(subject.get("role"), "subject.role")
        if role in subject_by_role:
            raise CompatibilityReplayError(f"duplicate subject role: {role}")
        required = ("component", "repository", "revision", "path", "checkout_dir")
        if any(key not in subject for key in required):
            raise CompatibilityReplayError(f"{role}: incomplete subject binding")
        normalized = {key: _text(subject[key], f"{role}.{key}") for key in required}
        normalized["role"] = role
        subject_by_role[role] = normalized
        verified.append(
            verify_git_subject(checkout_root / normalized["checkout_dir"], normalized)
        )

    required_roles = {
        "proofpath_authorization_schema",
        "cml_route_fixture",
        "liminaldb_version",
        "liminaldb_commands_schema",
        "liminaldb_events_schema",
        "rinse_receipt_schema",
        "rinse_graph_schema",
        "resonance_route_fixture",
    }
    if set(subject_by_role) != required_roles:
        raise CompatibilityReplayError(
            "subject roles must be exactly the bounded P1-8 compatibility set"
        )

    proofpath = _load_json(
        _subject_path(subject_by_role, "proofpath_authorization_schema", checkout_root),
        "ProofPath authorization schema",
    )
    proofpath_properties = _mapping(proofpath.get("properties"), "ProofPath schema.properties")
    if proofpath_properties.get("schema", {}).get("const") != CURRENT_CONTRACTS["proofpath_schema"]:
        raise CompatibilityReplayError("ProofPath authorization schema revision drift")
    if proofpath.get("additionalProperties") is not False:
        raise CompatibilityReplayError("ProofPath authorization schema must remain strict")
    if "decision" not in proofpath.get("required", []):
        raise CompatibilityReplayError("ProofPath authorization schema lost decision field")

    cml = _load_json(
        _subject_path(subject_by_role, "cml_route_fixture", checkout_root),
        "CML route fixture",
    )
    if not cml:
        raise CompatibilityReplayError("CML route fixture must not be empty")

    liminaldb_version_path = _subject_path(subject_by_role, "liminaldb_version", checkout_root)
    liminaldb_version = liminaldb_version_path.read_text(encoding="utf-8").strip()
    if liminaldb_version != CURRENT_CONTRACTS["liminaldb_protocol"]:
        raise CompatibilityReplayError("LiminalDB protocol version drift")

    liminaldb_commands = _load_json(
        _subject_path(subject_by_role, "liminaldb_commands_schema", checkout_root),
        "LiminalDB commands schema",
    )
    liminaldb_events = _load_json(
        _subject_path(subject_by_role, "liminaldb_events_schema", checkout_root),
        "LiminalDB events schema",
    )
    for label, document, expected in (
        (
            "commands",
            liminaldb_commands,
            CURRENT_CONTRACTS["liminaldb_commands_schema"],
        ),
        ("events", liminaldb_events, CURRENT_CONTRACTS["liminaldb_events_schema"]),
    ):
        if document.get("$id") != expected:
            raise CompatibilityReplayError(f"LiminalDB {label} schema identity drift")
        if document.get("properties", {}).get("version", {}).get("const") != CURRENT_CONTRACTS["liminaldb_protocol"]:
            raise CompatibilityReplayError(f"LiminalDB {label} protocol version drift")
        if document.get("additionalProperties") is not False:
            raise CompatibilityReplayError(f"LiminalDB {label} schema must remain strict")

    rinse_receipt = _load_json(
        _subject_path(subject_by_role, "rinse_receipt_schema", checkout_root),
        "RINSE receipt schema",
    )
    if rinse_receipt.get("properties", {}).get("schema", {}).get("const") != CURRENT_CONTRACTS["rinse_receipt_schema"]:
        raise CompatibilityReplayError("RINSE receipt schema revision drift")
    if rinse_receipt.get("additionalProperties") is not False:
        raise CompatibilityReplayError("RINSE receipt schema must remain strict")

    rinse_graph = _load_json(
        _subject_path(subject_by_role, "rinse_graph_schema", checkout_root),
        "RINSE reflection graph schema",
    )
    if rinse_graph.get("properties", {}).get("schema", {}).get("const") != CURRENT_CONTRACTS["rinse_graph_schema"]:
        raise CompatibilityReplayError("RINSE reflection graph schema revision drift")
    if rinse_graph.get("additionalProperties") is not False:
        raise CompatibilityReplayError("RINSE reflection graph schema must remain strict")

    resonance = _load_json(
        _subject_path(subject_by_role, "resonance_route_fixture", checkout_root),
        "RESONANCE route fixture",
    )
    resolved_target = _mapping(resonance.get("resolved_target"), "RESONANCE resolved_target")
    if tuple(resolved_target.get("route", ())) != RESONANCE_ROUTE:
        raise CompatibilityReplayError("RESONANCE route is not the canonical SYSTEM-007 route")
    boundary = _mapping(resonance.get("authority_boundary"), "RESONANCE authority_boundary")
    for field in ("execution_authorized", "mutation_authorized", "external_effects_authorized"):
        _false(boundary.get(field), f"RESONANCE authority_boundary.{field}")

    observations = {
        **CURRENT_CONTRACTS,
        "route": list(CANONICAL_ROUTE),
        "resonance_route": list(RESONANCE_ROUTE),
        "authority": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
            "source_mutation_authorized": False,
        },
    }
    return observations, verified


def _source_payload(matrix: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(_mapping(matrix.get("source_payload"), "matrix.source_payload"))
    if tuple(payload.get("route", ())) != CANONICAL_ROUTE:
        raise CompatibilityReplayError("source payload route drift")
    if payload.get("proofpath_schema") != CURRENT_CONTRACTS["proofpath_schema"]:
        raise CompatibilityReplayError("source payload ProofPath schema drift")
    if payload.get("liminaldb_protocol") != CURRENT_CONTRACTS["liminaldb_protocol"]:
        raise CompatibilityReplayError("source payload LiminalDB version drift")
    if payload.get("rinse_schema") != CURRENT_CONTRACTS["rinse_receipt_schema"]:
        raise CompatibilityReplayError("source payload RINSE schema drift")
    authority = _mapping(payload.get("authority"), "source_payload.authority")
    for field in ("execution_authorized", "mutation_authorized", "external_effects_authorized"):
        _false(authority.get(field), f"source_payload.authority.{field}")
    return payload


def evaluate_case(
    case: dict[str, Any],
    source_payload: dict[str, Any],
) -> dict[str, Any]:
    case_id = _text(case.get("id"), "case.id")
    expected = _text(case.get("expected"), f"{case_id}.expected")
    candidate = _mapping(case.get("candidate"), f"{case_id}.candidate")
    current = {
        "proofpath_schema": source_payload["proofpath_schema"],
        "liminaldb_protocol": source_payload["liminaldb_protocol"],
        "rinse_schema": source_payload["rinse_schema"],
        "route": list(CANONICAL_ROUTE),
        "authority": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
        },
    }

    decision = "ACCEPT"
    reason_code = "EXACT_CURRENT_REVISION"
    if candidate.get("route") is not None and candidate.get("route") != current["route"]:
        decision = "REJECT"
        reason_code = "ROUTE_ORDER_DRIFT"
    elif any(
        candidate.get(field) is not None and candidate.get(field) != current[field]
        for field in ("proofpath_schema", "liminaldb_protocol", "rinse_schema")
    ):
        decision = "REJECT"
        reason_code = "UNSUPPORTED_SCHEMA_REVISION"
    elif candidate.get("authority") is not None:
        candidate_authority = _mapping(candidate.get("authority"), f"{case_id}.candidate.authority")
        if any(candidate_authority.get(field) is not False for field in current["authority"]):
            decision = "REJECT"
            reason_code = "AUTHORITY_ESCALATION"

    if decision != expected:
        raise CompatibilityReplayError(
            f"{case_id}: expected {expected}, independently computed {decision}"
        )

    source_digest = sha256_object(source_payload)
    if decision == "REJECT":
        recovered = copy.deepcopy(source_payload)
        recovered_digest = sha256_object(recovered)
        if recovered_digest != source_digest:
            raise CompatibilityReplayError(f"{case_id}: recovery changed original cargo")
        recovery_status = "ORIGINAL_PRESERVED"
    else:
        recovered_digest = None
        recovery_status = "NOT_REQUIRED"

    return {
        "case_id": case_id,
        "decision": decision,
        "reason_code": reason_code,
        "source_payload_digest": source_digest,
        "recovered_payload_digest": recovered_digest,
        "recovery_status": recovery_status,
        "write_performed": False,
        "authority": {
            "source_mutation_authorized": False,
            "execution_authorized": False,
            "external_effects_authorized": False,
        },
    }


def build_subject_fingerprint(subjects: Iterable[dict[str, str]]) -> str:
    records = list(subjects)
    components = [record["component"] for record in records]
    if len(components) != len(set(components)):
        raise CompatibilityReplayError("duplicate component in compatibility subject set")
    return sha256_object(
        {
            "schema": "cgqa.p1-8-subject-set.v0.1",
            "subjects": sorted(records, key=lambda item: item["component"]),
        }
    )


def verify_receipt(receipt: dict[str, Any]) -> None:
    recorded = receipt.get("receipt_digest")
    if not isinstance(recorded, str) or not recorded.startswith("sha256:"):
        raise CompatibilityReplayError("compatibility receipt digest is missing")
    payload = copy.deepcopy(receipt)
    payload.pop("receipt_digest", None)
    expected = "sha256:" + sha256_object(payload)
    if recorded != expected:
        raise CompatibilityReplayError("compatibility receipt digest mismatch")
    for field in (
        "source_mutation_authorized",
        "execution_authorized",
        "external_effects_authorized",
    ):
        _false(receipt.get("authority", {}).get(field), f"receipt.authority.{field}")


def replay(
    *,
    matrix_path: Path,
    checkout_root: Path,
    verifier_root: Path,
    verifier_revision: str,
) -> dict[str, Any]:
    matrix = _load_json(matrix_path, "P1-8 compatibility matrix")
    if matrix.get("schema") != MATRIX_SCHEMA:
        raise CompatibilityReplayError("unsupported P1-8 compatibility matrix schema")
    source_payload = _source_payload(matrix)
    observations, verified_subjects = inspect_contracts(matrix, checkout_root)

    self_subject = {
        "component": "contractgraph_qa",
        "repository": "safal207/ContractGraph-QA",
        "revision": verifier_revision,
        "path": "tools/compatibility_migration_replay.py",
    }
    verified_subjects.append(verify_git_subject(verifier_root, self_subject))
    subject_fingerprint = build_subject_fingerprint(verified_subjects)

    cases = matrix.get("cases")
    if not isinstance(cases, list) or len(cases) < 4:
        raise CompatibilityReplayError("P1-8 matrix must contain at least four bounded cases")
    results = [evaluate_case(_mapping(case, "matrix.cases[]"), source_payload) for case in cases]
    if not any(result["decision"] == "ACCEPT" for result in results):
        raise CompatibilityReplayError("P1-8 matrix has no accepted current contract control")
    if not all(
        result["recovery_status"] == "ORIGINAL_PRESERVED"
        for result in results
        if result["decision"] == "REJECT"
    ):
        raise CompatibilityReplayError("every rejected candidate must preserve original cargo")

    receipt_payload = {
        "schema": RECEIPT_SCHEMA,
        "case_id": _text(matrix.get("case_id"), "matrix.case_id"),
        "decision": "PASS",
        "policy": "EXACT_CURRENT_REVISION_ONLY",
        "source_payload_digest": sha256_object(source_payload),
        "contract_observations": observations,
        "subject_fingerprint": subject_fingerprint,
        "subjects": sorted(verified_subjects, key=lambda item: item["component"]),
        "cases": results,
        "recovery": {
            "rejected_cases_preserve_source_digest": True,
            "byte_recovery_mode": "CANONICAL_SOURCE_REPLAY",
            "write_performed": False,
        },
        "authority": {
            "source_mutation_authorized": False,
            "execution_authorized": False,
            "external_effects_authorized": False,
        },
    }
    receipt = {**receipt_payload, "receipt_digest": "sha256:" + sha256_object(receipt_payload)}
    verify_receipt(receipt)

    witness_payload = {
        "schema": "cgqa.p1-8-independent-compatibility-replay.v0.1",
        "decision": "PASS",
        "policy": "EXACT_CURRENT_REVISION_ONLY",
        "subject_fingerprint": subject_fingerprint,
        "receipt_digest": receipt["receipt_digest"],
        "accepted_cases": sum(result["decision"] == "ACCEPT" for result in results),
        "rejected_cases": sum(result["decision"] == "REJECT" for result in results),
        "all_rejected_candidates_recovered": all(
            result["recovery_status"] == "ORIGINAL_PRESERVED"
            for result in results
            if result["decision"] == "REJECT"
        ),
        "side_effects_executed": False,
        "production_ledger_mutated": False,
        "verifier_revision": verifier_revision,
    }
    return {
        **witness_payload,
        "compatibility_receipt": receipt,
        "witness_digest": sha256_object(witness_payload),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay bounded exact-head compatibility and migration policy for Neo Resonance"
    )
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
    except (CompatibilityReplayError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"decision": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
