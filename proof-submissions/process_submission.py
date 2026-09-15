#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_PROFILES = HERE / "profiles.v0.2.json"
SCHEMA_ID = "contractgraph.external-proof-submission.v0.2"
ADMITTED = "ADMITTED_BOUNDED"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
NAMESPACE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{1,63}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CLAIM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,191}$")


class PlatformIntegrityError(RuntimeError):
    pass


class SubmissionError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SubmissionError(f"expected JSON object: {path}")
    return data


def validate_submission(data: dict[str, Any]) -> None:
    required = {
        "schema",
        "submission_id",
        "submitted_by",
        "protocol_namespace",
        "verification_profile",
        "source",
        "requested_claims",
        "non_claims",
    }
    missing = sorted(required - set(data))
    extra = sorted(set(data) - required)
    if missing:
        raise SubmissionError(f"missing required fields: {missing}")
    if extra:
        raise SubmissionError(f"unknown top-level fields: {extra}")
    if data["schema"] != SCHEMA_ID:
        raise SubmissionError(f"unsupported schema: {data['schema']!r}")
    if not isinstance(data["submission_id"], str) or not ID_RE.fullmatch(data["submission_id"]):
        raise SubmissionError("invalid submission_id")
    submitted_by = data["submitted_by"]
    if not isinstance(submitted_by, dict) or set(submitted_by) != {"kind", "id"}:
        raise SubmissionError("submitted_by must contain exactly kind + id")
    if submitted_by["kind"] not in {"github", "organization", "person", "agent", "other"}:
        raise SubmissionError("unsupported submitted_by.kind")
    if not isinstance(submitted_by["id"], str) or not submitted_by["id"]:
        raise SubmissionError("submitted_by.id must be non-empty")
    if not isinstance(data["protocol_namespace"], str) or not NAMESPACE_RE.fullmatch(data["protocol_namespace"]):
        raise SubmissionError("invalid protocol_namespace")
    if not isinstance(data["verification_profile"], str) or not PROFILE_RE.fullmatch(data["verification_profile"]):
        raise SubmissionError("invalid verification_profile")

    source = data["source"]
    if not isinstance(source, dict):
        raise SubmissionError("source must be an object")
    source_keys = {"repository", "commit", "path", "sha256", "bytes"}
    if set(source) != source_keys:
        raise SubmissionError("source must contain exactly repository, commit, path, sha256, bytes")
    if not isinstance(source["repository"], str) or not REPO_RE.fullmatch(source["repository"]):
        raise SubmissionError("invalid source.repository")
    if not isinstance(source["commit"], str) or not COMMIT_RE.fullmatch(source["commit"]):
        raise SubmissionError("invalid source.commit")
    if not isinstance(source["path"], str) or not source["path"] or source["path"].startswith("/"):
        raise SubmissionError("invalid source.path")
    parts = Path(source["path"]).parts
    if ".." in parts:
        raise SubmissionError("source.path may not contain '..'")
    if not isinstance(source["sha256"], str) or not SHA256_RE.fullmatch(source["sha256"]):
        raise SubmissionError("invalid source.sha256")
    if not isinstance(source["bytes"], int) or isinstance(source["bytes"], bool) or source["bytes"] <= 0:
        raise SubmissionError("source.bytes must be a positive integer")

    claims = data["requested_claims"]
    if not isinstance(claims, list) or not claims:
        raise SubmissionError("requested_claims must be a non-empty list")
    if len(claims) != len(set(claims)):
        raise SubmissionError("requested_claims must be unique")
    for claim in claims:
        if not isinstance(claim, str) or not CLAIM_RE.fullmatch(claim):
            raise SubmissionError(f"invalid requested claim: {claim!r}")
    non_claims = data["non_claims"]
    if not isinstance(non_claims, list) or any(not isinstance(item, str) or not item for item in non_claims):
        raise SubmissionError("non_claims must be a list of non-empty strings")


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    if payload.get("schema") != "contractgraph.external-proof-profiles.v0.2":
        raise PlatformIntegrityError("unsupported trusted profile catalog schema")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise PlatformIntegrityError("trusted profile catalog has no profiles list")
    out: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict) or not isinstance(profile.get("id"), str):
            raise PlatformIntegrityError("malformed trusted profile")
        pid = profile["id"]
        if pid in out:
            raise PlatformIntegrityError(f"duplicate trusted profile: {pid}")
        out[pid] = profile
    return out


