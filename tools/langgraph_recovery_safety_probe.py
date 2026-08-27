#!/usr/bin/env python3
"""Live LangGraph #8039 crash/recovery probe with stable action identity.

Linux/POSIX only because the injected crash uses SIGKILL.

Examples:
    python tools/langgraph_recovery_safety_probe.py writes-delay --receiver append
    python tools/langgraph_recovery_safety_probe.py put-delay --receiver append
    python tools/langgraph_recovery_safety_probe.py writes-delay --receiver dedup
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

from contractgraph_qa.integrations.langgraph_recovery_safety import (
    LANGGRAPH_BASELINE_VERSION,
    LANGGRAPH_ISSUE_NUMBER,
    LANGGRAPH_ISSUE_REPOSITORY,
    LANGGRAPH_SQLITE_BASELINE_VERSION,
    OBSERVATION_SCHEMA,
    canonical_digest,
    logical_action_set_digest,
    semantic_action_identity,
)

STEPS = ("step1", "step2", "step3")
THREAD_ID = "t1"
WORKFLOW_INSTANCE = "langgraph-8039:t1"
CRASH_BOUNDARY = "checkpoint.put:channel_values.sent=2:entry"


class State(TypedDict):
    sent: int


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def _action(step: str) -> dict[str, Any]:
    return {
        "kind": "fixture_external_effect",
        "workflow_instance": WORKFLOW_INSTANCE,
        "logical_action": step,
    }


def _logical_actions() -> list[dict[str, Any]]:
    return [_action(step) for step in STEPS]


def _admit_effect(workdir: Path, step: str, receiver: str) -> None:
    action = _action(step)
    action_id = semantic_action_identity(action)
    attempt = {"step": step, "action_id": action_id, "action": action}
    _append_jsonl(workdir / "attempts.jsonl", attempt)

    if receiver == "append":
        _append_jsonl(workdir / "admissions.jsonl", attempt)
        return

    if receiver != "dedup":
        raise ValueError(f"unsupported receiver: {receiver}")

    conn = sqlite3.connect(workdir / "receiver.db", timeout=30)
    try:
        conn.execute(
            "create table if not exists admissions ("
            "action_id text primary key, step text not null, payload text not null)"
        )
        cursor = conn.execute(
            "insert or ignore into admissions(action_id, step, payload) values (?, ?, ?)",
            (action_id, step, json.dumps(action, sort_keys=True)),
        )
        conn.commit()
        if cursor.rowcount == 1:
            _append_jsonl(workdir / "admissions.jsonl", attempt)
    finally:
        conn.close()


def _run_graph(workdir_text: str, mode: str, delay_side: str, receiver: str) -> None:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, START, StateGraph

    workdir = Path(workdir_text)

    def die() -> None:
        os.kill(os.getpid(), signal.SIGKILL)

    def worker(state: State) -> State:
        index = state["sent"]
        step = STEPS[index]
        _admit_effect(workdir, step, receiver)
        return {"sent": index + 1}

    def cont(state: State) -> str:
        return "worker" if state["sent"] < len(STEPS) else END

    class RacingSaver(SqliteSaver):
        def put_writes(self, config, writes, task_id, task_path=""):
            if mode == "start" and delay_side == "writes-delay":
                time.sleep(0.08)
            return super().put_writes(config, writes, task_id, task_path)

        def put(self, config, checkpoint, metadata_value, new_versions):
            if mode == "start":
                if delay_side == "put-delay":
                    time.sleep(0.08)
                if checkpoint.get("channel_values", {}).get("sent") == 2:
                    die()
            return super().put(config, checkpoint, metadata_value, new_versions)

    conn = sqlite3.connect(workdir / "state.db", check_same_thread=False)
    try:
        graph_builder = StateGraph(State)
        graph_builder.add_node("worker", worker)
        graph_builder.add_edge(START, "worker")
        graph_builder.add_conditional_edges("worker", cont)
        graph = graph_builder.compile(checkpointer=RacingSaver(conn))
        config = {"configurable": {"thread_id": THREAD_ID}}
        if mode == "resume":
            result = graph.invoke(None, config, durability="sync")
        else:
            result = graph.invoke({"sent": 0}, config, durability="sync")
        (workdir / "final-state.json").write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
    finally:
        conn.close()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(record["step"] for record in records).items()))


def _database_counts(workdir: Path) -> tuple[int, int]:
    db = sqlite3.connect(workdir / "state.db", timeout=30)
    try:
        checkpoint_rows = db.execute("select count(*) from checkpoints").fetchone()[0]
        pending_write_rows = db.execute("select count(*) from writes").fetchone()[0]
        return int(checkpoint_rows), int(pending_write_rows)
    finally:
        db.close()


def _build_observation(
    workdir: Path,
    scenario: str,
    receiver: str,
    start_returncode: int,
    resume_returncode: int,
    crash_counts: tuple[int, int],
    post_resume_counts: tuple[int, int],
) -> dict[str, Any]:
    attempts = _read_jsonl(workdir / "attempts.jsonl")
    admissions = _read_jsonl(workdir / "admissions.jsonl")
    final_state = json.loads((workdir / "final-state.json").read_text(encoding="utf-8"))
    observable_state = {
        "graph_state": final_state,
        "attempt_counts": _counts(attempts),
        "admission_counts": _counts(admissions),
    }
    received = {"thread_id": THREAD_ID, "input": {"sent": 0}}
    logical_actions = _logical_actions()
    return {
        "schema": OBSERVATION_SCHEMA,
        "source": {
            "repository": LANGGRAPH_ISSUE_REPOSITORY,
            "issue": LANGGRAPH_ISSUE_NUMBER,
            "kind": "live_sigkill_probe",
            "langgraph_version": metadata.version("langgraph"),
            "sqlite_checkpointer_version": metadata.version(
                "langgraph-checkpoint-sqlite"
            ),
        },
        "scenario": scenario,
        "receiver": receiver,
        "received": received,
        "received_digest": canonical_digest(received),
        "logical_actions": logical_actions,
        "logical_action_set_digest": logical_action_set_digest(logical_actions),
        "crash_boundary": CRASH_BOUNDARY,
        "start_sigkill_observed": start_returncode == -signal.SIGKILL,
        "resume_returncode": resume_returncode,
        "checkpoint_rows_at_crash": crash_counts[0],
        "pending_write_rows_at_crash": crash_counts[1],
        "checkpoint_rows_after_resume": post_resume_counts[0],
        "pending_write_rows_after_resume": post_resume_counts[1],
        "attempts": attempts,
        "attempt_counts": _counts(attempts),
        "admissions": admissions,
        "admission_counts": _counts(admissions),
        "observable_state": observable_state,
        "recovered_state_digest": canonical_digest(observable_state),
        "runtime_reexecution_observed": any(
            count > 1 for count in _counts(attempts).values()
        ),
        "duplicate_admission_observed": any(
            count > 1 for count in _counts(admissions).values()
        ),
    }


def _expected_matches(observation: dict[str, Any], expected: str | None) -> bool:
    if expected is None:
        return True
    reexecuted = observation["runtime_reexecution_observed"]
    duplicated = observation["duplicate_admission_observed"]
    if expected == "duplicate":
        return reexecuted and duplicated
    if expected == "exactly-once":
        return not reexecuted and not duplicated
    if expected == "deduped-reexecution":
        return reexecuted and not duplicated
    raise ValueError(f"unsupported expectation: {expected}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario", choices=("natural", "writes-delay", "put-delay")
    )
    parser.add_argument("--receiver", choices=("append", "dedup"), default="append")
    parser.add_argument(
        "--expect", choices=("duplicate", "exactly-once", "deduped-reexecution")
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    return parser.parse_args()


def _print_subprocess_failure(label: str, process: subprocess.CompletedProcess[str]) -> None:
    print(f"{label} return code: {process.returncode}", file=sys.stderr)
    if process.stdout:
        print(process.stdout, file=sys.stderr)
    if process.stderr:
        print(process.stderr, file=sys.stderr)


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--child":
        _run_graph(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        return 0

    if os.name != "posix":
        print("This live fault probe requires POSIX SIGKILL.", file=sys.stderr)
        return 2

    args = _parse_args()
    installed_langgraph = metadata.version("langgraph")
    installed_sqlite = metadata.version("langgraph-checkpoint-sqlite")
    print(
        f"python {platform.python_version()} | {platform.platform()} | "
        f"langgraph {installed_langgraph} | "
        f"langgraph-checkpoint-sqlite {installed_sqlite}"
    )
    if installed_langgraph != LANGGRAPH_BASELINE_VERSION:
        print(
            f"warning: benchmark baseline is langgraph {LANGGRAPH_BASELINE_VERSION}",
            file=sys.stderr,
        )
    if installed_sqlite != LANGGRAPH_SQLITE_BASELINE_VERSION:
        print(
            "warning: benchmark baseline is langgraph-checkpoint-sqlite "
            f"{LANGGRAPH_SQLITE_BASELINE_VERSION}",
            file=sys.stderr,
        )

    workdir = Path(tempfile.mkdtemp(prefix="cgqa_langgraph_rs_"))
    try:
        script = Path(__file__).resolve()
        start = subprocess.run(
            [
                sys.executable,
                str(script),
                "--child",
                str(workdir),
                "start",
                args.scenario,
                args.receiver,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if start.returncode != -signal.SIGKILL:
            _print_subprocess_failure("start", start)
            print("expected SIGKILL was not observed", file=sys.stderr)
            return 1

        crash_counts = _database_counts(workdir)
        print(
            "durable state at crash:",
            f"{crash_counts[0]} checkpoints / {crash_counts[1]} pending-write rows",
        )

        resume = subprocess.run(
            [
                sys.executable,
                str(script),
                "--child",
                str(workdir),
                "resume",
                args.scenario,
                args.receiver,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if resume.returncode != 0:
            _print_subprocess_failure("resume", resume)
            return 1

        post_resume_counts = _database_counts(workdir)
        observation = _build_observation(
            workdir,
            args.scenario,
            args.receiver,
            start.returncode,
            resume.returncode,
            crash_counts,
            post_resume_counts,
        )
        print("attempts:", observation["attempt_counts"])
        print("admissions:", observation["admission_counts"])
        print(
            "verdict:",
            "DUPLICATE_ADMISSION"
            if observation["duplicate_admission_observed"]
            else (
                "REEXECUTED_BUT_DEDUPED"
                if observation["runtime_reexecution_observed"]
                else "EXACTLY_ONCE_UNDER_THIS_INTERLEAVING"
            ),
        )

        if args.json is not None:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(
                json.dumps(observation, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"observation: {args.json}")
        if args.keep_workdir:
            print(f"workdir: {workdir}")

        if not _expected_matches(observation, args.expect):
            print(f"expectation failed: {args.expect}", file=sys.stderr)
            return 1
        return 0
    finally:
        if not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
