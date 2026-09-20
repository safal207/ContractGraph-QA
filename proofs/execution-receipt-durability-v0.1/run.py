#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

SYSTEM_CASE = "EXECUTION-RECEIPT-DURABILITY-001"
SCHEMA = "contractgraph.execution-receipt-durability.v0.1"
CASES = ("effect_then_crash", "crash_before_effect", "unavailable_readback")

CASE_CONFIG = {
    "effect_then_crash": {
        "provider": "openai",
        "target": "provider:openai",
        "request": {"prompt": "durable-effect-then-crash", "model": "durable-model-a"},
    },
    "crash_before_effect": {
        "provider": "gemini",
        "target": "provider:gemini",
        "request": {"prompt": "durable-crash-before-effect", "model": "durable-model-b"},
    },
    "unavailable_readback": {
        "provider": "groq",
        "target": "provider:groq",
        "request": {"prompt": "durable-unavailable-readback", "model": "durable-model-c"},
    },
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def fail(message: str) -> None:
    raise RuntimeError(f"{SYSTEM_CASE}: {message}")


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("pragma journal_mode=WAL")
        conn.execute("pragma synchronous=FULL")
        conn.execute("pragma foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_receipt_db(path: Path) -> None:
    with connect(path) as conn:
        conn.executescript(
            """
            create table if not exists records (
                seq integer primary key autoincrement,
                ordinal integer not null,
                action_id text not null,
                case_name text not null,
                record_kind text not null,
                target text not null,
                payload_digest text not null,
                trace_id text not null,
                decision_id text not null,
                execution_id text not null,
                evidence_id text not null,
                observation_availability text not null,
                external_outcome text not null,
                externally_verified integer not null check (externally_verified in (0,1)),
                effect_count integer,
                continuity text not null,
                recovery_decision text not null,
                previous_record_sha256 text,
                record_sha256 text not null,
                unique(action_id, ordinal)
            );

            create table if not exists verifications (
                seq integer primary key autoincrement,
                action_id text not null,
                verification_kind text not null,
                verified integer not null check (verified in (0,1)),
                observed_record_sha256 text not null
            );
            """
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")


def init_effect_db(path: Path) -> None:
    with connect(path) as conn:
        conn.executescript(
            """
            create table if not exists attempts (
                seq integer primary key autoincrement,
                action_id text not null,
                case_name text not null,
                target text not null,
                payload_digest text not null
            );

            create table if not exists effects (
                seq integer primary key autoincrement,
                action_id text not null,
                case_name text not null,
                target text not null,
                payload_digest text not null,
                result text not null
            );

            create table if not exists verifications (
                seq integer primary key autoincrement,
                action_id text not null,
                verification_kind text not null,
                verified integer not null check (verified in (0,1)),
                observed_effect_count integer not null
            );
            """
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")


def record_body(
    *,
    ordinal: int,
    action_id: str,
    case_name: str,
    record_kind: str,
    target: str,
    payload_digest: str,
    trace_id: str,
    decision_id: str,
    execution_id: str,
    evidence_id: str,
    observation_availability: str,
    external_outcome: str,
    externally_verified: bool,
    effect_count: int | None,
    continuity: str,
    recovery_decision: str,
    previous_record_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "ordinal": ordinal,
        "action_id": action_id,
        "case_name": case_name,
        "record_kind": record_kind,
        "target": target,
        "payload_digest": payload_digest,
        "trace_id": trace_id,
        "decision_id": decision_id,
        "execution_id": execution_id,
        "evidence_id": evidence_id,
        "observation_availability": observation_availability,
        "external_outcome": external_outcome,
        "externally_verified": externally_verified,
        "effect_count": effect_count,
        "continuity": continuity,
        "recovery_decision": recovery_decision,
        "previous_record_sha256": previous_record_sha256,
    }


def insert_record(conn: sqlite3.Connection, body: dict[str, Any]) -> dict[str, Any]:
    digest = sha256_json(body)
    conn.execute(
        """
        insert into records(
            ordinal, action_id, case_name, record_kind, target, payload_digest,
            trace_id, decision_id, execution_id, evidence_id,
            observation_availability, external_outcome, externally_verified,
            effect_count, continuity, recovery_decision,
            previous_record_sha256, record_sha256
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            body["ordinal"],
            body["action_id"],
            body["case_name"],
            body["record_kind"],
            body["target"],
            body["payload_digest"],
            body["trace_id"],
            body["decision_id"],
            body["execution_id"],
            body["evidence_id"],
            body["observation_availability"],
            body["external_outcome"],
            int(body["externally_verified"]),
            body["effect_count"],
            body["continuity"],
            body["recovery_decision"],
            body["previous_record_sha256"],
            digest,
        ),
    )
    return {**body, "record_sha256": digest}


def row_to_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "ordinal": int(row["ordinal"]),
        "action_id": str(row["action_id"]),
        "case_name": str(row["case_name"]),
        "record_kind": str(row["record_kind"]),
        "target": str(row["target"]),
        "payload_digest": str(row["payload_digest"]),
        "trace_id": str(row["trace_id"]),
        "decision_id": str(row["decision_id"]),
        "execution_id": str(row["execution_id"]),
        "evidence_id": str(row["evidence_id"]),
        "observation_availability": str(row["observation_availability"]),
        "external_outcome": str(row["external_outcome"]),
        "externally_verified": bool(row["externally_verified"]),
        "effect_count": None if row["effect_count"] is None else int(row["effect_count"]),
        "continuity": str(row["continuity"]),
        "recovery_decision": str(row["recovery_decision"]),
        "previous_record_sha256": (
            None if row["previous_record_sha256"] is None else str(row["previous_record_sha256"])
        ),
        "record_sha256": str(row["record_sha256"]),
    }


def verify_record(record: dict[str, Any]) -> None:
    supplied = record["record_sha256"]
    body = dict(record)
    body.pop("record_sha256", None)
    actual = sha256_json(body)
    if supplied != actual:
        fail("record SHA-256 mismatch")


def pending_write(args: argparse.Namespace) -> int:
    path = Path(args.receipt_db)
    init_receipt_db(path)
    with connect(path) as conn:
        existing = conn.execute(
            "select count(*) as c from records where action_id = ?",
            (args.action_id,),
        ).fetchone()
        if existing is None or int(existing["c"]) != 0:
            fail("PENDING requires empty action history")

        body = record_body(
            ordinal=1,
            action_id=args.action_id,
            case_name=args.case,
            record_kind="PENDING",
            target=args.target,
            payload_digest=args.payload_digest,
            trace_id=args.trace_id,
            decision_id=args.decision_id,
            execution_id=args.execution_id,
            evidence_id=args.evidence_id,
            observation_availability="NOT_READ_BACK",
            external_outcome="INDETERMINATE",
            externally_verified=False,
            effect_count=None,
            continuity="IN_FLIGHT",
            recovery_decision="AWAIT_TERMINAL_OR_READBACK",
            previous_record_sha256=None,
        )
        record = insert_record(conn, body)
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")

    print(json.dumps({"status": "PENDING_COMMITTED", "record": record}, sort_keys=True))
    return 0


def pending_verify(args: argparse.Namespace) -> int:
    path = Path(args.receipt_db)
    with connect(path, readonly=True) as conn:
        rows = conn.execute(
            "select * from records where action_id = ? order by ordinal",
            (args.action_id,),
        ).fetchall()
    if len(rows) != 1:
        fail(f"fresh pending verifier expected 1 record, got {len(rows)}")
    record = row_to_record(rows[0])
    verify_record(record)
    if record["record_kind"] != "PENDING":
        fail("fresh pending verifier did not observe PENDING")

    with connect(path) as conn:
        conn.execute(
            """
            insert into verifications(action_id, verification_kind, verified, observed_record_sha256)
            values (?, 'FRESH_PROCESS_PENDING_READ', 1, ?)
            """,
            (args.action_id, record["record_sha256"]),
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")

    print(
        json.dumps(
            {
                "status": "PENDING_FRESH_READ_VERIFIED",
                "action_id": args.action_id,
                "record_sha256": record["record_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def attempt_write(args: argparse.Namespace) -> int:
    path = Path(args.effect_db)
    init_effect_db(path)
    with connect(path) as conn:
        conn.execute(
            """
            insert into attempts(action_id, case_name, target, payload_digest)
            values (?, ?, ?, ?)
            """,
            (args.action_id, args.case, args.target, args.payload_digest),
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")
    print(json.dumps({"status": "ATTEMPT_COMMITTED", "action_id": args.action_id}, sort_keys=True))
    return 0


def effect_write(args: argparse.Namespace) -> int:
    path = Path(args.effect_db)
    init_effect_db(path)
    with connect(path) as conn:
        conn.execute(
            """
            insert into effects(action_id, case_name, target, payload_digest, result)
            values (?, ?, ?, ?, ?)
            """,
            (args.action_id, args.case, args.target, args.payload_digest, "effect-ok"),
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")
    print(json.dumps({"status": "EFFECT_COMMITTED", "action_id": args.action_id}, sort_keys=True))
    return 0


def effect_verify(args: argparse.Namespace) -> int:
    path = Path(args.effect_db)
    with connect(path, readonly=True) as conn:
        rows = conn.execute(
            """
            select target, payload_digest, result
            from effects where action_id = ? order by seq
            """,
            (args.action_id,),
        ).fetchall()
    if len(rows) != args.expected_count:
        fail(f"fresh effect verifier expected {args.expected_count}, got {len(rows)}")
    for row in rows:
        if str(row["target"]) != args.target:
            fail("fresh effect verifier target mismatch")
        if str(row["payload_digest"]) != args.payload_digest:
            fail("fresh effect verifier payload mismatch")
        if str(row["result"]) != "effect-ok":
            fail("fresh effect verifier result mismatch")

    with connect(path) as conn:
        conn.execute(
            """
            insert into verifications(action_id, verification_kind, verified, observed_effect_count)
            values (?, 'FRESH_PROCESS_EFFECT_READ', 1, ?)
            """,
            (args.action_id, len(rows)),
        )
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")

    print(
        json.dumps(
            {
                "status": "EFFECT_FRESH_READ_VERIFIED",
                "action_id": args.action_id,
                "effect_count": len(rows),
            },
            sort_keys=True,
        )
    )
    return 0


def read_pending(path: Path, action_id: str) -> dict[str, Any]:
    with connect(path, readonly=True) as conn:
        rows = conn.execute(
            "select * from records where action_id = ? order by ordinal",
            (action_id,),
        ).fetchall()
    if not rows:
        fail("recovery found no durable PENDING")
    records = [row_to_record(row) for row in rows]
    for record in records:
        verify_record(record)
    pending = records[0]
    if pending["record_kind"] != "PENDING":
        fail("first durable record is not PENDING")
    return pending


def raw_effect_snapshot(path: Path, action_id: str) -> dict[str, Any]:
    with connect(path, readonly=True) as conn:
        attempts = conn.execute(
            "select target, payload_digest from attempts where action_id = ? order by seq",
            (action_id,),
        ).fetchall()
        effects = conn.execute(
            "select target, payload_digest, result from effects where action_id = ? order by seq",
            (action_id,),
        ).fetchall()
        verifications = conn.execute(
            """
            select verification_kind, verified, observed_effect_count
            from verifications where action_id = ? order by seq
            """,
            (action_id,),
        ).fetchall()
    return {
        "attempt_count": len(attempts),
        "effect_count": len(effects),
        "attempts": [
            {"target": str(row["target"]), "payload_digest": str(row["payload_digest"])}
            for row in attempts
        ],
        "effects": [
            {
                "target": str(row["target"]),
                "payload_digest": str(row["payload_digest"]),
                "result": str(row["result"]),
            }
            for row in effects
        ],
        "fresh_effect_verifications": [
            {
                "kind": str(row["verification_kind"]),
                "verified": bool(row["verified"]),
                "observed_effect_count": int(row["observed_effect_count"]),
            }
            for row in verifications
        ],
    }


def append_reconciliation(
    *,
    receipt_db: Path,
    pending: dict[str, Any],
    availability: str,
    external_outcome: str,
    externally_verified: bool,
    effect_count: int | None,
    continuity: str,
    recovery_decision: str,
) -> dict[str, Any]:
    with connect(receipt_db) as conn:
        rows = conn.execute(
            "select * from records where action_id = ? order by ordinal",
            (pending["action_id"],),
        ).fetchall()
        records = [row_to_record(row) for row in rows]
        for record in records:
            verify_record(record)
        previous = records[-1]
        body = record_body(
            ordinal=len(records) + 1,
            action_id=pending["action_id"],
            case_name=pending["case_name"],
            record_kind="RECONCILIATION",
            target=pending["target"],
            payload_digest=pending["payload_digest"],
            trace_id=pending["trace_id"],
            decision_id=pending["decision_id"],
            execution_id=pending["execution_id"],
            evidence_id=pending["evidence_id"],
            observation_availability=availability,
            external_outcome=external_outcome,
            externally_verified=externally_verified,
            effect_count=effect_count,
            continuity=continuity,
            recovery_decision=recovery_decision,
            previous_record_sha256=previous["record_sha256"],
        )
        record = insert_record(conn, body)
        conn.commit()
        conn.execute("pragma wal_checkpoint(FULL)")
    return record


def classify_full_readback(
    *,
    effect_db: Path,
    pending: dict[str, Any],
) -> dict[str, Any]:
    with connect(effect_db, readonly=True) as conn:
        rows = conn.execute(
            """
            select target, payload_digest, result
            from effects where action_id = ? order by seq
            """,
            (pending["action_id"],),
        ).fetchall()

    count = len(rows)
    if count == 0:
        return {
            "availability": "FULL",
            "external_outcome": "NO_EFFECT",
            "externally_verified": True,
            "effect_count": 0,
            "continuity": "FRESH_AUTHORIZATION_REQUIRED",
            "recovery_decision": "NO_REDISPATCH_FRESH_AUTHORIZATION_REQUIRED",
        }

    matching = all(
        str(row["target"]) == pending["target"]
        and str(row["payload_digest"]) == pending["payload_digest"]
        and str(row["result"]) == "effect-ok"
        for row in rows
    )

    if count == 1 and matching:
        return {
            "availability": "FULL",
            "external_outcome": "ONE_EFFECT_MATCHING",
            "externally_verified": True,
            "effect_count": 1,
            "continuity": "FINALIZE_EXISTING",
            "recovery_decision": "FINALIZE_EXISTING_NO_REDISPATCH",
        }

    if count == 1:
        return {
            "availability": "FULL",
            "external_outcome": "ONE_EFFECT_MISMATCHED",
            "externally_verified": True,
            "effect_count": 1,
            "continuity": "BLOCKED",
            "recovery_decision": "BLOCK_MISMATCH",
        }

    return {
        "availability": "FULL",
        "external_outcome": "MULTIPLE_EFFECTS",
        "externally_verified": True,
        "effect_count": count,
        "continuity": "BLOCKED",
        "recovery_decision": "BLOCK_MULTIPLE_EFFECTS",
    }


def recover(args: argparse.Namespace) -> int:
    receipt_db = Path(args.receipt_db)
    effect_db = Path(args.effect_db)
    pending = read_pending(receipt_db, args.action_id)

    if args.readback_mode == "unavailable":
        classification = {
            "availability": "UNAVAILABLE",
            "external_outcome": "INDETERMINATE",
            "externally_verified": False,
            "effect_count": None,
            "continuity": "REVALIDATE",
            "recovery_decision": "HOLD_REVALIDATE_NO_REDISPATCH",
        }
        readback_used = False
    else:
        classification = classify_full_readback(effect_db=effect_db, pending=pending)
        readback_used = True

    reconciliation = append_reconciliation(
        receipt_db=receipt_db,
        pending=pending,
        availability=classification["availability"],
        external_outcome=classification["external_outcome"],
        externally_verified=classification["externally_verified"],
        effect_count=classification["effect_count"],
        continuity=classification["continuity"],
        recovery_decision=classification["recovery_decision"],
    )

    output = {
        "system_case": SYSTEM_CASE,
        "status": "RECOVERED",
        "action_id": args.action_id,
        "readback_mode": args.readback_mode,
        "readback_used": readback_used,
        **classification,
        "reconciliation_record_sha256": reconciliation["record_sha256"],
    }
    print(json.dumps(output, sort_keys=True))
    return 0


def receipt_snapshot(path: Path, action_id: str) -> dict[str, Any]:
    with connect(path, readonly=True) as conn:
        rows = conn.execute(
            "select * from records where action_id = ? order by ordinal",
            (action_id,),
        ).fetchall()
        verifications = conn.execute(
            """
            select verification_kind, verified, observed_record_sha256
            from verifications where action_id = ? order by seq
            """,
            (action_id,),
        ).fetchall()

    records = [row_to_record(row) for row in rows]
    previous = None
    for record in records:
        verify_record(record)
        if record["previous_record_sha256"] != previous:
            fail("receipt/reconciliation hash chain discontinuity")
        previous = record["record_sha256"]

    return {
        "records": records,
        "fresh_pending_verifications": [
            {
                "kind": str(row["verification_kind"]),
                "verified": bool(row["verified"]),
                "observed_record_sha256": str(row["observed_record_sha256"]),
            }
            for row in verifications
        ],
    }


def stable_action_id(case_name: str) -> str:
    return "act_" + hashlib.sha256(f"{SYSTEM_CASE}|{case_name}".encode()).hexdigest()[:32]


def expected_payload_digest(case_name: str) -> str:
    cfg = CASE_CONFIG[case_name]
    return sha256_json(
        {
            "target": cfg["target"],
            "action": "provider.generate",
            "request": cfg["request"],
        }
    )


def run_process(argv: list[str], *, cwd: Path, expected: int) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if proc.returncode != expected:
        fail(
            "\n".join(
                [
                    f"unexpected subprocess return code expected={expected} actual={proc.returncode}",
                    f"argv={' '.join(argv)}",
                    f"stdout={proc.stdout.strip() or '<empty>'}",
                    f"stderr={proc.stderr.strip() or '<empty>'}",
                ]
            )
        )
    return proc


def parse_json_stdout(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    raw = proc.stdout.strip().splitlines()
    if not raw:
        fail("fresh recovery emitted no JSON")
    try:
        value = json.loads(raw[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            SYSTEM_CASE + ": invalid recovery JSON: " + repr(raw[-1])
        ) from exc
    if not isinstance(value, dict):
        fail("recovery output is not an object")
    return value


def run_case(
    *,
    case_name: str,
    subject_dir: Path,
    subject_script: str,
    work_dir: Path,
) -> dict[str, Any]:
    cfg = CASE_CONFIG[case_name]
    case_dir = work_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    receipt_db = case_dir / "receipt.sqlite"
    effect_db = case_dir / "receiver.sqlite"
    init_receipt_db(receipt_db)
    init_effect_db(effect_db)

    action_id = stable_action_id(case_name)
    payload_digest = expected_payload_digest(case_name)

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        fail("pnpm not found")

    subject_argv = [
        pnpm,
        "--filter",
        "@aegisora/runtime",
        "exec",
        "tsx",
        subject_script,
        "--case",
        case_name,
        "--action-id",
        action_id,
        "--receipt-db",
        str(receipt_db.resolve()),
        "--effect-db",
        str(effect_db.resolve()),
        "--helper",
        str(Path(__file__).resolve()),
        "--payload-digest",
        payload_digest,
    ]

    subject = run_process(
        subject_argv,
        cwd=subject_dir,
        expected=-int(signal.SIGKILL),
    )

    before_receipt = receipt_snapshot(receipt_db, action_id)
    before_effect = raw_effect_snapshot(effect_db, action_id)

    if len(before_receipt["records"]) != 1:
        fail(f"{case_name}: expected exactly durable PENDING before recovery")
    pending = before_receipt["records"][0]
    if pending["record_kind"] != "PENDING":
        fail(f"{case_name}: durable first record is not PENDING")
    if len(before_receipt["fresh_pending_verifications"]) != 1:
        fail(f"{case_name}: PENDING was not independently re-read before dispatch")
    if not before_receipt["fresh_pending_verifications"][0]["verified"]:
        fail(f"{case_name}: fresh PENDING verification failed")
    if before_effect["attempt_count"] != 1:
        fail(f"{case_name}: provider attempt count before recovery must be 1")

    if case_name == "crash_before_effect":
        if before_effect["effect_count"] != 0:
            fail("crash_before_effect unexpectedly retained an effect")
    else:
        if before_effect["effect_count"] != 1:
            fail(f"{case_name}: expected one retained external effect")
        if len(before_effect["fresh_effect_verifications"]) != 1:
            fail(f"{case_name}: effect was not independently re-read before kill")

    helper = str(Path(__file__).resolve())

    def fresh_recover(mode: str) -> dict[str, Any]:
        proc = run_process(
            [
                sys.executable,
                helper,
                "recover",
                "--receipt-db",
                str(receipt_db),
                "--effect-db",
                str(effect_db),
                "--action-id",
                action_id,
                "--readback-mode",
                mode,
            ],
            cwd=Path.cwd(),
            expected=0,
        )
        return parse_json_stdout(proc)

    recoveries: list[dict[str, Any]] = []

    if case_name == "unavailable_readback":
        first = fresh_recover("unavailable")
        recoveries.append(first)
        mid_effect = raw_effect_snapshot(effect_db, action_id)
        if mid_effect["attempt_count"] != 1 or mid_effect["effect_count"] != 1:
            fail("UNAVAILABLE recovery caused redispatch or effect drift")

        second = fresh_recover("full")
        recoveries.append(second)
    else:
        recoveries.append(fresh_recover("full"))

    after_receipt = receipt_snapshot(receipt_db, action_id)
    after_effect = raw_effect_snapshot(effect_db, action_id)

    if after_effect["attempt_count"] != 1:
        fail(f"{case_name}: recovery implicitly redispatched provider")
    if after_effect["effect_count"] != before_effect["effect_count"]:
        fail(f"{case_name}: recovery changed external effect count")

    if case_name == "effect_then_crash":
        final = recoveries[-1]
        passed = (
            final["external_outcome"] == "ONE_EFFECT_MATCHING"
            and final["continuity"] == "FINALIZE_EXISTING"
            and final["recovery_decision"] == "FINALIZE_EXISTING_NO_REDISPATCH"
            and final["effect_count"] == 1
            and len(after_receipt["records"]) == 2
        )
        verdict = "CONFIRMED_EFFECT_FINALIZED"
    elif case_name == "crash_before_effect":
        final = recoveries[-1]
        passed = (
            final["external_outcome"] == "NO_EFFECT"
            and final["continuity"] == "FRESH_AUTHORIZATION_REQUIRED"
            and final["recovery_decision"] == "NO_REDISPATCH_FRESH_AUTHORIZATION_REQUIRED"
            and final["effect_count"] == 0
            and len(after_receipt["records"]) == 2
        )
        verdict = "VERIFIED_NO_EFFECT_FRESH_AUTH_REQUIRED"
    else:
        first, second = recoveries
        passed = (
            first["external_outcome"] == "INDETERMINATE"
            and first["continuity"] == "REVALIDATE"
            and first["effect_count"] is None
            and first["readback_used"] is False
            and second["external_outcome"] == "ONE_EFFECT_MATCHING"
            and second["continuity"] == "FINALIZE_EXISTING"
            and second["effect_count"] == 1
            and after_effect["effect_count"] == 1
            and len(after_receipt["records"]) == 3
        )
        verdict = "UNAVAILABLE_REVALIDATE_THEN_CONFIRMED"

    return {
        "case": case_name,
        "passed": passed,
        "verdict": verdict if passed else "UNEXPECTED",
        "action_id": action_id,
        "target": cfg["target"],
        "payload_digest": payload_digest,
        "subject_returncode": subject.returncode,
        "subject_stdout": subject.stdout,
        "subject_stderr": subject.stderr,
        "before_recovery": {
            "receipt": before_receipt,
            "receiver": before_effect,
        },
        "recoveries": recoveries,
        "after_recovery": {
            "receipt": after_receipt,
            "receiver": after_effect,
        },
    }


def run(args: argparse.Namespace) -> int:
    subject_dir = Path(args.subject_dir).resolve()
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    cases = {
        case_name: run_case(
            case_name=case_name,
            subject_dir=subject_dir,
            subject_script=args.subject_script,
            work_dir=work_dir,
        )
        for case_name in CASES
    }

    all_pass = all(case["passed"] for case in cases.values())

    report = {
        "schema": SCHEMA,
        "system_case": SYSTEM_CASE,
        "status": "PASS" if all_pass else "FAIL",
        "barrier": "durable_pending_then_real_process_sigkill_before_terminal",
        "source_runtime": {
            "repository": "aegisora-ai/aegisora",
            "commit": "2bac618215671f6f0ac8ebddf169830d4fc0f9b3",
        },
        "storage": {
            "receipt": "SQLite WAL + synchronous=FULL + checkpoint; process-crash scope only",
            "receiver": "separate SQLite WAL + synchronous=FULL receiver ledger",
        },
        "cases": cases,
        "invariants": [
            "PENDING is durably committed and independently re-read before provider dispatch.",
            "Recovery never dispatches the provider from PENDING alone.",
            "FULL + ONE_EFFECT_MATCHING finalizes the existing action without redispatch.",
            "FULL + NO_EFFECT does not retry automatically; it requires fresh authorization.",
            "UNAVAILABLE remains INDETERMINATE / REVALIDATE even when the fixture ledger actually contains an effect.",
            "Later FULL readback may resolve the same PENDING action without creating a second effect.",
        ],
        "claim_ceiling": [
            "Real OS-process SIGKILL boundary, not host/power-loss durability.",
            "SQLite same-host fixture, not distributed consensus or Byzantine storage.",
            "Receiver ledger is authoritative only for this harmless local fixture.",
            "NO_EFFECT authorizes no dispatch by itself; fresh authorization remains separate.",
            "No production provider, recipient identity, payment, or settlement binding.",
        ],
    }

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        path = Path(args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    print("REPORT_JSON=" + json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if all_pass else 1


def add_common_db_args(parser: argparse.ArgumentParser, *, effect: bool = False) -> None:
    parser.add_argument("--action-id", required=True)
    if effect:
        parser.add_argument("--effect-db", required=True)
    else:
        parser.add_argument("--receipt-db", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pending-write")
    add_common_db_args(p)
    p.add_argument("--case", required=True, choices=CASES)
    p.add_argument("--target", required=True)
    p.add_argument("--payload-digest", required=True)
    p.add_argument("--trace-id", required=True)
    p.add_argument("--decision-id", required=True)
    p.add_argument("--execution-id", required=True)
    p.add_argument("--evidence-id", required=True)
    p.set_defaults(func=pending_write)

    p = sub.add_parser("pending-verify")
    add_common_db_args(p)
    p.set_defaults(func=pending_verify)

    p = sub.add_parser("attempt-write")
    add_common_db_args(p, effect=True)
    p.add_argument("--case", required=True, choices=CASES)
    p.add_argument("--target", required=True)
    p.add_argument("--payload-digest", required=True)
    p.set_defaults(func=attempt_write)

    p = sub.add_parser("effect-write")
    add_common_db_args(p, effect=True)
    p.add_argument("--case", required=True, choices=CASES)
    p.add_argument("--target", required=True)
    p.add_argument("--payload-digest", required=True)
    p.set_defaults(func=effect_write)

    p = sub.add_parser("effect-verify")
    add_common_db_args(p, effect=True)
    p.add_argument("--expected-count", type=int, required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--payload-digest", required=True)
    p.set_defaults(func=effect_verify)

    p = sub.add_parser("recover")
    p.add_argument("--receipt-db", required=True)
    p.add_argument("--effect-db", required=True)
    p.add_argument("--action-id", required=True)
    p.add_argument("--readback-mode", choices=("full", "unavailable"), required=True)
    p.set_defaults(func=recover)

    p = sub.add_parser("run")
    p.add_argument("--subject-dir", required=True)
    p.add_argument("--subject-script", required=True)
    p.add_argument("--work-dir", required=True)
    p.add_argument("--write-report")
    p.set_defaults(func=run)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
