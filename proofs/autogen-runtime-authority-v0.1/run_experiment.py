from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from autogen_core import AgentId, MessageContext, RoutedAgent, SingleThreadedAgentRuntime, message_handler

TARGET = "local-sqlite-target"
OTHER_TARGET = "other-sqlite-target"
RESULT = "external-effect-ok"
INTENT = "append-one-marker"
AGENT_TYPE = "authority_agent"
AGENT_KEY = "default"
AUTOGEN_SOURCE_COMMIT = "027ecf0a379bcc1d09956d46d12d44a3ad9cee14"
CASES = ("confirmed", "unknown", "mismatch", "not_executed")


@dataclass
class AuthorityMessage:
    phase: str


def intent_hash() -> str:
    return hashlib.sha256(f"{INTENT}|{TARGET}".encode()).hexdigest()


def stable_action_id(case: str) -> str:
    raw = f"autogen-runtime-authority|{case}|{intent_hash()}".encode()
    return "act_" + hashlib.sha256(raw).hexdigest()[:32]


def permit_id(action_id: str, generation: int) -> str:
    raw = f"{action_id}|permit|{generation}".encode()
    return "permit_" + hashlib.sha256(raw).hexdigest()[:24]


def init_external(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            create table if not exists entries (
                seq integer primary key autoincrement,
                case_name text not null,
                phase text not null,
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
                case_name text not null,
                action_id text not null,
                generation integer not null,
                permit_id text not null,
                consumed integer not null,
                consume_count integer not null,
                primary key (case_name, action_id, generation)
            );
            create table if not exists receipts (
                case_name text not null,
                action_id text not null,
                target text not null,
                result text not null,
                visible integer not null,
                primary key (case_name, action_id)
            );
            create table if not exists outcomes (
                case_name text not null,
                action_id text not null,
                status text not null,
                primary key (case_name, action_id)
            );
            create table if not exists authorizations (
                seq integer primary key autoincrement,
                case_name text not null,
                action_id text not null,
                generation integer not null,
                decision text not null
            );
            """
        )


def record_entry(path: Path, case: str, phase: str, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into entries(case_name, phase, action_id) values (?, ?, ?)",
            (case, phase, action_id),
        )


def record_decision(path: Path, case: str, action_id: str, decision: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into decisions(case_name, action_id, decision) values (?, ?, ?)",
            (case, action_id, decision),
        )


def issue_and_consume_permit(path: Path, case: str, action_id: str, generation: int) -> str:
    pid = permit_id(action_id, generation)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into authorizations(case_name, action_id, generation, decision) values (?, ?, ?, 'issued')",
            (case, action_id, generation),
        )
        conn.execute(
            "insert into permits(case_name, action_id, generation, permit_id, consumed, consume_count) "
            "values (?, ?, ?, ?, 1, 1)",
            (case, action_id, generation, pid),
        )
    return pid


def commit_effect(
    path: Path,
    case: str,
    action_id: str,
    *,
    receipt_target: str | None,
    receipt_visible: bool,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert into effects(case_name, action_id, target, result) values (?, ?, ?, ?)",
            (case, action_id, TARGET, RESULT),
        )
        if receipt_target is not None:
            conn.execute(
                "insert or replace into receipts(case_name, action_id, target, result, visible) "
                "values (?, ?, ?, ?, ?)",
                (case, action_id, receipt_target, RESULT, int(receipt_visible)),
            )


def mark_not_executed(path: Path, case: str, action_id: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "insert or replace into outcomes(case_name, action_id, status) values (?, ?, 'NOT_EXECUTED')",
            (case, action_id),
        )


def set_receipt_visibility(path: Path, case: str, action_id: str, visible: bool) -> None:
    with sqlite3.connect(path) as conn:
        updated = conn.execute(
            "update receipts set visible = ? where case_name = ? and action_id = ?",
            (int(visible), case, action_id),
        ).rowcount
    if updated != 1:
        raise RuntimeError("receipt visibility update did not match exactly one row")


def read_external_state(path: Path, case: str, action_id: str) -> tuple[str, dict[str, str] | None]:
    with sqlite3.connect(path) as conn:
        receipt = conn.execute(
            "select target, result, visible from receipts where case_name = ? and action_id = ?",
            (case, action_id),
        ).fetchone()
        outcome = conn.execute(
            "select status from outcomes where case_name = ? and action_id = ?",
            (case, action_id),
        ).fetchone()

    if receipt is not None and bool(receipt[2]):
        return "CONFIRMED", {"target": str(receipt[0]), "result": str(receipt[1])}
    if outcome is not None and str(outcome[0]) == "NOT_EXECUTED":
        return "NOT_EXECUTED", None
    return "UNKNOWN", None


class AuthorityAgent(RoutedAgent):
    def __init__(self, external_db: str, case: str) -> None:
        super().__init__("ContractGraph-QA AutoGen recovery-authority fixture")
        self._external_db = Path(external_db)
        self._case = case
        self._action_id: str | None = None
        self._intent_hash = intent_hash()
        self._target = TARGET

    @message_handler
    async def handle(self, message: AuthorityMessage, ctx: MessageContext) -> dict[str, str]:
        del ctx
        if message.phase not in {"subject", "recovery"}:
            raise ValueError(f"unexpected phase: {message.phase}")

        if self._action_id is None:
            if message.phase != "subject":
                raise RuntimeError("recovery reached agent without restored action identity")
            self._action_id = stable_action_id(self._case)

        action_id = self._action_id
        record_entry(self._external_db, self._case, message.phase, action_id)

        if message.phase == "subject":
            issue_and_consume_permit(self._external_db, self._case, action_id, 1)
            record_decision(self._external_db, self._case, action_id, "dispatch")

            if self._case == "not_executed":
                mark_not_executed(self._external_db, self._case, action_id)
                raise RuntimeError("injected pre-effect failure with authoritative NOT_EXECUTED witness")

            receipt_target = OTHER_TARGET if self._case == "mismatch" else TARGET
            receipt_visible = self._case != "unknown"
            commit_effect(
                self._external_db,
                self._case,
                action_id,
                receipt_target=receipt_target,
                receipt_visible=receipt_visible,
            )
            raise RuntimeError("injected lost response after external effect commit")

        external_status, receipt = read_external_state(self._external_db, self._case, action_id)

        if external_status == "CONFIRMED":
            assert receipt is not None
            if receipt != {"target": self._target, "result": RESULT}:
                record_decision(self._external_db, self._case, action_id, "fail_closed_mismatch")
                return {"status": "BLOCKED_MISMATCH"}
            record_decision(self._external_db, self._case, action_id, "return_prior")
            return {"status": "RETURN_PRIOR", "result": RESULT}

        if external_status == "UNKNOWN":
            record_decision(self._external_db, self._case, action_id, "fail_closed_unknown")
            return {"status": "BLOCKED_UNKNOWN"}

        if external_status == "NOT_EXECUTED":
            record_decision(self._external_db, self._case, action_id, "fresh_authorization_required")
            issue_and_consume_permit(self._external_db, self._case, action_id, 2)
            record_decision(self._external_db, self._case, action_id, "dispatch")
            commit_effect(
                self._external_db,
                self._case,
                action_id,
                receipt_target=TARGET,
                receipt_visible=True,
            )
            return {"status": "FRESH_DISPATCH", "result": RESULT}

        raise RuntimeError(f"unsupported external status: {external_status}")

    async def save_state(self) -> Mapping[str, Any]:
        if self._action_id is None:
            return {
                "schema": "contractgraph.autogen-authority-agent-state.v0.1",
                "action_id": None,
                "intent_hash": self._intent_hash,
                "target": self._target,
            }
        return {
            "schema": "contractgraph.autogen-authority-agent-state.v0.1",
            "action_id": self._action_id,
            "intent_hash": self._intent_hash,
            "target": self._target,
        }

    async def load_state(self, state: Mapping[str, Any]) -> None:
        if state.get("schema") != "contractgraph.autogen-authority-agent-state.v0.1":
            raise ValueError("unexpected AutoGen authority state schema")
        if state.get("intent_hash") != self._intent_hash:
            raise ValueError("restored intent hash mismatch")
        if state.get("target") != self._target:
            raise ValueError("restored target mismatch")
        action_id = state.get("action_id")
        if not isinstance(action_id, str):
            raise ValueError("restored action_id must be a string")
        self._action_id = action_id


async def create_runtime(external_db: str, case: str) -> SingleThreadedAgentRuntime:
    runtime = SingleThreadedAgentRuntime()
    await AuthorityAgent.register(
        runtime,
        AGENT_TYPE,
        lambda: AuthorityAgent(external_db, case),
    )
    return runtime


async def subject_phase(external_db: str, case: str, state_path: str) -> dict[str, Any]:
    runtime = await create_runtime(external_db, case)
    runtime.start()
    error_type = ""
    error_message = ""
    try:
        await runtime.send_message(
            AuthorityMessage("subject"),
            recipient=AgentId(AGENT_TYPE, AGENT_KEY),
        )
    except Exception as exc:
        error_type = type(exc).__name__
        error_message = str(exc)

    state = dict(await runtime.save_state())
    encoded = json.dumps(state, sort_keys=True)
    decoded = json.loads(encoded)
    if decoded != state:
        raise AssertionError("AutoGen runtime state did not survive JSON round-trip")

    if len(state) != 1:
        raise AssertionError(f"expected exactly one instantiated agent state, got {list(state)}")
    agent_state = next(iter(state.values()))
    if not isinstance(agent_state, dict):
        raise AssertionError("saved AutoGen agent state is not a mapping")
    expected_fields = {"schema", "action_id", "intent_hash", "target"}
    if set(agent_state) != expected_fields:
        raise AssertionError(f"saved agent state fields differ: {sorted(agent_state)}")
    if any("permit" in key.lower() for key in agent_state):
        raise AssertionError("execution permit leaked into AutoGen agent state")

    Path(state_path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    await runtime.stop_when_idle()
    return {
        "error_type": error_type,
        "error_message": error_message,
        "saved_agent_fields": sorted(agent_state),
        "saved_action_id": agent_state["action_id"],
        "permit_persisted": False,
    }


async def recovery_phase(external_db: str, case: str, state_path: str) -> dict[str, Any]:
    state = json.loads(Path(state_path).read_text())
    if not isinstance(state, dict):
        raise AssertionError("saved runtime state is not an object")

    runtime = await create_runtime(external_db, case)
    await runtime.load_state(state)
    restored = dict(await runtime.save_state())
    if restored != state:
        raise AssertionError("AutoGen runtime load/save did not preserve the frozen agent state")

    runtime.start()
    result = await runtime.send_message(
        AuthorityMessage("recovery"),
        recipient=AgentId(AGENT_TYPE, AGENT_KEY),
    )
    final_state = dict(await runtime.save_state())
    await runtime.stop_when_idle()
    if final_state != state:
        raise AssertionError("recovery mutated persisted identity state")
    if not isinstance(result, dict):
        raise AssertionError("recovery result is not an object")
    return result


def run_phase(args: argparse.Namespace) -> int:
    if args.phase == "subject":
        result = asyncio.run(subject_phase(args.external_db, args.case, args.state))
    elif args.phase == "recovery":
        result = asyncio.run(recovery_phase(args.external_db, args.case, args.state))
    else:
        raise ValueError(f"unknown phase: {args.phase}")
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


def run_process(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, text=True, capture_output=True, check=False, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(
            "\n".join(
                [
                    f"AutoGen fixture subprocess failed: {proc.returncode}",
                    f"argv={' '.join(args)}",
                    f"stdout={proc.stdout.strip() or '<empty>'}",
                    f"stderr={proc.stderr.strip() or '<empty>'}",
                ]
            )
        )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("AutoGen fixture subprocess emitted no JSON")
    parsed = json.loads(lines[-1])
    if not isinstance(parsed, dict):
        raise RuntimeError("AutoGen fixture subprocess result is not an object")
    return parsed


def snapshot(path: Path, case: str) -> dict[str, Any]:
    with sqlite3.connect(path) as conn:
        entries = conn.execute(
            "select phase, action_id from entries where case_name = ? order by seq", (case,)
        ).fetchall()
        decisions = conn.execute(
            "select decision from decisions where case_name = ? order by seq", (case,)
        ).fetchall()
        effects = conn.execute(
            "select action_id, target, result from effects where case_name = ? order by seq", (case,)
        ).fetchall()
        permits = conn.execute(
            "select generation, permit_id, consumed, consume_count from permits "
            "where case_name = ? order by generation",
            (case,),
        ).fetchall()
        receipt = conn.execute(
            "select target, result, visible from receipts where case_name = ? and action_id = ?",
            (case, stable_action_id(case)),
        ).fetchone()
        outcome = conn.execute(
            "select status from outcomes where case_name = ? and action_id = ?",
            (case, stable_action_id(case)),
        ).fetchone()

    return {
        "entries": [{"phase": str(row[0]), "action_id": str(row[1])} for row in entries],
        "decisions": [str(row[0]) for row in decisions],
        "effect_count": len(effects),
        "effects": [
            {"action_id": str(row[0]), "target": str(row[1]), "result": str(row[2])}
            for row in effects
        ],
        "permits": [
            {
                "generation": int(row[0]),
                "permit_id": str(row[1]),
                "consumed": bool(row[2]),
                "consume_count": int(row[3]),
            }
            for row in permits
        ],
        "receipt": None
        if receipt is None
        else {"target": str(receipt[0]), "result": str(receipt[1]), "visible": bool(receipt[2])},
        "outcome": None if outcome is None else str(outcome[0]),
    }


def phase_argv(script: Path, phase: str, case: str, external: Path, state: Path) -> list[str]:
    return [
        sys.executable,
        str(script),
        "--phase",
        phase,
        "--case",
        case,
        "--external-db",
        str(external),
        "--state",
        str(state),
    ]


def run_case(root: Path, case: str) -> dict[str, Any]:
    external = root / f"external-{case}.sqlite"
    state = root / f"autogen-state-{case}.json"
    init_external(external)
    script = Path(__file__).resolve()

    subject = run_process(phase_argv(script, "subject", case, external, state))
    before = snapshot(external, case)
    saved_runtime_state = json.loads(state.read_text())
    if not isinstance(saved_runtime_state, dict) or len(saved_runtime_state) != 1:
        raise AssertionError("unexpected frozen AutoGen runtime state shape")
    saved_agent_state = next(iter(saved_runtime_state.values()))

    first_recovery = run_process(phase_argv(script, "recovery", case, external, state))
    after_first = snapshot(external, case)

    second_recovery: dict[str, Any] | None = None
    after_second: dict[str, Any] | None = None
    if case == "unknown":
        set_receipt_visibility(external, case, stable_action_id(case), True)
        second_recovery = run_process(phase_argv(script, "recovery", case, external, state))
        after_second = snapshot(external, case)

    expected_action = stable_action_id(case)
    saved_identity_ok = (
        isinstance(saved_agent_state, dict)
        and saved_agent_state.get("action_id") == expected_action
        and saved_agent_state.get("intent_hash") == intent_hash()
        and saved_agent_state.get("target") == TARGET
        and set(saved_agent_state) == {"schema", "action_id", "intent_hash", "target"}
    )

    if case == "confirmed":
        passed = (
            saved_identity_ok
            and subject["permit_persisted"] is False
            and first_recovery == {"status": "RETURN_PRIOR", "result": RESULT}
            and after_first["decisions"] == ["dispatch", "return_prior"]
            and after_first["effect_count"] == 1
            and len(after_first["entries"]) == 2
            and {row["action_id"] for row in after_first["entries"]} == {expected_action}
            and len(after_first["permits"]) == 1
            and after_first["permits"][0]["generation"] == 1
            and after_first["permits"][0]["consume_count"] == 1
        )
        verdict = "CONFIRMED_RETURN_PRIOR"
    elif case == "unknown":
        assert after_second is not None and second_recovery is not None
        passed = (
            saved_identity_ok
            and subject["permit_persisted"] is False
            and first_recovery == {"status": "BLOCKED_UNKNOWN"}
            and after_first["decisions"] == ["dispatch", "fail_closed_unknown"]
            and after_first["effect_count"] == 1
            and after_first["receipt"]["visible"] is False
            and second_recovery == {"status": "RETURN_PRIOR", "result": RESULT}
            and after_second["decisions"] == ["dispatch", "fail_closed_unknown", "return_prior"]
            and after_second["effect_count"] == 1
            and len(after_second["entries"]) == 3
            and {row["action_id"] for row in after_second["entries"]} == {expected_action}
            and len(after_second["permits"]) == 1
            and after_second["permits"][0]["consume_count"] == 1
        )
        verdict = "UNKNOWN_BLOCKED_THEN_CONFIRMED"
    elif case == "mismatch":
        passed = (
            saved_identity_ok
            and subject["permit_persisted"] is False
            and first_recovery == {"status": "BLOCKED_MISMATCH"}
            and after_first["decisions"] == ["dispatch", "fail_closed_mismatch"]
            and after_first["effect_count"] == 1
            and len(after_first["entries"]) == 2
            and {row["action_id"] for row in after_first["entries"]} == {expected_action}
            and after_first["receipt"]["target"] == OTHER_TARGET
            and len(after_first["permits"]) == 1
            and after_first["permits"][0]["consume_count"] == 1
        )
        verdict = "MISMATCH_FAIL_CLOSED"
    elif case == "not_executed":
        passed = (
            saved_identity_ok
            and subject["permit_persisted"] is False
            and before["effect_count"] == 0
            and before["outcome"] == "NOT_EXECUTED"
            and first_recovery == {"status": "FRESH_DISPATCH", "result": RESULT}
            and after_first["decisions"] == [
                "dispatch",
                "fresh_authorization_required",
                "dispatch",
            ]
            and after_first["effect_count"] == 1
            and len(after_first["entries"]) == 2
            and {row["action_id"] for row in after_first["entries"]} == {expected_action}
            and [row["generation"] for row in after_first["permits"]] == [1, 2]
            and [row["consume_count"] for row in after_first["permits"]] == [1, 1]
            and after_first["permits"][0]["permit_id"] != after_first["permits"][1]["permit_id"]
        )
        verdict = "NOT_EXECUTED_FRESH_AUTHORITY"
    else:
        raise ValueError(case)

    return {
        "case": case,
        "passed": passed,
        "verdict": verdict if passed else "UNEXPECTED",
        "saved_agent_state": saved_agent_state,
        "subject": subject,
        "before_recovery": before,
        "first_recovery": first_recovery,
        "after_first_recovery": after_first,
        "second_recovery": second_recovery,
        "after_second_recovery": after_second,
    }


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cases = {case: run_case(root, case) for case in CASES}

    report: dict[str, Any] = {
        "schema": "contractgraph.autogen-runtime-authority.v0.1",
        "runtime": {"autogen_core": importlib.metadata.version("autogen-core")},
        "upstream": {
            "repository": "microsoft/autogen",
            "commit": AUTOGEN_SOURCE_COMMIT,
            "package_version_at_commit": "0.7.5",
            "state_boundary": "SingleThreadedAgentRuntime.save_state/load_state",
        },
        "claim": (
            "on the pinned AutoGen 0.7.5 runtime state boundary, stable action identity can survive "
            "fresh-process save/load while execution permits remain external and each recovery state "
            "maps to the frozen recovery-authority decisions"
        ),
        "cases": cases,
        "all_pass": all(case["passed"] for case in cases.values()),
        "state_rule": (
            "AutoGen persisted state carries action identity, intent hash and target only; it does not "
            "carry a permit or a derived authorization to execute again."
        ),
        "non_claims": [
            "does not prove AutoGen natively implements retry deduplication or external reconciliation",
            "does not prove crash recovery of AutoGen runtime internals",
            "does not prove global exactly-once execution",
            "does not prove external target availability or Byzantine correctness",
        ],
        "predecessors": [
            "https://github.com/safal207/ContractGraph-QA/pull/81",
            "https://github.com/safal207/ContractGraph-QA/pull/173",
            "https://github.com/safal207/ContractGraph-QA/pull/185",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("subject", "recovery"))
    ap.add_argument("--case", choices=CASES)
    ap.add_argument("--external-db")
    ap.add_argument("--state")
    ap.add_argument("--write-report")
    args = ap.parse_args(argv)

    if args.phase:
        if not args.case or not args.external_db or not args.state:
            ap.error("--phase requires --case, --external-db and --state")
        return run_phase(args)

    report = run()
    compact = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print("REPORT_JSON=" + compact)
    if args.write_report:
        Path(args.write_report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