def make_decision(status: str, submission: dict[str, Any], **fields: Any) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "schema": "contractgraph.external-proof-admission-decision.v0.2",
        "submission_id": submission.get("submission_id"),
        "status": status,
        **fields,
    }
    canonical = json.dumps(decision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    decision["decision_digest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return decision


def write_decision(decision: dict[str, Any], path: str | None) -> None:
    encoded = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if path:
        Path(path).write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)


def profile_allowed_claims(profile: dict[str, Any]) -> dict[str, str]:
    allowed = profile.get("allowed_claims")
    if not isinstance(allowed, list):
        raise PlatformIntegrityError("profile allowed_claims is malformed")
    out: dict[str, str] = {}
    for row in allowed:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("text"), str):
            raise PlatformIntegrityError("profile allowed claim is malformed")
        if row["id"] in out:
            raise PlatformIntegrityError(f"duplicate allowed claim: {row['id']}")
        out[row["id"]] = row["text"]
    return out


def verify_trusted_verifier_pin(profile: dict[str, Any]) -> bytes:
    pin = profile.get("trusted_verifier")
    if not isinstance(pin, dict):
        raise PlatformIntegrityError("trusted_verifier pin is missing")
    commit = pin.get("merge_commit")
    path = pin.get("path")
    expected_blob = pin.get("blob_sha")
    if not all(isinstance(v, str) for v in (commit, path, expected_blob)):
        raise PlatformIntegrityError("trusted_verifier pin is malformed")
    try:
        actual_blob = subprocess.check_output(
            ["git", "rev-parse", f"{commit}:{path}"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise PlatformIntegrityError(f"trusted verifier artifact is unavailable: {exc.output.strip()}") from exc
    if actual_blob != expected_blob:
        raise PlatformIntegrityError(
            f"trusted verifier blob mismatch: expected {expected_blob}, got {actual_blob}"
        )
    try:
        return subprocess.check_output(
            ["git", "show", f"{commit}:{path}"],
            cwd=REPO_ROOT,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        raise PlatformIntegrityError(f"cannot read trusted verifier: {exc.output!r}") from exc


def source_matches_profile(source: dict[str, Any], profile: dict[str, Any]) -> bool:
    expected = profile.get("source_constraints")
    if not isinstance(expected, dict):
        raise PlatformIntegrityError("profile source_constraints is malformed")
    keys = {"repository", "commit", "path", "sha256", "bytes"}
    if set(expected) != keys:
        raise PlatformIntegrityError("profile source_constraints has unexpected fields")
    return all(source.get(key) == expected.get(key) for key in keys)


def materialize_source(source: dict[str, Any], destination: Path, local_override: str | None) -> None:
    if local_override:
        raw = Path(local_override).read_bytes()
        destination.write_bytes(raw)
        return
    url = (
        "https://raw.githubusercontent.com/"
        f"{source['repository']}/{source['commit']}/{source['path']}"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "ContractGraph-QA-proof-intake/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def check_source_integrity(path: Path, source: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    actual_bytes = path.stat().st_size
    actual_sha = sha256_file(path)
    return (
        actual_bytes == source["bytes"] and actual_sha == source["sha256"],
        {
            "expected_bytes": source["bytes"],
            "actual_bytes": actual_bytes,
            "expected_sha256": source["sha256"],
            "actual_sha256": actual_sha,
        },
    )


def run_trusted_verifier(verifier_bytes: bytes, evidence: Path) -> tuple[bool, dict[str, Any] | None, str]:
    with tempfile.TemporaryDirectory(prefix="cgqa-trusted-verifier-") as tmpdir:
        tmp = Path(tmpdir)
        script = tmp / "verifier.py"
        report_path = tmp / "verification.json"
        script.write_bytes(verifier_bytes)
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--evidence",
                str(evidence),
                "--write-report",
                str(report_path),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
        output = completed.stdout[-8000:]
        if completed.returncode != 0 or not report_path.exists():
            return False, None, output
        try:
            report = load_json(report_path)
        except Exception as exc:  # noqa: BLE001 - external verifier boundary
            return False, None, f"trusted verifier emitted unreadable report: {exc}\n{output}"
        return True, report, output


def process_submission(
    submission: dict[str, Any],
    profiles_path: Path,
    source_file: str | None = None,
) -> dict[str, Any]:
    try:
        validate_submission(submission)
    except SubmissionError as exc:
        return make_decision("REJECTED_SCHEMA", submission, reason=str(exc))

    profiles = load_profiles(profiles_path)
    profile = profiles.get(submission["verification_profile"])
    if profile is None or profile.get("enabled") is not True:
        return make_decision(
            "REJECTED_PROFILE",
            submission,
            reason="unknown or disabled verification profile",
        )
    if submission["protocol_namespace"] != profile.get("protocol_namespace"):
        return make_decision(
            "REJECTED_PROFILE",
            submission,
            reason="submission namespace does not match verification profile",
        )

    allowed = profile_allowed_claims(profile)
    overreach = sorted(set(submission["requested_claims"]) - set(allowed))
    if overreach:
        return make_decision(
            "REJECTED_CLAIM_OVERREACH",
            submission,
            reason="requested claims exceed this trusted profile",
            rejected_claims=overreach,
            allowed_claims=sorted(allowed),
        )

    source = submission["source"]
    if not source_matches_profile(source, profile):
        return make_decision(
            "REJECTED_INTEGRITY",
            submission,
            reason="declared source does not match the immutable source pin for this profile",
        )

    verifier_bytes = verify_trusted_verifier_pin(profile)

    with tempfile.TemporaryDirectory(prefix="cgqa-proof-submission-") as tmpdir:
        evidence = Path(tmpdir) / "evidence.json"
        try:
            materialize_source(source, evidence, source_file)
        except Exception as exc:  # noqa: BLE001 - network/source boundary
            return make_decision(
                "REJECTED_SOURCE_UNAVAILABLE",
                submission,
                reason=f"could not materialize pinned source: {type(exc).__name__}: {exc}",
            )
        integrity_ok, integrity = check_source_integrity(evidence, source)
        if not integrity_ok:
            return make_decision(
                "REJECTED_INTEGRITY",
                submission,
                reason="materialized source bytes do not match the submission pin",
                source_integrity=integrity,
            )

        verified, verifier_report, verifier_output = run_trusted_verifier(verifier_bytes, evidence)
        if not verified:
            return make_decision(
                "REJECTED_VERIFICATION",
                submission,
                reason="trusted verifier rejected the evidence",
                source_integrity=integrity,
                verifier_output=verifier_output,
            )

    accepted_claims = [
        {"id": claim_id, "text": allowed[claim_id]}
        for claim_id in submission["requested_claims"]
    ]
    combined_non_claims: list[str] = []
    for item in [*submission["non_claims"], *profile.get("required_non_claims", [])]:
        if item not in combined_non_claims:
            combined_non_claims.append(item)

    verifier_pin = profile["trusted_verifier"]
    return make_decision(
        ADMITTED,
        submission,
        protocol_namespace=submission["protocol_namespace"],
        verification_profile=submission["verification_profile"],
        submitted_by=submission["submitted_by"],
        source=submission["source"],
        source_integrity=integrity,
        trusted_verifier={
            "merge_commit": verifier_pin["merge_commit"],
            "path": verifier_pin["path"],
            "blob_sha": verifier_pin["blob_sha"],
        },
        accepted_claims=accepted_claims,
        non_claims=combined_non_claims,
        claim_ceiling=profile["claim_ceiling"],
        verifier_report=verifier_report,
        registry_candidate={
            "id": f"external-{submission['submission_id']}",
            "kind": "external_submission_candidate",
            "status": "candidate_pending_immutable_merge",
            "claim_inputs": [],
            "claims": submission["requested_claims"],
            "non_claims": combined_non_claims,
            "claim_ceiling": profile["claim_ceiling"],
            "source": submission["source"],
        },
        promotion_gate={
            "canonical_registry_mutated": False,
            "requires_human_review": True,
            "requires_immutable_merge_artifact": True,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one ContractGraph external proof submission")
    parser.add_argument("submission", help="Path to submission JSON")
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES), help="Trusted profile catalog")
    parser.add_argument("--source-file", help="Optional local source bytes instead of network materialization")
    parser.add_argument("--write-decision", help="Optional path for the admission decision JSON")
    parser.add_argument("--require-admitted", action="store_true", help="Exit non-zero unless status is ADMITTED_BOUNDED")
    args = parser.parse_args()

    submission_path = Path(args.submission)
    try:
        submission = load_json(submission_path)
        decision = process_submission(submission, Path(args.profiles), args.source_file)
    except PlatformIntegrityError as exc:
        sys.stderr.write(f"PLATFORM_INTEGRITY_FAILURE: {exc}\n")
        return 2
    except Exception as exc:  # noqa: BLE001 - top-level fail closed
        sys.stderr.write(f"PLATFORM_FAILURE: {type(exc).__name__}: {exc}\n")
        return 2

    write_decision(decision, args.write_decision)
    if args.require_admitted and decision["status"] != ADMITTED:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
