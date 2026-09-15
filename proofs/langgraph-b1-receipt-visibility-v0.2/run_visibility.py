from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal, TypedDict

TARGET = "local-sqlite-target"
WRONG_TARGET = "other-sqlite-target"
RESULT = "external-effect-ok"
_STATE = {"effect_done": False, "crashed": False}

Case = Literal["confirmed", "delayed", "mismatch"]
CASES: tuple[Case, ...] = ("confirmed", "delayed", "mismatch")


class UnknownReceiptError(RuntimeError):
    pass


class ReceiptMismatchError(RuntimeError):
    pass


class GraphState(TypedDict):
    done: bool


def stable_action_id(case: str) -> str:
    raw = f"langgraph-b1-receipt-v0.2|{case}|append-marker|{TARGET}".encode()
    return "act_" + hashlib.sha256(raw).hexdigest()[:32]


def stable_permit_id(action_id: str) -> str:
    return "permit_" + hashlib.sha256(f"{action_id}|1".encode()).hexdigest()[:24]


def init_external(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table if not exists entries (
                seq integer primary key autoincrement,
                case_name text not null,
                action_id text not null
            );
            create table if not exists decisions (
                seq integer primary key autoincrement,
                case_name text not null,
                action_id text not null,
                decision text not null
            );
            create table if not exists effects (
                seq integer primary key autoincrement,
                case_name text not null,
                action_id text not null,
                target text not null,
                result text not null
            );
            create table if not exists permits (
                action_id text primary key,
                permit_id text not null,
                consumed integer not null default 0,
                consume_count integer not null default 0
            );
            create table if not exists receipts (
                action_id text primary key,
                target text not null,
                result text not null,
                visible integer not null check (visible in (0,1))
            );
            """
        )


def record_entry(path: Path, case: str, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into entries(case_name, action_id) values (?, ?)",
            (case, action_id),
        )


def record_decision(path: Path, case: str, action_id: str, decision: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into decisions(case_name, action_id, decision) values (?, ?, ?)",
            (case, action_id, decision),
        )


def ensure_and_consume_permit(path: Path, action_id: str) -> str:
    permit_id = stable_permit_id(action_id)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert or ignore into permits(action_id, permit_id) values (?, ?)",
            (action_id, permit_id),
        )
        row = conn.execute(
            "select permit_id, consumed, consume_count from permits where action_id = ?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("permit disappeared")
        if int(row[1]) != 0:
            raise RuntimeError("consumed permit cannot authorize redispatch")
        updated = conn.execute(
            "update permits set consumed = 1, consume_count = consume_count + 1 "
            "where action_id = ? and consumed = 0",
            (action_id,),
        ).rowcount
        if updated != 1:
            raise RuntimeError("one-use permit consumption race")
    return permit_id


def commit_effect(path: Path, case: Case, action_id: str) -> None:
    if case == "confirmed":
        receipt_target = TARGET
        visible = 1
    elif case == "delayed":
        receipt_target = TARGET
        visible = 0
    elif case == "mismatch":
        receipt_target = WRONG_TARGET
        visible = 1
    else:
        raise ValueError(case)

    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into effects(case_name, action_id, target, result) values (?, ?, ?, ?)",
            (case, action_id, TARGET, RESULT),
        )
        conn.execute(
            "insert into receipts(action_id, target, result, visible) values (?, ?, ?, ?)",
            (action_id, receipt_target, RESULT, visible),
        )


def set_receipt_visible(path: Path, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        updated = conn.execute(
            "update receipts set visible = 1 where action_id = ?",
            (action_id,),
        ).rowcount
        if updated != 1:
            raise RuntimeError("receipt visibility update failed")


def reconcile_receipt(path: Path, action_id: str) -> tuple[str, tuple[str, str] | None]:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "select target, result, visible from receipts where action_id = ?",
            (action_id,),
        ).fetchone()
    if row is None or int(row[2]) == 0:
        return "UNKNOWN", None
    receipt = (str(row[0]), str(row[1]))
    if receipt != (TARGET, RESULT):
        return "MISMATCH", receipt
    return "CONFIRMED", receipt


def reset_process_state() -> None:
    _STATE.update({"effect_done": False, "crashed": False})


def build_app(checkpoint: str, external_db: str, case: Case, *, crash_enabled: bool) -> Any:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    class B1Saver(SqliteSaver):
        def put_writes(self, *args: Any, **kwargs: Any) -> Any:
            if crash_enabled and _STATE["effect_done"] and not _STATE["crashed"]:
                _STATE["crashed"] = True
                os.kill(os.getpid(), signal.SIGKILL)
            return super().put_writes(*args, **kwargs)

    external = Path(external_db)
    action_id = stable_action_id(case)

    def node(_state: GraphState) -> GraphState:
        record_entry(external, case, action_id)
        status, receipt = reconcile_receipt(external, action_id)

        if status == "CONFIRMED":
            record_decision(external, case, action_id, "return_prior")
            return {"done": True}
        if status == "MISMATCH":
            record_decision(external, case, action_id, "fail_closed_mismatch")
            raise ReceiptMismatchError(f"receipt mismatch: {receipt!r}")
        if status != "UNKNOWN":
            raise RuntimeError(f"unexpected reconciliation state: {status}")

        # UNKNOWN is only safe to dispatch before the first effect, while a fresh
        # permit still exists. After the subject crash the same permit is consumed;
        # recovery must fail closed instead of converting missing visibility into
        # new execution authority.
        with sqlite3.connect(external) as conn:
            permit_row = conn.execute(
                "select consumed from permits where action_id = ?", (action_id,)
            ).fetchone()
        if permit_row is not None and int(permit_row[0]) == 1:
            record_decision(external, case, action_id, "fail_closed_unknown")
            raise UnknownReceiptError("external effect state is UNKNOWN")

        ensure_and_consume_permit(external, action_id)
        record_decision(external, case, action_id, "dispatch")
        commit_effect(external, case, action_id)
        _STATE["effect_done"] = True
        return {"done": True}

    graph = StateGraph(GraphState)
    graph.add_node("effect", node)
    graph.add_edge(START, "effect")
    graph.add_edge("effect", END)

    conn = sqlite3.connect(checkpoint, check_same_thread=False)
    saver = B1Saver(conn)
    saver.setup()
    return graph.compile(checkpointer=saver)


def phase_subject(checkpoint: str, external_db: str, case: Case) -> int:
    reset_process_state()
    app = build_app(checkpoint, external_db, case, crash_enabled=True)
    config = {"configurable": {"thread_id": f"langgraph-b1-receipt-{case}"}}
    app.invoke({"done": False}, config, durability="sync")
    return 0


def phase_recovery(checkpoint: str, external_db: str, case: Case) -> int:
    reset_process_state()
    app = build_app(checkpoint, external_db, case, crash_enabled=False)
    config = {"configurable": {"thread_id": f"langgraph-b1-receipt-{case}"}}
    try:
        out = app.invoke(None, config, durability="sync")
    except UnknownReceiptError:
        print(json.dumps({"status": "BLOCKED_UNKNOWN"}, sort_keys=True), flush=True)
        return 0
    except ReceiptMismatchError:
        print(json.dumps({"status": "BLOCKED_MISMATCH"}, sort_keys=True), flush=True)
        return 0
    print(json.dumps({"status": "COMPLETED", "returned": out}, sort_keys=True), flush=True)
    return 0


def checkpoint_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        checkpoints = conn.execute("select count(*) from checkpoints").fetchone()
        writes = conn.execute("select count(*) from writes").fetchone()
    return {
        "checkpoints": int(checkpoints[0]) if checkpoints else 0,
        "writes": int(writes[0]) if writes else 0,
    }


def snapshot(path: Path, case: Case) -> dict[str, object]:
    action_id = stable_action_id(case)
    with sqlite3.connect(path) as conn:
        entries = conn.execute(
            "select action_id from entries where case_name = ? order by seq", (case,)
        ).fetchall()
        decisions = conn.execute(
            "select decision from decisions where case_name = ? order by seq", (case,)
        ).fetchall()
        effects = conn.execute(
            "select action_id, target, result from effects where case_name = ? order by seq", (case,)
        ).fetchall()
        permit = conn.execute(
            "select permit_id, consumed, consume_count from permits where action_id = ?",
            (action_id,),
        ).fetchone()
        receipt = conn.execute(
            "select target, result, visible from receipts where action_id = ?",
            (action_id,),
        ).fetchone()

    return {
        "node_entries": len(entries),
        "action_ids": [str(row[0]) for row in entries],
        "decisions": [str(row[0]) for row in decisions],
        "effect_count": len(effects),
        "effects": [
            {"action_id": str(row[0]), "target": str(row[1]), "result": str(row[2])}
            for row in effects
        ],
        "permit": None
        if permit is None
        else {
            "permit_id": str(permit[0]),
            "consumed": bool(permit[1]),
            "consume_count": int(permit[2]),
        },
        "receipt": None
        if receipt is None
        else {
            "target": str(receipt[0]),
            "result": str(receipt[1]),
            "visible": bool(receipt[2]),
        },
    }


def run_process(args: list[str], expected: int) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, text=True, capture_output=True, check=False, timeout=60)
    if proc.returncode != expected:
        raise RuntimeError(
            "\n".join(
                [
                    f"unexpected subprocess return code: expected={expected} actual={proc.returncode}",
                    f"argv={' '.join(args)}",
                    f"stdout={proc.stdout.strip() or '<empty>'}",
                    f"stderr={proc.stderr.strip() or '<empty>'}",
                ]
            )
        )
    return proc


def recovery_status(proc: subprocess.CompletedProcess[str]) -> str:
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid recovery JSON: {proc.stdout!r}") from exc
    return str(payload.get("status", "")) if isinstance(payload, dict) else ""


def run_case(root: Path, case: Case) -> dict[str, object]:
    checkpoint = root / f"checkpoint-{case}.sqlite"
    external = root / f"external-{case}.sqlite"
    init_external(external)

    base_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--checkpoint",
        str(checkpoint),
        "--external-db",
        str(external),
        "--case",
        case,
    ]
    subject = run_process([*base_args, "--phase", "subject"], -int(signal.SIGKILL))
    before = snapshot(external, case)
    checkpoint_before = checkpoint_counts(checkpoint)

    first_recovery = run_process([*base_args, "--phase", "recovery"], 0)
    first_status = recovery_status(first_recovery)
    after_first = snapshot(external, case)
    checkpoint_after_first = checkpoint_counts(checkpoint)

    second_status: str | None = None
    after_second: dict[str, object] | None = None
    checkpoint_after_second: dict[str, int] | None = None
    if case == "delayed":
        set_receipt_visible(external, stable_action_id(case))
        second_recovery = run_process([*base_args, "--phase", "recovery"], 0)
        second_status = recovery_status(second_recovery)
        after_second = snapshot(external, case)
        checkpoint_after_second = checkpoint_counts(checkpoint)

    permit = (after_second or after_first)["permit"]
    permit_ok = (
        isinstance(permit, dict)
        and permit.get("consumed") is True
        and permit.get("consume_count") == 1
    )
    action_id = stable_action_id(case)

    if case == "confirmed":
        passed = (
            before["effect_count"] == 1
            and before["node_entries"] == 1
            and first_status == "COMPLETED"
            and after_first["effect_count"] == 1
            and after_first["node_entries"] == 2
            and after_first["decisions"] == ["dispatch", "return_prior"]
            and after_first["action_ids"] == [action_id, action_id]
            and permit_ok
        )
        verdict = "CONFIRMED_RETURN_PRIOR" if passed else "UNEXPECTED"
    elif case == "delayed":
        assert after_second is not None
        passed = (
            before["effect_count"] == 1
            and before["node_entries"] == 1
            and first_status == "BLOCKED_UNKNOWN"
            and after_first["effect_count"] == 1
            and after_first["node_entries"] == 2
            and after_first["decisions"] == ["dispatch", "fail_closed_unknown"]
            and second_status == "COMPLETED"
            and after_second["effect_count"] == 1
            and after_second["node_entries"] == 3
            and after_second["decisions"]
            == ["dispatch", "fail_closed_unknown", "return_prior"]
            and after_second["action_ids"] == [action_id, action_id, action_id]
            and permit_ok
        )
        verdict = "UNKNOWN_BLOCKED_THEN_CONFIRMED" if passed else "UNEXPECTED"
    else:
        passed = (
            before["effect_count"] == 1
            and before["node_entries"] == 1
            and first_status == "BLOCKED_MISMATCH"
            and after_first["effect_count"] == 1
            and after_first["node_entries"] == 2
            and after_first["decisions"] == ["dispatch", "fail_closed_mismatch"]
            and after_first["action_ids"] == [action_id, action_id]
            and permit_ok
        )
        verdict = "MISMATCH_FAIL_CLOSED" if passed else "UNEXPECTED"

    return {
        "case": case,
        "passed": passed,
        "verdict": verdict,
        "subject_returncode": subject.returncode,
        "first_recovery_status": first_status,
        "second_recovery_status": second_status,
        "before_recovery": before,
        "after_first_recovery": after_first,
        "after_second_recovery": after_second,
        "checkpoint_before_recovery": checkpoint_before,
        "checkpoint_after_first_recovery": checkpoint_after_first,
        "checkpoint_after_second_recovery": checkpoint_after_second,
    }


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        results = {case: run_case(root, case) for case in CASES}

    return {
        "schema": "contractgraph.langgraph-b1-receipt-visibility.v0.2",
        "runtime": {
            "langgraph": importlib.metadata.version("langgraph"),
            "langgraph_checkpoint_sqlite": importlib.metadata.version(
                "langgraph-checkpoint-sqlite"
            ),
        },
        "barrier": "b1_after_effect_before_pending_writes",
        "predecessor": "proofs/langgraph-b1-identity-authority-v0.1",
        "claim": (
            "on the pinned LangGraph b1 recovery boundary, absent or mismatching external "
            "commit visibility is not converted into redispatch authority; UNKNOWN blocks "
            "recovery until the original matching receipt becomes visible"
        ),
        "cases": results,
        "all_pass": all(bool(result["passed"]) for result in results.values()),
        "non_claims": [
            "does not reproduce LangGraph Cloud sweeper timing",
            "does not prove arbitrary eventual-consistency behavior",
            "does not prove Byzantine receipt-provider correctness",
            "does not prove global exactly-once execution",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("subject", "recovery"))
    ap.add_argument("--checkpoint")
    ap.add_argument("--external-db")
    ap.add_argument("--case", choices=CASES)
    ap.add_argument("--write-report")
    args = ap.parse_args(argv)

    if args.phase:
        if not args.checkpoint or not args.external_db or not args.case:
            ap.error("--phase requires --checkpoint, --external-db and --case")
        if args.phase == "subject":
            return phase_subject(args.checkpoint, args.external_db, args.case)
        return phase_recovery(args.checkpoint, args.external_db, args.case)

    report = run()
    compact = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print("REPORT_JSON=" + compact)
    if args.write_report:
        Path(args.write_report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
