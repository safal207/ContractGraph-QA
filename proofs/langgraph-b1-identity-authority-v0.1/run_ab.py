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
from typing import Any, TypedDict

TARGET = "local-sqlite-target"
RESULT = "external-effect-ok"
_STATE = {"effect_done": False, "crashed": False}


class GraphState(TypedDict):
    done: bool


def stable_action_id(arm: str) -> str:
    raw = f"langgraph-b1|{arm}|append-marker|{TARGET}".encode()
    return "act_" + hashlib.sha256(raw).hexdigest()[:32]


def stable_permit_id(action_id: str) -> str:
    return "permit_" + hashlib.sha256(f"{action_id}|1".encode()).hexdigest()[:24]


def init_external(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table if not exists entries (
                seq integer primary key autoincrement,
                arm text not null,
                action_id text not null
            );
            create table if not exists decisions (
                seq integer primary key autoincrement,
                arm text not null,
                action_id text not null,
                decision text not null
            );
            create table if not exists effects (
                seq integer primary key autoincrement,
                arm text not null,
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
                result text not null
            );
            """
        )


def record_entry(path: Path, arm: str, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into entries(arm, action_id) values (?, ?)",
            (arm, action_id),
        )


def record_decision(path: Path, arm: str, action_id: str, decision: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into decisions(arm, action_id, decision) values (?, ?, ?)",
            (arm, action_id, decision),
        )


def read_receipt(path: Path, action_id: str) -> tuple[str, str] | None:
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "select target, result from receipts where action_id = ?",
            (action_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row[0]), str(row[1])


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


def commit_effect(path: Path, arm: str, action_id: str, *, write_receipt: bool) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into effects(arm, action_id, target, result) values (?, ?, ?, ?)",
            (arm, action_id, TARGET, RESULT),
        )
        if write_receipt:
            conn.execute(
                "insert into receipts(action_id, target, result) values (?, ?, ?)",
                (action_id, TARGET, RESULT),
            )


def reset_process_state() -> None:
    _STATE.update({"effect_done": False, "crashed": False})


def build_app(checkpoint: str, external_db: str, arm: str, *, crash_enabled: bool) -> Any:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    class B1Saver(SqliteSaver):
        def put_writes(self, *args: Any, **kwargs: Any) -> Any:
            if crash_enabled and _STATE["effect_done"] and not _STATE["crashed"]:
                _STATE["crashed"] = True
                os.kill(os.getpid(), signal.SIGKILL)
            return super().put_writes(*args, **kwargs)

    external = Path(external_db)
    action_id = stable_action_id(arm)

    def node(_state: GraphState) -> GraphState:
        record_entry(external, arm, action_id)

        if arm == "guarded":
            receipt = read_receipt(external, action_id)
            if receipt is not None:
                if receipt != (TARGET, RESULT):
                    raise RuntimeError("receipt target/result mismatch")
                record_decision(external, arm, action_id, "return_prior")
                return {"done": True}

            ensure_and_consume_permit(external, action_id)
            record_decision(external, arm, action_id, "dispatch")
            commit_effect(external, arm, action_id, write_receipt=True)
        elif arm == "baseline":
            record_decision(external, arm, action_id, "dispatch")
            commit_effect(external, arm, action_id, write_receipt=False)
        else:
            raise ValueError(f"unknown arm: {arm}")

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


def phase_subject(checkpoint: str, external_db: str, arm: str) -> int:
    reset_process_state()
    app = build_app(checkpoint, external_db, arm, crash_enabled=True)
    config = {"configurable": {"thread_id": f"langgraph-b1-{arm}"}}
    app.invoke({"done": False}, config, durability="sync")
    return 0


def phase_recovery(checkpoint: str, external_db: str, arm: str) -> int:
    reset_process_state()
    app = build_app(checkpoint, external_db, arm, crash_enabled=False)
    config = {"configurable": {"thread_id": f"langgraph-b1-{arm}"}}
    out = app.invoke(None, config, durability="sync")
    print(json.dumps({"returned": out}, sort_keys=True), flush=True)
    return 0


def checkpoint_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        checkpoints = conn.execute("select count(*) from checkpoints").fetchone()
        writes = conn.execute("select count(*) from writes").fetchone()
    return {
        "checkpoints": int(checkpoints[0]) if checkpoints else 0,
        "writes": int(writes[0]) if writes else 0,
    }


def snapshot(path: Path, arm: str) -> dict[str, object]:
    with sqlite3.connect(path) as conn:
        entries = conn.execute(
            "select action_id from entries where arm = ? order by seq", (arm,)
        ).fetchall()
        decisions = conn.execute(
            "select decision from decisions where arm = ? order by seq", (arm,)
        ).fetchall()
        effects = conn.execute(
            "select action_id, target, result from effects where arm = ? order by seq", (arm,)
        ).fetchall()
        permit = conn.execute(
            "select permit_id, consumed, consume_count from permits where action_id = ?",
            (stable_action_id(arm),),
        ).fetchone()
        receipt = conn.execute(
            "select target, result from receipts where action_id = ?",
            (stable_action_id(arm),),
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
        else {"target": str(receipt[0]), "result": str(receipt[1])},
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


def run_arm(root: Path, arm: str) -> dict[str, object]:
    checkpoint = root / f"checkpoint-{arm}.sqlite"
    external = root / f"external-{arm}.sqlite"
    init_external(external)

    base_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--checkpoint",
        str(checkpoint),
        "--external-db",
        str(external),
        "--arm",
        arm,
    ]
    subject = run_process([*base_args, "--phase", "subject"], -int(signal.SIGKILL))
    before = snapshot(external, arm)
    checkpoint_before = checkpoint_counts(checkpoint)
    recovery = run_process([*base_args, "--phase", "recovery"], 0)
    after = snapshot(external, arm)
    checkpoint_after = checkpoint_counts(checkpoint)

    if arm == "baseline":
        passed = (
            before["node_entries"] == 1
            and before["effect_count"] == 1
            and after["node_entries"] == 2
            and after["effect_count"] == 2
            and after["decisions"] == ["dispatch", "dispatch"]
            and after["action_ids"] == [stable_action_id(arm), stable_action_id(arm)]
        )
        verdict = "DUPLICATED" if passed else "UNEXPECTED"
    else:
        permit = after["permit"]
        passed = (
            before["node_entries"] == 1
            and before["effect_count"] == 1
            and after["node_entries"] == 2
            and after["effect_count"] == 1
            and after["decisions"] == ["dispatch", "return_prior"]
            and after["action_ids"] == [stable_action_id(arm), stable_action_id(arm)]
            and isinstance(permit, dict)
            and permit.get("consumed") is True
            and permit.get("consume_count") == 1
            and after["receipt"] == {"target": TARGET, "result": RESULT}
        )
        verdict = "RECONCILED_NO_DUPLICATE" if passed else "UNEXPECTED"

    return {
        "arm": arm,
        "passed": passed,
        "verdict": verdict,
        "subject_returncode": subject.returncode,
        "recovery_returncode": recovery.returncode,
        "before_recovery": before,
        "after_recovery": after,
        "checkpoint_before_recovery": checkpoint_before,
        "checkpoint_after_recovery": checkpoint_after,
    }


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        baseline = run_arm(root, "baseline")
        guarded = run_arm(root, "guarded")

    report: dict[str, object] = {
        "schema": "contractgraph.langgraph-b1-identity-authority.v0.1",
        "runtime": {
            "langgraph": importlib.metadata.version("langgraph"),
            "langgraph_checkpoint_sqlite": importlib.metadata.version(
                "langgraph-checkpoint-sqlite"
            ),
        },
        "barrier": "b1_after_effect_before_pending_writes",
        "external_reference": {
            "repository": "mstevens843/crashpoint",
            "commit": "606893ebb353df5dab3ac68738051eb5fbb7286e",
            "adapter_blob": "9dea189cae3ebbcc573786c1df878094c61207fd",
        },
        "claim": (
            "on the pinned local LangGraph b1 recovery boundary, external receipt reconciliation "
            "preserves stable action identity while preventing persisted/recovered state from "
            "becoming authority for a second side effect"
        ),
        "arms": {"baseline": baseline, "guarded": guarded},
        "all_pass": bool(baseline["passed"] and guarded["passed"]),
        "non_claims": [
            "does not reproduce the LangGraph Cloud sweeper or its approximately 180-second timing",
            "does not prove global exactly-once execution",
            "does not prove distributed authorization or consensus",
            "does not prove external target availability or Byzantine correctness",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("subject", "recovery"))
    ap.add_argument("--checkpoint")
    ap.add_argument("--external-db")
    ap.add_argument("--arm", choices=("baseline", "guarded"))
    ap.add_argument("--write-report")
    args = ap.parse_args(argv)

    if args.phase:
        if not args.checkpoint or not args.external_db or not args.arm:
            ap.error("--phase requires --checkpoint, --external-db and --arm")
        if args.phase == "subject":
            return phase_subject(args.checkpoint, args.external_db, args.arm)
        return phase_recovery(args.checkpoint, args.external_db, args.arm)

    report = run()
    compact = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print("REPORT_JSON=" + compact)
    if args.write_report:
        Path(args.write_report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
