"""Host-filesystem storage fault verification for FCRP-SYSTEM-009.

SYSTEM-009 strengthens Recovery Integrity with real file mutations on a hosted
Linux filesystem: missing/truncated projections, split generations, orphan temp
candidates, and corrupted SQLite authority bytes.

This is deliberately *not* physical power-loss evidence. The contract refuses
claims that exceed the observed host-filesystem fault-injection boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .recovery_integrity_adapter import canonical_bytes

SYSTEM_CASE = "FCRP-SYSTEM-009"
SCHEMA = "cgqa.storage-fault-receipt.v0.1"
EVIDENCE_BOUNDARY = "HOST_FILESYSTEM_FAULT_INJECTION_NOT_PHYSICAL_POWER_LOSS"
PARENT_SYSTEM_008_HEAD = "71a37c7a6b71454edca2b50ef89ac3edff2d3855"
PARENT_RECOVERY_RECEIPT_DIGEST = (
    "sha256:30f6966e3a55606f6ed3fc7ac04760a6c1ed6e53d858b589d51fde6d3daf6736"
)

CASES = (
    "healthy",
    "projection_missing",
    "projection_truncated",
    "projection_future_generation",
    "orphan_temp_candidate",
    "authority_header_corrupt",
)

EXPECTED = {
    "healthy": ("HEALTHY", "NO_REBUILD", "HOLD"),
    "projection_missing": ("MISSING", "ALLOW_REBUILD", "HOLD"),
    "projection_truncated": ("CORRUPT", "ALLOW_REBUILD", "HOLD"),
    "projection_future_generation": ("UNPROVABLE", "HOLD", "HOLD"),
    "orphan_temp_candidate": ("STALE", "ALLOW_REBUILD", "HOLD"),
    "authority_header_corrupt": ("UNPROVABLE", "HOLD", "HOLD"),
}


class StorageFaultError(ValueError):
    """Raised when a storage-fault claim exceeds the evidence boundary."""


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _write_projection(path: Path, generation: int) -> None:
    payload = {
        "schema": "projection.v1",
        "generation": generation,
        "projects": ["alpha", "beta"],
        "pins": ["thread-1"],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    if hasattr(os, "O_DIRECTORY"):
        fd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _create_authority(path: Path, generation: int) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        con.execute("CREATE TABLE threads(id TEXT PRIMARY KEY, project TEXT NOT NULL)")
        con.execute("INSERT INTO meta(key, value) VALUES('generation', ?)", (generation,))
        con.execute("INSERT INTO threads(id, project) VALUES('thread-1', 'alpha')")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        con.close()


def _read_authority(path: Path) -> dict[str, Any]:
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            check = con.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                return {"integrity": "CORRUPT", "generation": None, "error": str(check)}
            row = con.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
            if not row or not isinstance(row[0], int):
                return {"integrity": "CORRUPT", "generation": None, "error": "missing generation"}
            return {"integrity": "VALID", "generation": row[0], "error": None}
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return {"integrity": "CORRUPT", "generation": None, "error": type(exc).__name__}


def _read_projection(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"integrity": "MISSING", "generation": None, "error": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"integrity": "CORRUPT", "generation": None, "error": type(exc).__name__}
    generation = payload.get("generation")
    if not isinstance(generation, int):
        return {"integrity": "CORRUPT", "generation": None, "error": "missing generation"}
    return {"integrity": "VALID", "generation": generation, "error": None}


def observe_storage_state(root: Path) -> dict[str, Any]:
    authority = _read_authority(root / "authority.db")
    projection = _read_projection(root / "projection.json")
    temp = _read_projection(root / "projection.json.tmp")

    if authority["integrity"] != "VALID":
        state = "UNPROVABLE"
    elif projection["integrity"] == "MISSING":
        state = "MISSING"
    elif projection["integrity"] == "CORRUPT":
        state = "CORRUPT"
    elif projection["generation"] > authority["generation"]:
        state = "UNPROVABLE"
    elif projection["generation"] < authority["generation"]:
        state = "STALE"
    else:
        state = "HEALTHY"

    if authority["integrity"] == "VALID" and state in {"MISSING", "STALE", "CORRUPT"}:
        rebuild = "ALLOW_REBUILD"
    elif state == "HEALTHY":
        rebuild = "NO_REBUILD"
    else:
        rebuild = "HOLD"

    return {
        "authority": authority,
        "projection": projection,
        "tempCandidate": temp,
        "projectionState": state,
        "rebuildDecision": rebuild,
        "executionDecision": "HOLD",
        "tempCandidateAuthority": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }


def _prepare_case(root: Path, case: str) -> None:
    if case not in CASES:
        raise StorageFaultError(f"unknown case: {case}")

    authority_generation = 3 if case == "orphan_temp_candidate" else 2
    projection_generation = 2
    _create_authority(root / "authority.db", authority_generation)
    _write_projection(root / "projection.json", projection_generation)

    if case == "healthy":
        return
    if case == "projection_missing":
        (root / "projection.json").unlink()
        return
    if case == "projection_truncated":
        path = root / "projection.json"
        raw = path.read_bytes()
        path.write_bytes(raw[: max(1, len(raw) // 2)])
        return
    if case == "projection_future_generation":
        _write_projection(root / "projection.json", authority_generation + 1)
        return
    if case == "orphan_temp_candidate":
        payload = {
            "schema": "projection.v1",
            "generation": authority_generation,
            "projects": ["alpha", "beta"],
            "pins": ["thread-1"],
        }
        tmp = root / "projection.json.tmp"
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
            fh.flush()
            os.fsync(fh.fileno())
        return
    if case == "authority_header_corrupt":
        path = root / "authority.db"
        raw = bytearray(path.read_bytes())
        if len(raw) < 32:
            raise StorageFaultError("authority fixture unexpectedly small")
        raw[:16] = b"BROKEN-SQLITE!!!"
        path.write_bytes(raw)
        return


def finalize_storage_fault_receipt(
    *,
    case: str,
    observation: dict[str, Any],
    parent_head: str = PARENT_SYSTEM_008_HEAD,
    parent_receipt_digest: str = PARENT_RECOVERY_RECEIPT_DIGEST,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
) -> dict[str, Any]:
    if case not in EXPECTED:
        raise StorageFaultError(f"unknown case: {case}")
    if parent_head != PARENT_SYSTEM_008_HEAD:
        raise StorageFaultError("parent SYSTEM-008 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_RECOVERY_RECEIPT_DIGEST:
        raise StorageFaultError("parent Recovery Receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise StorageFaultError("SYSTEM-009 may not claim physical power-loss evidence")

    expected_state, expected_rebuild, expected_execution = EXPECTED[case]
    if observation.get("projectionState") != expected_state:
        raise StorageFaultError("projection state does not match case contract")
    if observation.get("rebuildDecision") != expected_rebuild:
        raise StorageFaultError("rebuild decision exceeds evidence")
    if observation.get("executionDecision") != expected_execution:
        raise StorageFaultError("execution continuation must remain HOLD")
    if observation.get("tempCandidateAuthority") is not False:
        raise StorageFaultError("orphan temp candidate must never become authority")
    if observation.get("authorityTransfer") != "NONE":
        raise StorageFaultError("verification must transfer no authority")
    for field in ("executionAuthorized", "mutationAuthorized", "externalEffectsPerformed"):
        if observation.get(field) is not False:
            raise StorageFaultError(f"{field} must remain false")

    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "faultCase": case,
        "parent": {
            "systemCase": "FCRP-SYSTEM-008",
            "head": parent_head,
            "recoveryReceiptDigest": parent_receipt_digest,
        },
        "projectionState": expected_state,
        "rebuildDecision": expected_rebuild,
        "executionDecision": expected_execution,
        "authorityIntegrity": observation["authority"]["integrity"],
        "authorityGeneration": observation["authority"]["generation"],
        "projectionIntegrity": observation["projection"]["integrity"],
        "projectionGeneration": observation["projection"]["generation"],
        "tempCandidateGeneration": observation["tempCandidate"]["generation"],
        "tempCandidateAuthority": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256(unsigned)
    return receipt


def run_fault_case(case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix=f"system-009-{case}-") as tmp:
        root = Path(tmp)
        _prepare_case(root, case)
        observation = observe_storage_state(root)
        receipt = finalize_storage_fault_receipt(case=case, observation=observation)
        return observation, receipt


def run_matrix(output_dir: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        observation, receipt = run_fault_case(case)
        row = {
            "case": case,
            "projectionState": observation["projectionState"],
            "rebuildDecision": observation["rebuildDecision"],
            "executionDecision": observation["executionDecision"],
            "authorityIntegrity": observation["authority"]["integrity"],
            "tempCandidateAuthority": observation["tempCandidateAuthority"],
            "receiptDigest": receipt["receiptDigest"],
            "evidenceBoundary": receipt["evidenceBoundary"],
        }
        rows.append(row)
        if output_dir is not None:
            (output_dir / f"{case}.receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    if output_dir is not None:
        (output_dir / "matrix.json").write_text(
            json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["matrix"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = run_matrix(args.output)
    for row in rows:
        print(
            row["case"],
            row["projectionState"],
            row["rebuildDecision"],
            row["executionDecision"],
            row["authorityIntegrity"],
        )
    print(f"PASS storage-fault matrix {len(rows)}/{len(CASES)}")
    print(f"EVIDENCE_BOUNDARY {EVIDENCE_BOUNDARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
