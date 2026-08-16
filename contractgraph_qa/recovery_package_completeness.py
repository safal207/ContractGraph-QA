from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

SYSTEM_CASE = "FCRP-SYSTEM-014"
SCHEMA = "cgqa.recovery-package-receipt.v0.1"
SUITE_SCHEMA = "cgqa.recovery-package-suite-receipt.v0.1"
MANIFEST_SCHEMA = "cgqa.recovery-package-manifest.v0.1"
COMMIT_MARKER_SCHEMA = "cgqa.recovery-package-commit-marker.v0.1"
PARENT_SYSTEM_013_HEAD = "896b8c6e4710c733e7ac82ac70e0287f3ffa017d"
PARENT_SYSTEM_013_RECEIPT_DIGEST = "sha256:cd35a7a0157b5750986ea85c7482c6b62310d62cca9e3fd2db18831a2a746c20"
EVIDENCE_BOUNDARY = "RECOVERY_PACKAGE_COMPLETENESS_NOT_AUTHORITY"
VERDICT = "RECOVERY_PACKAGE_COMPLETENESS_BOUNDARIES_PRESERVED"

CASES = (
    "complete_live_wal_package",
    "missing_required_wal",
    "tampered_required_wal",
    "generation_incoherent_manifest",
)

EXPECTED = {
    "complete_live_wal_package": ("COMPLETE_COHERENT", "ALLOW_OBSERVATION"),
    "missing_required_wal": ("MISSING_REQUIRED_COMPONENT", "HOLD"),
    "tampered_required_wal": ("DIGEST_MISMATCH", "HOLD"),
    "generation_incoherent_manifest": ("GENERATION_INCOHERENT", "HOLD"),
}

REQUIRED_BASE_COMPONENTS = (
    "authority.db",
    "authority.db-wal",
    "projection.json",
    "commit-marker.json",
)


