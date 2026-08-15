from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable

CANONICAL_ROUTE = ("ProofPath", "CML", "LiminalDB", "RINSE", "ContractGraph-QA")
RESONANCE_ROUTE = ("intent", "proofpath", "cml", "liminaldb", "rinse", "contractgraph_qa")


class IndependentReplayError(ValueError):
    """Raised when independent cross-repository replay cannot prove the subject."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_object(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def resolve_occurrence(
    occurrences: Iterable[dict[str, object]],
    *,
    decision_ref: str,
    cites_event_id: str | None,
) -> dict[str, object]:
    candidates = [record for record in occurrences if record.get("decision_ref") == decision_ref]
    if cites_event_id:
        candidates = [record for record in candidates if record.get("cites_event_id") == cites_event_id]
    if not candidates:
        raise IndependentReplayError("OCCURRENCE_NOT_FOUND")
    if len(candidates) > 1:
        raise IndependentReplayError("OCCURRENCE_AMBIGUOUS")
    return candidates[0]


def occurrence_envelope(record: dict[str, object]) -> dict[str, object]:
    required = (
        "decision_ref",
        "cites_event_id",
        "action_digest",
        "authority_revision",
        "issued_at_epoch",
        "expires_at_epoch",
        "revoked",
    )
    missing = [name for name in required if name not in record]
    if missing:
        raise IndependentReplayError(f"occurrence missing fields: {', '.join(missing)}")
    if not all(record[name] for name in ("decision_ref", "cites_event_id", "action_digest", "authority_revision")):
        raise IndependentReplayError("occurrence identity fields must be non-empty")
    issued = record["issued_at_epoch"]
    expires = record["expires_at_epoch"]
    if not isinstance(issued, int) or not isinstance(expires, int) or issued < 0 or expires < issued:
        raise IndependentReplayError("invalid occurrence validity interval")
    if not isinstance(record["revoked"], bool):
        raise IndependentReplayError("revoked must be boolean")
    return {
        "schema": "cgqa.authorization-occurrence.v0.1",
        **{name: record[name] for name in required},
    }


def compute_route_fingerprint(record: dict[str, object], route: Iterable[str]) -> str:
    route_tuple = tuple(route)
    if route_tuple != CANONICAL_ROUTE:
        raise IndependentReplayError("adapter route order changed")
    envelope = occurrence_envelope(record)
    occurrence_fingerprint = sha256_object(envelope)
    return sha256_object(
        {
            "schema": "cgqa.occurrence-route.v0.1",
            "route": list(route_tuple),
            "occurrence_fingerprint": occurrence_fingerprint,
            "hop_fingerprints": [occurrence_fingerprint] * len(route_tuple),
        }
    )


def expected_receipt(
    record: dict[str, object],
    request: dict[str, object],
    route_fingerprint: str,
) -> dict[str, object]:
    if request.get("action_digest") != record.get("action_digest"):
        raise IndependentReplayError("ACTION_MISMATCH")
    if record.get("revoked") is True:
        raise IndependentReplayError("OCCURRENCE_REVOKED")
    consumed_at = request.get("consumed_at_epoch")
    if not isinstance(consumed_at, int) or consumed_at < 0:
        raise IndependentReplayError("invalid consumed_at_epoch")
    if consumed_at < int(record["issued_at_epoch"]):
        raise IndependentReplayError("OCCURRENCE_NOT_YET_VALID")
    if consumed_at > int(record["expires_at_epoch"]):
        raise IndependentReplayError("OCCURRENCE_EXPIRED")
    for field in ("consumer_id", "request_id"):
        if not request.get(field):
            raise IndependentReplayError(f"{field} must be non-empty")
    payload = {
        "schema": "cgqa.consumption-receipt.v0.1",
        "decision_ref": record["decision_ref"],
        "cites_event_id": record["cites_event_id"],
        "consumer_id": request["consumer_id"],
        "action_digest": record["action_digest"],
        "authority_revision": record["authority_revision"],
        "route_fingerprint": route_fingerprint,
        "request_id": request["request_id"],
        "consumed_at_epoch": consumed_at,
        "result": "CONSUMED",
    }
    return {**payload, "receipt_digest": sha256_object(payload)}


def verify_observed_receipt(observed: dict[str, object], expected: dict[str, object]) -> None:
    if observed != expected:
        raise IndependentReplayError("observed ConsumptionReceipt does not match independent reconstruction")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise IndependentReplayError(f"git {' '.join(args)} failed for {root}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def verify_git_subject(root: Path, subject: dict[str, str]) -> dict[str, str]:
    revision = subject["revision"]
    path = subject["path"]
    actual_head = _git(root, "rev-parse", "HEAD")
    if actual_head != revision:
        raise IndependentReplayError(
            f"{subject['component']}: revision mismatch: expected {revision}, got {actual_head}"
        )
    file_path = root / path
    if not file_path.is_file():
        raise IndependentReplayError(f"{subject['component']}: missing subject path {path}")
    committed_blob = _git(root, "rev-parse", f"{revision}:{path}")
    worktree_blob = _git(root, "hash-object", path)
    if committed_blob != worktree_blob:
        raise IndependentReplayError(f"{subject['component']}: worktree subject differs from pinned revision")
    return {
        "component": subject["component"],
        "repository": subject["repository"],
        "revision": revision,
        "path": path,
        "git_blob": committed_blob,
        "sha256": sha256_bytes(file_path.read_bytes()),
    }


def build_subject_fingerprint(subjects: Iterable[dict[str, str]]) -> str:
    records = list(subjects)
    components = [record["component"] for record in records]
    if len(components) != len(set(components)):
        raise IndependentReplayError("duplicate component in cross-repository subject set")
    normalized = sorted(records, key=lambda item: item["component"])
    return sha256_object({"schema": "cgqa.cross-repo-subject-set.v0.1", "subjects": normalized})


def verify_resonance_fixture(fixture: dict[str, object], manifest: dict[str, object]) -> None:
    resolved = fixture.get("resolved_target")
    if not isinstance(resolved, dict) or tuple(resolved.get("route", ())) != RESONANCE_ROUTE:
        raise IndependentReplayError("RESONANCE route does not match the canonical SYSTEM-007 route")
    boundary = fixture.get("authority_boundary")
    if not isinstance(boundary, dict) or any(
        boundary.get(name) is not False
        for name in ("execution_authorized", "mutation_authorized", "external_effects_authorized")
    ):
        raise IndependentReplayError("RESONANCE authority boundary is not fail-closed")

    manifest_revisions = {
        str(item["component"]): str(item["revision"])
        for item in manifest["subjects"]
        if item["component"] in {"proofpath", "cml", "liminaldb", "rinse"}
    }
    bindings = {
        str(item["component"]): str(item["revision"])
        for item in fixture.get("component_bindings", [])
        if isinstance(item, dict) and item.get("component") in manifest_revisions
    }
    if bindings != manifest_revisions:
        raise IndependentReplayError("RESONANCE component bindings disagree with pinned external revisions")


def replay(
    *,
    manifest_path: Path,
    occurrence_path: Path,
    checkout_root: Path,
    verifier_root: Path,
    verifier_revision: str,
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw = json.loads(occurrence_path.read_text(encoding="utf-8"))

    if manifest.get("schema") != "cgqa.global-p1-7-subject-manifest.v0.1":
        raise IndependentReplayError("unsupported P1-7 subject manifest schema")
    if raw.get("schema") != "cgqa.global-p1-7-occurrence-consumption.v0.1":
        raise IndependentReplayError("unsupported P1-7 occurrence fixture schema")
    scope = raw.get("scope")
    if not isinstance(scope, dict) or scope.get("side_effects_executed") is not False or scope.get("production_ledger_mutated") is not False:
        raise IndependentReplayError("P1-7 fixture must remain conformance-only and side-effect free")

    route = tuple(raw.get("route", ()))
    if route != CANONICAL_ROUTE:
        raise IndependentReplayError("adapter route order changed")

    request = raw.get("request")
    occurrences = raw.get("authorization_occurrences")
    observed = raw.get("observed_receipt")
    if not isinstance(request, dict) or not isinstance(occurrences, list) or not isinstance(observed, dict):
        raise IndependentReplayError("invalid P1-7 occurrence fixture shape")

    decision_ref = request.get("decision_ref")
    cites_event_id = request.get("cites_event_id")
    if not isinstance(decision_ref, str) or not decision_ref:
        raise IndependentReplayError("request decision_ref must be non-empty")
    if cites_event_id is not None and not isinstance(cites_event_id, str):
        raise IndependentReplayError("request cites_event_id must be a string or null")

    selected = resolve_occurrence(occurrences, decision_ref=decision_ref, cites_event_id=cites_event_id)
    route_fingerprint = compute_route_fingerprint(selected, route)
    receipt = expected_receipt(selected, request, route_fingerprint)
    verify_observed_receipt(observed, receipt)

    verified_subjects: list[dict[str, str]] = []
    resonance_fixture: dict[str, object] | None = None
    for item in manifest["subjects"]:
        subject = {key: str(item[key]) for key in ("component", "repository", "revision", "path", "checkout_dir")}
        root = checkout_root / subject["checkout_dir"]
        verified_subjects.append(verify_git_subject(root, subject))
        if subject["component"] == "resonance":
            resonance_fixture = json.loads((root / subject["path"]).read_text(encoding="utf-8"))

    if resonance_fixture is None:
        raise IndependentReplayError("RESONANCE subject missing from manifest")
    verify_resonance_fixture(resonance_fixture, manifest)

    self_subject = {
        "component": "contractgraph_qa",
        "repository": "safal207/ContractGraph-QA",
        "revision": verifier_revision,
        "path": "tools/independent_cross_repo_replay.py",
    }
    verified_subjects.append(verify_git_subject(verifier_root, self_subject))
    subject_fingerprint = build_subject_fingerprint(verified_subjects)

    witness_payload = {
        "schema": "cgqa.independent-cross-repo-replay.v0.1",
        "decision": "PASS",
        "decision_ref": selected["decision_ref"],
        "cites_event_id": selected["cites_event_id"],
        "route_fingerprint": route_fingerprint,
        "receipt_digest": receipt["receipt_digest"],
        "cross_repo_subject_fingerprint": subject_fingerprint,
        "verifier_revision": verifier_revision,
        "verified_subjects": sorted(verified_subjects, key=lambda item: item["component"]),
        "side_effects_executed": False,
        "production_ledger_mutated": False,
    }
    return {
        **witness_payload,
        "witness_digest": sha256_object(witness_payload),
        "reconstructed_receipt": receipt,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently replay exact occurrence consumption across pinned Neo Resonance repositories"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--occurrence", type=Path, required=True)
    parser.add_argument("--checkout-root", type=Path, required=True)
    parser.add_argument("--verifier-root", type=Path, default=Path("."))
    parser.add_argument("--verifier-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = replay(
            manifest_path=args.manifest,
            occurrence_path=args.occurrence,
            checkout_root=args.checkout_root,
            verifier_root=args.verifier_root,
            verifier_revision=args.verifier_revision,
        )
    except (IndependentReplayError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"decision": "FAIL", "error": str(exc)}, sort_keys=True))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
