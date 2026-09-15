from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

Arm = Literal["baseline", "guarded"]
ARMS: tuple[Arm, ...] = ("baseline", "guarded")
CRASH_EXIT = 79
RESULT = "external-effect-ok"


class State(TypedDict, total=False):
    action_id: str
    prepared: bool
    done: bool
    result: str


def init_store(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table if not exists permits (
                action_id text primary key,
                permit_id text not null,
                consumed integer not null check (consumed in (0,1))
            );
            create table if not exists effects (
                seq integer primary key autoincrement,
                action_id text not null,
                phase text not null
            );
            create table if not exists receipts (
                action_id text primary key,
                result text not null
            );
            create table if not exists events (
                seq integer primary key autoincrement,
                action_id text not null,
                phase text not null,
                event text not null
            );
            """
        )


def issue_permit(path: Path, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into permits(action_id, permit_id, consumed) values (?, ?, 0)",
            (action_id, f"permit:{action_id}"),
        )
        conn.execute(
            "insert into events(action_id, phase, event) values (?, 'driver', 'permit_issued')",
            (action_id,),
        )


def record_event(path: Path, action_id: str, phase: str, event: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into events(action_id, phase, event) values (?, ?, ?)",
            (action_id, phase, event),
        )


def baseline_dispatch(path: Path, action_id: str, phase: str) -> str:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into effects(action_id, phase) values (?, ?)",
            (action_id, phase),
        )
        conn.execute(
            "insert into events(action_id, phase, event) values (?, ?, 'dispatch')",
            (action_id, phase),
        )
    return RESULT


def guarded_decide(path: Path, action_id: str, phase: str) -> tuple[str, str]:
    """Reconcile first; dispatch only under fresh unconsumed authority."""
    with sqlite3.connect(path) as conn:
        conn.execute("begin immediate")
        receipt = conn.execute(
            "select result from receipts where action_id = ?", (action_id,)
        ).fetchone()
        if receipt is not None:
            result = str(receipt[0])
            conn.execute(
                "insert into events(action_id, phase, event) values (?, ?, 'return_prior')",
                (action_id, phase),
            )
            conn.commit()
            return "return_prior", result

        permit = conn.execute(
            "select consumed from permits where action_id = ?", (action_id,)
        ).fetchone()
        if permit is None or int(permit[0]) != 0:
            conn.execute(
                "insert into events(action_id, phase, event) values (?, ?, 'fail_closed')",
                (action_id, phase),
            )
            conn.commit()
            raise RuntimeError("no fresh execution authority")

        conn.execute(
            "update permits set consumed = 1 where action_id = ? and consumed = 0",
            (action_id,),
        )
        conn.execute(
            "insert into effects(action_id, phase) values (?, ?)",
            (action_id, phase),
        )
        conn.execute(
            "insert into receipts(action_id, result) values (?, ?)",
            (action_id, RESULT),
        )
        conn.execute(
            "insert into events(action_id, phase, event) values (?, ?, 'dispatch')",
            (action_id, phase),
        )
        conn.commit()
        return "dispatch", RESULT


def build_app(checkpoint_path: Path, store_path: Path, arm: Arm, phase: str, crash: bool) -> Any:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    def prepare(state: State) -> State:
        # This node exists to force a durable checkpoint containing action_id
        # before the side-effecting node begins.
        return {"prepared": True, "action_id": state["action_id"]}

    def effect(state: State) -> State:
        action_id = state["action_id"]
        record_event(store_path, action_id, phase, "effect_enter")
        if arm == "baseline":
            result = baseline_dispatch(store_path, action_id, phase)
        else:
            _decision, result = guarded_decide(store_path, action_id, phase)

        if crash:
            # External store transactions above are committed. Exit before this
            # node returns, so its completion is not checkpointed.
            os._exit(CRASH_EXIT)
        return {"done": True, "result": result, "action_id": action_id}

    graph: Any = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("effect", effect)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "effect")
    graph.add_edge("effect", END)

    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return graph.compile(checkpointer=saver)


def subject(checkpoint: Path, store: Path, arm: Arm, thread_id: str, action_id: str) -> int:
    app = build_app(checkpoint, store, arm, "subject", crash=True)
    config = {"configurable": {"thread_id": thread_id}}
    app.invoke(
        cast(State, {"action_id": action_id, "prepared": False, "done": False}),
        config,
        durability="sync",
    )
    raise AssertionError("subject should exit abruptly")


def recovery(checkpoint: Path, store: Path, arm: Arm, thread_id: str) -> int:
    app = build_app(checkpoint, store, arm, "recovery", crash=False)
    config = {"configurable": {"thread_id": thread_id}}
    returned = app.invoke(None, config, durability="sync")
    if not isinstance(returned, dict) or returned.get("done") is not True:
        raise RuntimeError(f"unexpected recovery result: {returned!r}")
    if returned.get("result") != RESULT:
        raise RuntimeError(f"unexpected recovery effect result: {returned!r}")
    return 0


def snapshot_store(path: Path, action_id: str) -> dict[str, object]:
    with sqlite3.connect(path) as conn:
        effects = conn.execute(
            "select phase from effects where action_id = ? order by seq", (action_id,)
        ).fetchall()
        events = conn.execute(
            "select phase, event from events where action_id = ? order by seq", (action_id,)
        ).fetchall()
        permit = conn.execute(
            "select consumed from permits where action_id = ?", (action_id,)
        ).fetchone()
        receipt = conn.execute(
            "select result from receipts where action_id = ?", (action_id,)
        ).fetchone()

    effect_phases = [str(row[0]) for row in effects]
    node_entries = [str(phase) for phase, event in events if event == "effect_enter"]
    decisions = [str(event) for _phase, event in events if event in {"dispatch", "return_prior", "fail_closed"}]
    return {
        "effect_count": len(effect_phases),
        "effect_phases": effect_phases,
        "node_entries": node_entries,
        "decisions": decisions,
        "permit_consumed": None if permit is None else bool(int(permit[0])),
        "receipt_result": None if receipt is None else str(receipt[0]),
    }


def run_trial(root: Path, arm: Arm, index: int) -> dict[str, object]:
    checkpoint = root / f"checkpoint-{arm}-{index}.sqlite"
    store = root / f"external-{arm}-{index}.sqlite"
    init_store(store)
    action_id = f"lg-action-{arm}-{index}"
    thread_id = f"lg-thread-{arm}-{index}"
    if arm == "guarded":
        issue_permit(store, action_id)

    script = str(Path(__file__).resolve())
    subject_proc = subprocess.run(
        [
            sys.executable,
            script,
            "--subject",
            "--checkpoint",
            str(checkpoint),
            "--store",
            str(store),
            "--arm",
            arm,
            "--thread-id",
            thread_id,
            "--action-id",
            action_id,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    after_subject = snapshot_store(store, action_id)

    recovery_proc = subprocess.run(
        [
            sys.executable,
            script,
            "--recovery",
            "--checkpoint",
            str(checkpoint),
            "--store",
            str(store),
            "--arm",
            arm,
            "--thread-id",
            thread_id,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    after_recovery = snapshot_store(store, action_id)

    if recovery_proc.returncode != 0:
        raise RuntimeError(
            "recovery subprocess failed:\n"
            f"arm={arm} index={index}\n"
            f"stdout={recovery_proc.stdout}\n"
            f"stderr={recovery_proc.stderr}"
        )

    common = (
        subject_proc.returncode == CRASH_EXIT
        and after_subject["effect_count"] == 1
        and after_subject["node_entries"] == ["subject"]
        and after_recovery["node_entries"] == ["subject", "recovery"]
    )
    if arm == "baseline":
        passed = (
            common
            and after_recovery["effect_count"] == 2
            and after_recovery["effect_phases"] == ["subject", "recovery"]
            and after_recovery["decisions"] == ["dispatch", "dispatch"]
        )
        verdict = "DUPLICATED_ON_RECOVERY"
    else:
        passed = (
            common
            and after_recovery["effect_count"] == 1
            and after_recovery["effect_phases"] == ["subject"]
            and after_recovery["decisions"] == ["dispatch", "return_prior"]
            and after_recovery["permit_consumed"] is True
            and after_recovery["receipt_result"] == RESULT
        )
        verdict = "RECONCILED_NO_DUPLICATE"

    return {
        "arm": arm,
        "index": index,
        "action_id": action_id,
        "thread_id": thread_id,
        "subject_returncode": subject_proc.returncode,
        "recovery_returncode": recovery_proc.returncode,
        "effect_count_after_subject": after_subject["effect_count"],
        "effect_count_after_recovery": after_recovery["effect_count"],
        "effect_phases": after_recovery["effect_phases"],
        "node_entries": after_recovery["node_entries"],
        "decisions": after_recovery["decisions"],
        "permit_consumed": after_recovery["permit_consumed"],
        "receipt_result": after_recovery["receipt_result"],
        "verdict": verdict,
        "passed": passed,
    }


def run(k: int) -> dict[str, object]:
    trials: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for arm in ARMS:
            for index in range(k):
                trials.append(run_trial(root, arm, index))

    arms: dict[str, object] = {}
    for arm in ARMS:
        rows = [row for row in trials if row["arm"] == arm]
        effect_counts = Counter(str(row["effect_count_after_recovery"]) for row in rows)
        decision_sequences = Counter("->".join(cast(list[str], row["decisions"])) for row in rows)
        verdicts = Counter(str(row["verdict"]) for row in rows)
        arms[arm] = {
            "k": k,
            "passing": sum(bool(row["passed"]) for row in rows),
            "effect_counts_after_recovery": dict(effect_counts),
            "decision_sequences": dict(decision_sequences),
            "verdicts": dict(verdicts),
        }

    report: dict[str, object] = {
        "schema": "contractgraph.langgraph-identity-authority-adapter.v0.1",
        "runtime": {
            "langgraph": importlib.metadata.version("langgraph"),
            "langgraph-checkpoint": importlib.metadata.version("langgraph-checkpoint"),
            "langgraph-checkpoint-sqlite": importlib.metadata.version("langgraph-checkpoint-sqlite"),
        },
        "external_reference": {
            "repository": "mstevens843/crashpoint",
            "publication_commit": "606893ebb353df5dab3ac68738051eb5fbb7286e",
        },
        "k_per_arm": k,
        "arms": arms,
        "all_pass": all(bool(row["passed"]) for row in trials),
        "claim": (
            "on the pinned local LangGraph SQLite checkpoint/resume surface, the incomplete "
            "side-effecting node is re-entered after abrupt process exit; external receipt "
            "reconciliation can preserve stable action identity while suppressing redispatch"
        ),
        "non_claims": [
            "not LangGraph Cloud heartbeat/sweeper evidence",
            "not a LangGraph framework fix",
            "not proof for every checkpointer or distributed worker race",
            "not global exactly-once execution",
        ],
        "trials": trials,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--subject", action="store_true")
    mode.add_argument("--recovery", action="store_true")
    ap.add_argument("--checkpoint")
    ap.add_argument("--store")
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--thread-id")
    ap.add_argument("--action-id")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--write-report")
    args = ap.parse_args(argv)

    if args.subject:
        assert args.checkpoint and args.store and args.arm and args.thread_id and args.action_id
        return subject(Path(args.checkpoint), Path(args.store), args.arm, args.thread_id, args.action_id)
    if args.recovery:
        assert args.checkpoint and args.store and args.arm and args.thread_id
        return recovery(Path(args.checkpoint), Path(args.store), args.arm, args.thread_id)

    report = run(args.k)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        Path(args.write_report).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    if not report["all_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