class RecoveryPackageError(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_value(value: object) -> str:
    return _sha256_bytes(canonical_bytes(value))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _fsync_dir(path: Path) -> None:
    if hasattr(os, "O_DIRECTORY"):
        fd = os.open(str(path), os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, sort_keys=True, separators=(",", ":"))
        fh.flush()
        os.fsync(fh.fileno())
    _fsync_dir(path.parent)


def _component_entry(path: Path, role: str) -> dict[str, str]:
    return {"path": path.name, "role": role, "sha256": _sha256_file(path)}


def _make_live_wal_package(package_dir: Path) -> dict[str, Any]:
    package_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="system-014-producer-") as tmp:
        source = Path(tmp)
        db = source / "authority.db"
        con = sqlite3.connect(db)
        try:
            mode = con.execute("PRAGMA journal_mode=WAL").fetchone()
            if not mode or str(mode[0]).lower() != "wal":
                raise RecoveryPackageError("SQLite WAL mode unavailable")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA wal_autocheckpoint=0")
            con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
            con.execute("INSERT INTO meta(key, value) VALUES('generation', 1)")
            con.commit()
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con.execute("UPDATE meta SET value=2 WHERE key='generation'")
            con.commit()

            wal = source / "authority.db-wal"
            if not wal.exists() or wal.stat().st_size <= 32:
                raise RecoveryPackageError("expected committed WAL sidecar was not materialized")

            shutil.copy2(db, package_dir / "authority.db")
            shutil.copy2(wal, package_dir / "authority.db-wal")
        finally:
            con.close()

    projection = {
        "schema": "projection.v1",
        "generation": 2,
        "projects": ["alpha", "beta"],
        "pins": ["thread-1"],
    }
    _write_json(package_dir / "projection.json", projection)

    marker = {
        "schema": COMMIT_MARKER_SCHEMA,
        "committedGeneration": 2,
        "storageMode": "SQLITE_WAL",
        "requiredSidecars": ["authority.db-wal"],
        "observationMode": "SQLITE_RO_WITH_REQUIRED_WAL",
    }
    _write_json(package_dir / "commit-marker.json", marker)

    components = {
        "authority.db": _component_entry(package_dir / "authority.db", "authority-main"),
        "authority.db-wal": _component_entry(package_dir / "authority.db-wal", "authority-sidecar"),
        "projection.json": _component_entry(package_dir / "projection.json", "projection"),
        "commit-marker.json": _component_entry(package_dir / "commit-marker.json", "commit-marker"),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "systemCase": SYSTEM_CASE,
        "packageGeneration": 2,
        "requiredComponents": list(REQUIRED_BASE_COMPONENTS),
        "components": components,
        "commitMarkerPath": "commit-marker.json",
        "parent": {
            "systemCase": "FCRP-SYSTEM-013",
            "head": PARENT_SYSTEM_013_HEAD,
            "recoveryObservationReceiptDigest": PARENT_SYSTEM_013_RECEIPT_DIGEST,
        },
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    _write_json(package_dir / "manifest.json", manifest)
    return manifest


def _mutate_case(case: str, package_dir: Path) -> None:
    if case == "complete_live_wal_package":
        return
    if case == "missing_required_wal":
        (package_dir / "authority.db-wal").unlink()
        return
    if case == "tampered_required_wal":
        with (package_dir / "authority.db-wal").open("ab") as fh:
            fh.write(b"SYSTEM-014-TAMPER")
            fh.flush()
            os.fsync(fh.fileno())
        return
    if case == "generation_incoherent_manifest":
        path = package_dir / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["packageGeneration"] = 3
        _write_json(path, manifest)
        return
    raise RecoveryPackageError(f"unknown case: {case}")


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryPackageError(f"{label} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise RecoveryPackageError(f"{label} must be a JSON object")
    return value


def validate_package(
    package_dir: Path,
    *,
    parent_head: str = PARENT_SYSTEM_013_HEAD,
    parent_receipt_digest: str = PARENT_SYSTEM_013_RECEIPT_DIGEST,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
    authority_claimed: bool = False,
    authority_transfer: str = "NONE",
    execution_authorized: bool = False,
    mutation_authorized: bool = False,
    external_effects_performed: bool = False,
) -> dict[str, Any]:
    if parent_head != PARENT_SYSTEM_013_HEAD:
        raise RecoveryPackageError("parent SYSTEM-013 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_SYSTEM_013_RECEIPT_DIGEST:
        raise RecoveryPackageError("parent SYSTEM-013 receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise RecoveryPackageError("SYSTEM-014 may not promote its evidence boundary")
    if authority_claimed:
        raise RecoveryPackageError("package completeness cannot claim authority")
    if authority_transfer != "NONE":
        raise RecoveryPackageError("package verifier cannot transfer authority")
    if execution_authorized:
        raise RecoveryPackageError("package completeness cannot authorize execution")
    if mutation_authorized:
        raise RecoveryPackageError("package verifier cannot authorize mutation")
    if external_effects_performed:
        raise RecoveryPackageError("package verification cannot perform external effects")

    manifest_path = package_dir / "manifest.json"
    manifest = _load_json(manifest_path, "manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise RecoveryPackageError("unexpected manifest schema")
    if manifest.get("systemCase") != SYSTEM_CASE:
        raise RecoveryPackageError("manifest systemCase mismatch")
    if manifest.get("evidenceBoundary") != EVIDENCE_BOUNDARY:
        raise RecoveryPackageError("manifest evidence boundary mismatch")

    parent = manifest.get("parent")
    if not isinstance(parent, dict):
        raise RecoveryPackageError("manifest parent binding missing")
    if parent.get("head") != PARENT_SYSTEM_013_HEAD:
        raise RecoveryPackageError("manifest parent head mismatch")
    if parent.get("recoveryObservationReceiptDigest") != PARENT_SYSTEM_013_RECEIPT_DIGEST:
        raise RecoveryPackageError("manifest parent receipt mismatch")

    required = manifest.get("requiredComponents")
    components = manifest.get("components")
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise RecoveryPackageError("manifest requiredComponents is invalid")
    if not isinstance(components, dict):
        raise RecoveryPackageError("manifest components is invalid")
    if set(required) != set(REQUIRED_BASE_COMPONENTS):
        raise RecoveryPackageError("manifest required component set drift")

    missing = []
    digest_mismatches = []
    for name in required:
        entry = components.get(name)
        if not isinstance(entry, dict):
            raise RecoveryPackageError(f"component metadata missing: {name}")
        if entry.get("path") != name:
            raise RecoveryPackageError(f"component path mismatch: {name}")
        expected_digest = entry.get("sha256")
        if not isinstance(expected_digest, str) or not expected_digest.startswith("sha256:"):
            raise RecoveryPackageError(f"component digest invalid: {name}")
        path = package_dir / name
        if not path.exists():
            missing.append(name)
            continue
        if _sha256_file(path) != expected_digest:
            digest_mismatches.append(name)

    manifest_digest = _sha256_file(manifest_path)
    package_complete = False
    generation_coherent = False
    observation_decision = "HOLD"
    marker_generation = None
    projection_generation = None
    package_generation = manifest.get("packageGeneration")

    if missing:
        classification = "MISSING_REQUIRED_COMPONENT"
    elif digest_mismatches:
        classification = "DIGEST_MISMATCH"
    else:
        marker = _load_json(package_dir / str(manifest.get("commitMarkerPath")), "commit marker")
        projection = _load_json(package_dir / "projection.json", "projection")
        if marker.get("schema") != COMMIT_MARKER_SCHEMA:
            raise RecoveryPackageError("unexpected commit marker schema")
        if marker.get("storageMode") != "SQLITE_WAL":
            raise RecoveryPackageError("SYSTEM-014 fixture requires SQLITE_WAL storage mode")
        if marker.get("requiredSidecars") != ["authority.db-wal"]:
            raise RecoveryPackageError("commit marker sidecar declaration drift")
        if marker.get("observationMode") != "SQLITE_RO_WITH_REQUIRED_WAL":
            raise RecoveryPackageError("commit marker observation mode drift")
        marker_generation = marker.get("committedGeneration")
        projection_generation = projection.get("generation")
        package_complete = True
        generation_coherent = (
            isinstance(package_generation, int)
            and isinstance(marker_generation, int)
            and isinstance(projection_generation, int)
            and package_generation == marker_generation == projection_generation
        )
        if generation_coherent:
            classification = "COMPLETE_COHERENT"
            observation_decision = "ALLOW_OBSERVATION"
        else:
            classification = "GENERATION_INCOHERENT"

    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parent": {
            "systemCase": "FCRP-SYSTEM-013",
            "head": PARENT_SYSTEM_013_HEAD,
            "recoveryObservationReceiptDigest": PARENT_SYSTEM_013_RECEIPT_DIGEST,
        },
        "manifestDigest": manifest_digest,
        "classification": classification,
        "packageComplete": package_complete,
        "generationCoherent": generation_coherent,
        "packageGeneration": package_generation,
        "commitMarkerGeneration": marker_generation,
        "projectionGeneration": projection_generation,
        "missingComponents": sorted(missing),
        "digestMismatches": sorted(digest_mismatches),
        "observationDecision": observation_decision,
        "executionDecision": "HOLD",
        "authorityClaimed": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256_value(unsigned)
    return receipt


def run_case(case: str, output_dir: Path) -> dict[str, Any]:
    if case not in CASES:
        raise RecoveryPackageError(f"unknown case: {case}")
    with tempfile.TemporaryDirectory(prefix=f"system-014-{case}-") as tmp:
        package_dir = Path(tmp) / "package"
        _make_live_wal_package(package_dir)
        _mutate_case(case, package_dir)
        receipt = validate_package(package_dir)
        expected_classification, expected_observation = EXPECTED[case]
        if receipt["classification"] != expected_classification:
            raise RecoveryPackageError(
                f"{case}: expected {expected_classification}, observed {receipt['classification']}"
            )
        if receipt["observationDecision"] != expected_observation:
            raise RecoveryPackageError(
                f"{case}: expected observation {expected_observation}, observed {receipt['observationDecision']}"
            )
        if receipt["executionDecision"] != "HOLD":
            raise RecoveryPackageError("execution continuation must remain HOLD")
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / f"{case}.receipt.json", receipt)
        if case == "complete_live_wal_package":
            manifest = _load_json(package_dir / "manifest.json", "manifest")
            _write_json(output_dir / "complete.manifest.json", manifest)
        return receipt


def run_matrix(output_dir: Path) -> dict[str, Any]:
    receipts = [run_case(case, output_dir) for case in CASES]
    by_case = dict(zip(CASES, receipts))
    semantic = {
        "schema": SUITE_SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parentHead": PARENT_SYSTEM_013_HEAD,
        "parentRecoveryObservationReceiptDigest": PARENT_SYSTEM_013_RECEIPT_DIGEST,
        "caseCount": len(receipts),
        "completePackageObserved": by_case["complete_live_wal_package"]["classification"] == "COMPLETE_COHERENT",
        "missingSidecarRejected": by_case["missing_required_wal"]["classification"] == "MISSING_REQUIRED_COMPONENT",
        "tamperedSidecarRejected": by_case["tampered_required_wal"]["classification"] == "DIGEST_MISMATCH",
        "generationIncoherenceRejected": by_case["generation_incoherent_manifest"]["classification"] == "GENERATION_INCOHERENT",
        "allExecutionHeld": all(r["executionDecision"] == "HOLD" for r in receipts),
        "allAuthorityUnclaimed": all(r["authorityClaimed"] is False for r in receipts),
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "verdict": VERDICT,
    }
    case_receipt_digests = {case: by_case[case]["receiptDigest"] for case in CASES}
    suite = dict(semantic)
    suite["receiptDigest"] = _sha256_value(semantic)
    suite["caseReceiptDigests"] = case_receipt_digests
    suite["evidenceSetDigest"] = _sha256_value(case_receipt_digests)
    record_unsigned = dict(suite)
    suite["recordDigest"] = _sha256_value(record_unsigned)
    _write_json(output_dir / "recovery-package-suite-receipt.json", suite)
    return suite


def _print_suite(suite: dict[str, Any]) -> None:
    print("SYSTEM_014_COMPLETE_PACKAGE", str(suite["completePackageObserved"]).upper())
    print("SYSTEM_014_MISSING_SIDECAR_REJECTED", str(suite["missingSidecarRejected"]).upper())
    print("SYSTEM_014_TAMPERED_SIDECAR_REJECTED", str(suite["tamperedSidecarRejected"]).upper())
    print("SYSTEM_014_GENERATION_INCOHERENCE_REJECTED", str(suite["generationIncoherenceRejected"]).upper())
    print("SYSTEM_014_EXECUTION_HELD", str(suite["allExecutionHeld"]).upper())
    print("SYSTEM_014_AUTHORITY_UNCLAIMED", str(suite["allAuthorityUnclaimed"]).upper())
    print("SYSTEM_014_VERDICT", suite["verdict"])
    print("SYSTEM_014_RECEIPT", suite["receiptDigest"])
    print("SYSTEM_014_EVIDENCE_SET", suite["evidenceSetDigest"])
    print("SYSTEM_014_RECORD", suite["recordDigest"])
    print("EVIDENCE_BOUNDARY", suite["evidenceBoundary"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "matrix":
        suite = run_matrix(args.output)
        _print_suite(suite)
        return 0
    raise RecoveryPackageError("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
