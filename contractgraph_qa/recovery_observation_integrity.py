from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

SYSTEM_CASE = "FCRP-SYSTEM-013"
SCHEMA = "cgqa.recovery-observation-receipt.v0.1"
SUITE_SCHEMA = "cgqa.recovery-observation-suite-receipt.v0.1"
PARENT_SYSTEM_012_HEAD = "82ff749eba2d257cfbebf873b52ec152c5b4664a"
PARENT_SYSTEM_012_RECEIPT_DIGEST = "sha256:a7ea56e8d8b9515301bf7f99e20c2817eb9848f2279aaa969c2ab08b25c42563"
EVIDENCE_BOUNDARY = "RECOVERY_OBSERVATION_MODE_NOT_AUTHORITY"
VERDICT = "RECOVERY_OBSERVATION_BOUNDARIES_PRESERVED"

EXPECTED: dict[str, tuple[str, str, str]] = {
    "checkpointed_current": ("CONSISTENT_CURRENT", "ACCEPT_OBSERVATION", "HOLD"),
    "live_wal_divergence": ("DIVERGENT_READ_VIEWS", "HOLD", "HOLD"),
    "main_db_only_snapshot": ("READABLE_STALE_VIEW", "HOLD", "HOLD"),
}


class RecoveryObservationError(ValueError):
    """Raised when an observation claim exceeds the bytes or read mode actually observed."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _byte_inventory(root: Path) -> dict[str, Any]:
    db = root / "authority.db"
    wal = root / "authority.db-wal"
    shm = root / "authority.db-shm"
    return {
        "main": {"present": db.exists(), "digest": _file_digest(db)},
        "wal": {"present": wal.exists(), "digest": _file_digest(wal)},
        "shm": {"present": shm.exists(), "digest": _file_digest(shm)},
    }


def _create_baseline(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    db = root / "authority.db"
    con = sqlite3.connect(db)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=FULL")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        con.execute("INSERT INTO meta(key, value) VALUES('generation', 1)")
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()


def _open_writer_at_generation_2(root: Path) -> sqlite3.Connection:
    con = sqlite3.connect(root / "authority.db")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA wal_autocheckpoint=0")
    con.execute("UPDATE meta SET value=2 WHERE key='generation'")
    con.commit()
    return con


def _read_generation(path: Path, mode: str) -> dict[str, Any]:
    if mode == "plain-ro":
        uri = f"file:{path}?mode=ro"
    elif mode == "immutable-ro":
        uri = f"file:{path}?mode=ro&immutable=1"
    else:
        raise RecoveryObservationError(f"unknown read mode: {mode}")

    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            check = con.execute("PRAGMA integrity_check").fetchone()
            row = con.execute("SELECT value FROM meta WHERE key='generation'").fetchone()
            if not check or check[0] != "ok" or not row or not isinstance(row[0], int):
                return {
                    "mode": mode,
                    "status": "UNREADABLE",
                    "generation": None,
                    "error": "integrity-or-generation-failed",
                }
            return {"mode": mode, "status": "READABLE", "generation": row[0], "error": None}
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        return {"mode": mode, "status": "UNREADABLE", "generation": None, "error": type(exc).__name__}


def _classify(plain: dict[str, Any], immutable: dict[str, Any], committed_generation: int) -> str:
    if plain["status"] != "READABLE" or immutable["status"] != "READABLE":
        return "UNREADABLE_VIEW"
    pgen = plain["generation"]
    igen = immutable["generation"]
    if pgen != igen:
        return "DIVERGENT_READ_VIEWS"
    if pgen != committed_generation:
        return "READABLE_STALE_VIEW"
    return "CONSISTENT_CURRENT"


def _observe(root: Path, committed_generation: int) -> dict[str, Any]:
    db = root / "authority.db"
    plain = _read_generation(db, "plain-ro")
    immutable = _read_generation(db, "immutable-ro")
    classification = _classify(plain, immutable, committed_generation)
    observation_decision = "ACCEPT_OBSERVATION" if classification == "CONSISTENT_CURRENT" else "HOLD"
    return {
        "byteInventory": _byte_inventory(root),
        "plainRead": plain,
        "immutableRead": immutable,
        "producerCommittedGeneration": committed_generation,
        "classification": classification,
        "observationDecision": observation_decision,
        "executionDecision": "HOLD",
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
    }


def finalize_case_receipt(
    *,
    case: str,
    observation: dict[str, Any],
    parent_head: str = PARENT_SYSTEM_012_HEAD,
    parent_receipt_digest: str = PARENT_SYSTEM_012_RECEIPT_DIGEST,
    evidence_boundary: str = EVIDENCE_BOUNDARY,
    authority_claimed: bool = False,
) -> dict[str, Any]:
    if case not in EXPECTED:
        raise RecoveryObservationError(f"unknown case: {case}")
    if parent_head != PARENT_SYSTEM_012_HEAD:
        raise RecoveryObservationError("parent SYSTEM-012 exact-head pin mismatch")
    if parent_receipt_digest != PARENT_SYSTEM_012_RECEIPT_DIGEST:
        raise RecoveryObservationError("parent SYSTEM-012 receipt digest mismatch")
    if evidence_boundary != EVIDENCE_BOUNDARY:
        raise RecoveryObservationError("SYSTEM-013 may not promote its evidence boundary")
    if authority_claimed:
        raise RecoveryObservationError("observation consistency cannot itself claim authority")

    expected_classification, expected_observation, expected_execution = EXPECTED[case]
    if observation.get("classification") != expected_classification:
        raise RecoveryObservationError(
            "classification mismatch: "
            f"expected={expected_classification} observed={observation.get('classification')} "
            f"plain={observation.get('plainRead')} immutable={observation.get('immutableRead')} "
            f"bytes={observation.get('byteInventory')}"
        )
    if observation.get("observationDecision") != expected_observation:
        raise RecoveryObservationError("observation decision exceeds observed evidence")
    if observation.get("executionDecision") != expected_execution:
        raise RecoveryObservationError("execution must remain HOLD")
    if observation.get("authorityTransfer") != "NONE":
        raise RecoveryObservationError("observation verification must transfer no authority")
    for field in ("executionAuthorized", "mutationAuthorized", "externalEffectsPerformed"):
        if observation.get(field) is not False:
            raise RecoveryObservationError(f"{field} must remain false")

    unsigned = {
        "schema": SCHEMA,
        "systemCase": SYSTEM_CASE,
        "case": case,
        "parent": {
            "systemCase": "FCRP-SYSTEM-012",
            "head": parent_head,
            "containerHardStopReceiptDigest": parent_receipt_digest,
        },
        "producerCommittedGeneration": observation["producerCommittedGeneration"],
        "byteInventory": observation["byteInventory"],
        "plainRead": observation["plainRead"],
        "immutableRead": observation["immutableRead"],
        "classification": expected_classification,
        "observationDecision": expected_observation,
        "executionDecision": expected_execution,
        "authorityClaimed": False,
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
    }
    receipt = dict(unsigned)
    receipt["receiptDigest"] = _sha256(unsigned)
    return receipt


def run_case(case: str) -> dict[str, Any]:
    if case not in EXPECTED:
        raise RecoveryObservationError(f"unknown case: {case}")

    with tempfile.TemporaryDirectory(prefix=f"system-013-{case}-") as tmp:
        root = Path(tmp)
        _create_baseline(root)
        writer = _open_writer_at_generation_2(root)
        try:
            if case == "checkpointed_current":
                writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                observation = _observe(root, 2)
            elif case == "live_wal_divergence":
                # The committed generation exists in WAL. Plain read-only sees WAL;
                # immutable read-only intentionally ignores sidecars and sees the base file.
                observation = _observe(root, 2)
            else:
                # Simulate a recovery package that preserved only the readable main DB
                # while omitting the WAL carrying the committed generation.
                snapshot = root / "main-only"
                snapshot.mkdir()
                shutil.copy2(root / "authority.db", snapshot / "authority.db")
                observation = _observe(snapshot, 2)
        finally:
            writer.close()

    return finalize_case_receipt(case=case, observation=observation)


def run_matrix(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    for case in EXPECTED:
        receipt = run_case(case)
        receipts.append(receipt)
        (output_dir / f"{case}.receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    unsigned = {
        "schema": SUITE_SCHEMA,
        "systemCase": SYSTEM_CASE,
        "parentHead": PARENT_SYSTEM_012_HEAD,
        "parentContainerHardStopReceiptDigest": PARENT_SYSTEM_012_RECEIPT_DIGEST,
        "caseCount": len(receipts),
        "allExecutionHeld": all(r["executionDecision"] == "HOLD" for r in receipts),
        "allAuthorityUnclaimed": all(r["authorityClaimed"] is False for r in receipts),
        "divergentWalViewObserved": any(r["classification"] == "DIVERGENT_READ_VIEWS" for r in receipts),
        "readableStaleViewObserved": any(r["classification"] == "READABLE_STALE_VIEW" for r in receipts),
        "consistentCheckpointedViewObserved": any(r["classification"] == "CONSISTENT_CURRENT" for r in receipts),
        "authorityTransfer": "NONE",
        "executionAuthorized": False,
        "mutationAuthorized": False,
        "externalEffectsPerformed": False,
        "evidenceBoundary": EVIDENCE_BOUNDARY,
        "verdict": VERDICT,
        "caseReceiptDigests": [r["receiptDigest"] for r in receipts],
    }
    suite = dict(unsigned)
    suite["receiptDigest"] = _sha256(unsigned)
    (output_dir / "recovery-observation-suite-receipt.json").write_text(
        json.dumps(suite, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    matrix = sub.add_parser("matrix")
    matrix.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "matrix":
        suite = run_matrix(args.output)
        print("SYSTEM_013_DIVERGENT_WAL_VIEW", str(suite["divergentWalViewObserved"]).upper())
        print("SYSTEM_013_READABLE_STALE_VIEW", str(suite["readableStaleViewObserved"]).upper())
        print("SYSTEM_013_CHECKPOINTED_CURRENT", str(suite["consistentCheckpointedViewObserved"]).upper())
        print("SYSTEM_013_EXECUTION_HELD", str(suite["allExecutionHeld"]).upper())
        print("SYSTEM_013_AUTHORITY_UNCLAIMED", str(suite["allAuthorityUnclaimed"]).upper())
        print("SYSTEM_013_VERDICT", suite["verdict"])
        print("SYSTEM_013_RECEIPT", suite["receiptDigest"])
        print("EVIDENCE_BOUNDARY", suite["evidenceBoundary"])
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
