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
from pathlib import Path
from typing import Any, Mapping

from autogen_core import AgentId, BaseAgent, MessageContext, SingleThreadedAgentRuntime

TARGET = "local-sqlite-target"
OTHER_TARGET = "other-sqlite-target"
RESULT = "external-effect-ok"
INTENT = "append-one-marker"
AGENT_TYPE = "authority_agent"
AGENT_KEY = "default"
AUTOGEN_SOURCE_COMMIT = "027ecf0a379bcc1d09956d46d12d44a3ad9cee14"
CASES = ("confirmed", "unknown", "mismatch", "not_executed")


def ihash() -> str:
    return hashlib.sha256(f"{INTENT}|{TARGET}".encode()).hexdigest()


def action_id(case: str) -> str:
    return "act_" + hashlib.sha256(f"autogen|{case}|{ihash()}".encode()).hexdigest()[:32]


def permit_id(aid: str, generation: int) -> str:
    return "permit_" + hashlib.sha256(f"{aid}|{generation}".encode()).hexdigest()[:24]


def init_db(path: Path) -> None:
    with sqlite3.connect(path) as c:
        c.executescript(
            """
            create table entries(seq integer primary key autoincrement, case_name text, phase text, action_id text);
            create table decisions(seq integer primary key autoincrement, case_name text, action_id text, decision text);
            create table effects(seq integer primary key autoincrement, case_name text, action_id text, target text, result text);
            create table permits(case_name text, action_id text, generation integer, permit_id text,
                consumed integer, consume_count integer, primary key(case_name, action_id, generation));
            create table receipts(case_name text, action_id text, target text, result text, visible integer,
                primary key(case_name, action_id));
            create table outcomes(case_name text, action_id text, status text, primary key(case_name, action_id));
            """
        )


def sql(path: Path, statement: str, params: tuple[Any, ...] = ()) -> None:
    with sqlite3.connect(path) as c:
        c.execute(statement, params)


def issue_permit(path: Path, case: str, aid: str, generation: int) -> None:
    sql(
        path,
        "insert into permits values (?, ?, ?, ?, 1, 1)",
        (case, aid, generation, permit_id(aid, generation)),
    )


def commit_effect(path: Path, case: str, aid: str, receipt_target: str, visible: bool) -> None:
    with sqlite3.connect(path) as c:
        c.execute("insert into effects(case_name, action_id, target, result) values (?, ?, ?, ?)",
                  (case, aid, TARGET, RESULT))
        c.execute("insert into receipts values (?, ?, ?, ?, ?)",
                  (case, aid, receipt_target, RESULT, int(visible)))


def readback(path: Path, case: str, aid: str) -> tuple[str, dict[str, str] | None]:
    with sqlite3.connect(path) as c:
        receipt = c.execute(
            "select target, result, visible from receipts where case_name=? and action_id=?",
            (case, aid),
        ).fetchone()
        outcome = c.execute(
            "select status from outcomes where case_name=? and action_id=?",
            (case, aid),
        ).fetchone()
    if receipt and bool(receipt[2]):
        return "CONFIRMED", {"target": str(receipt[0]), "result": str(receipt[1])}
    if outcome and str(outcome[0]) == "NOT_EXECUTED":
        return "NOT_EXECUTED", None
    return "UNKNOWN", None


class AuthorityAgent(BaseAgent):
    def __init__(self, db: str, case: str) -> None:
        super().__init__("ContractGraph-QA AutoGen authority fixture")
        self.db = Path(db)
        self.case = case
        self.aid: str | None = None

    async def on_message_impl(self, message: Any, ctx: MessageContext) -> Any:
        del ctx
        if message not in {"subject", "recovery"}:
            raise ValueError(f"bad phase {message!r}")
        phase = str(message)
        if self.aid is None:
            if phase != "subject":
                raise RuntimeError("recovery without restored action identity")
            self.aid = action_id(self.case)
        aid = self.aid
        sql(self.db, "insert into entries(case_name,phase,action_id) values (?,?,?)",
            (self.case, phase, aid))

        if phase == "subject":
            issue_permit(self.db, self.case, aid, 1)
            sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                (self.case, aid, "dispatch"))
            if self.case == "not_executed":
                sql(self.db, "insert into outcomes values (?,?,'NOT_EXECUTED')", (self.case, aid))
                raise RuntimeError("injected pre-effect failure")
            commit_effect(
                self.db,
                self.case,
                aid,
                OTHER_TARGET if self.case == "mismatch" else TARGET,
                self.case != "unknown",
            )
            raise RuntimeError("injected lost response after effect")

        status, receipt = readback(self.db, self.case, aid)
        if status == "CONFIRMED":
            assert receipt is not None
            if receipt != {"target": TARGET, "result": RESULT}:
                sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                    (self.case, aid, "fail_closed_mismatch"))
                return {"status": "BLOCKED_MISMATCH"}
            sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                (self.case, aid, "return_prior"))
            return {"status": "RETURN_PRIOR", "result": RESULT}
        if status == "UNKNOWN":
            sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                (self.case, aid, "fail_closed_unknown"))
            return {"status": "BLOCKED_UNKNOWN"}
        if status == "NOT_EXECUTED":
            sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                (self.case, aid, "fresh_authorization_required"))
            issue_permit(self.db, self.case, aid, 2)
            sql(self.db, "insert into decisions(case_name,action_id,decision) values (?,?,?)",
                (self.case, aid, "dispatch"))
            commit_effect(self.db, self.case, aid, TARGET, True)
            return {"status": "FRESH_DISPATCH", "result": RESULT}
        raise RuntimeError(status)

    async def save_state(self) -> Mapping[str, Any]:
        return {
            "schema": "contractgraph.autogen-authority-agent-state.v0.1",
            "action_id": self.aid,
            "intent_hash": ihash(),
            "target": TARGET,
        }

    async def load_state(self, state: Mapping[str, Any]) -> None:
        if state.get("schema") != "contractgraph.autogen-authority-agent-state.v0.1":
            raise ValueError("bad state schema")
        if state.get("intent_hash") != ihash() or state.get("target") != TARGET:
            raise ValueError("restored intent/target mismatch")
        if not isinstance(state.get("action_id"), str):
            raise ValueError("action_id missing from restored state")
        self.aid = str(state["action_id"])


async def runtime_for(db: str, case: str) -> SingleThreadedAgentRuntime:
    r = SingleThreadedAgentRuntime()
    await AuthorityAgent.register(r, AGENT_TYPE, lambda: AuthorityAgent(db, case))
    return r


async def phase_subject(db: str, case: str, state_path: str) -> dict[str, Any]:
    r = await runtime_for(db, case)
    r.start()
    error = ""
    try:
        await r.send_message("subject", AgentId(AGENT_TYPE, AGENT_KEY))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    state = dict(await r.save_state())
    json.loads(json.dumps(state, sort_keys=True))
    if len(state) != 1:
        raise AssertionError(f"expected one agent state, got {state}")
    agent_state = next(iter(state.values()))
    if set(agent_state) != {"schema", "action_id", "intent_hash", "target"}:
        raise AssertionError(f"unexpected saved fields: {sorted(agent_state)}")
    if any("permit" in str(k).lower() for k in agent_state):
        raise AssertionError("permit leaked into AutoGen state")
    Path(state_path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    await r.stop_when_idle()
    return {"error": error, "saved_fields": sorted(agent_state),
            "saved_action_id": agent_state["action_id"], "permit_persisted": False}


async def phase_recovery(db: str, case: str, state_path: str) -> dict[str, Any]:
    state = json.loads(Path(state_path).read_text())
    r = await runtime_for(db, case)
    await r.load_state(state)
    if dict(await r.save_state()) != state:
        raise AssertionError("load/save changed identity state")
    r.start()
    result = await r.send_message("recovery", AgentId(AGENT_TYPE, AGENT_KEY))
    if dict(await r.save_state()) != state:
        raise AssertionError("recovery mutated persisted identity state")
    await r.stop_when_idle()
    if not isinstance(result, dict):
        raise AssertionError("recovery result is not a mapping")
    return result


def subprocess_json(argv: list[str]) -> dict[str, Any]:
    p = subprocess.run(argv, text=True, capture_output=True, timeout=60, check=False)
    if p.returncode:
        raise RuntimeError(f"subprocess failed {p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}")
    lines = [x for x in p.stdout.splitlines() if x.strip()]
    return json.loads(lines[-1])


def argv(script: Path, phase: str, case: str, db: Path, state: Path) -> list[str]:
    return [sys.executable, str(script), "--phase", phase, "--case", case,
            "--external-db", str(db), "--state", str(state)]


def snapshot(db: Path, case: str) -> dict[str, Any]:
    aid = action_id(case)
    with sqlite3.connect(db) as c:
        entries = c.execute("select phase,action_id from entries where case_name=? order by seq", (case,)).fetchall()
        decisions = c.execute("select decision from decisions where case_name=? order by seq", (case,)).fetchall()
        effects = c.execute("select action_id,target,result from effects where case_name=? order by seq", (case,)).fetchall()
        permits = c.execute("select generation,permit_id,consumed,consume_count from permits where case_name=? order by generation", (case,)).fetchall()
        receipt = c.execute("select target,result,visible from receipts where case_name=? and action_id=?", (case, aid)).fetchone()
        outcome = c.execute("select status from outcomes where case_name=? and action_id=?", (case, aid)).fetchone()
    return {
        "entries": [{"phase": str(x[0]), "action_id": str(x[1])} for x in entries],
        "decisions": [str(x[0]) for x in decisions],
        "effect_count": len(effects),
        "effects": [{"action_id": str(x[0]), "target": str(x[1]), "result": str(x[2])} for x in effects],
        "permits": [{"generation": int(x[0]), "permit_id": str(x[1]), "consumed": bool(x[2]), "consume_count": int(x[3])} for x in permits],
        "receipt": None if receipt is None else {"target": str(receipt[0]), "result": str(receipt[1]), "visible": bool(receipt[2])},
        "outcome": None if outcome is None else str(outcome[0]),
    }


def run_case(root: Path, case: str) -> dict[str, Any]:
    db, state = root / f"{case}.sqlite", root / f"{case}.json"
    init_db(db)
    script = Path(__file__).resolve()
    subject = subprocess_json(argv(script, "subject", case, db, state))
    before = snapshot(db, case)
    frozen = json.loads(state.read_text())
    agent_state = next(iter(frozen.values()))
    first = subprocess_json(argv(script, "recovery", case, db, state))
    after_first = snapshot(db, case)
    second = after_second = None
    if case == "unknown":
        sql(db, "update receipts set visible=1 where case_name=? and action_id=?", (case, action_id(case)))
        second = subprocess_json(argv(script, "recovery", case, db, state))
        after_second = snapshot(db, case)

    aid = action_id(case)
    identity_ok = agent_state == {
        "schema": "contractgraph.autogen-authority-agent-state.v0.1",
        "action_id": aid,
        "intent_hash": ihash(),
        "target": TARGET,
    }
    one_gen1 = len(after_first["permits"]) >= 1 and after_first["permits"][0]["generation"] == 1 and after_first["permits"][0]["consume_count"] == 1

    if case == "confirmed":
        passed = identity_ok and not subject["permit_persisted"] and first == {"status": "RETURN_PRIOR", "result": RESULT} and after_first["decisions"] == ["dispatch", "return_prior"] and after_first["effect_count"] == 1 and one_gen1
        verdict = "CONFIRMED_RETURN_PRIOR"
    elif case == "unknown":
        assert after_second is not None
        passed = identity_ok and not subject["permit_persisted"] and first == {"status": "BLOCKED_UNKNOWN"} and after_first["decisions"] == ["dispatch", "fail_closed_unknown"] and after_first["effect_count"] == 1 and second == {"status": "RETURN_PRIOR", "result": RESULT} and after_second["decisions"] == ["dispatch", "fail_closed_unknown", "return_prior"] and after_second["effect_count"] == 1 and len(after_second["permits"]) == 1
        verdict = "UNKNOWN_BLOCKED_THEN_CONFIRMED"
    elif case == "mismatch":
        passed = identity_ok and not subject["permit_persisted"] and first == {"status": "BLOCKED_MISMATCH"} and after_first["decisions"] == ["dispatch", "fail_closed_mismatch"] and after_first["effect_count"] == 1 and after_first["receipt"]["target"] == OTHER_TARGET and one_gen1
        verdict = "MISMATCH_FAIL_CLOSED"
    else:
        passed = identity_ok and not subject["permit_persisted"] and before["effect_count"] == 0 and before["outcome"] == "NOT_EXECUTED" and first == {"status": "FRESH_DISPATCH", "result": RESULT} and after_first["decisions"] == ["dispatch", "fresh_authorization_required", "dispatch"] and after_first["effect_count"] == 1 and [x["generation"] for x in after_first["permits"]] == [1, 2] and [x["consume_count"] for x in after_first["permits"]] == [1, 1] and after_first["permits"][0]["permit_id"] != after_first["permits"][1]["permit_id"]
        verdict = "NOT_EXECUTED_FRESH_AUTHORITY"

    all_entries = (after_second or after_first)["entries"]
    passed = passed and {x["action_id"] for x in all_entries} == {aid}
    return {"case": case, "passed": passed, "verdict": verdict if passed else "UNEXPECTED",
            "saved_agent_state": agent_state, "subject": subject, "before_recovery": before,
            "first_recovery": first, "after_first_recovery": after_first,
            "second_recovery": second, "after_second_recovery": after_second}


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cases = {case: run_case(root, case) for case in CASES}
    return {
        "schema": "contractgraph.autogen-runtime-authority.v0.1",
        "runtime": {"autogen_core": importlib.metadata.version("autogen-core")},
        "upstream": {"repository": "microsoft/autogen", "commit": AUTOGEN_SOURCE_COMMIT,
                     "package_version_at_commit": "0.7.5",
                     "state_boundary": "SingleThreadedAgentRuntime.save_state/load_state"},
        "claim": "AutoGen runtime save/load preserves stable action identity across fresh processes while execution permits remain external and recovery decisions follow the frozen authority profile.",
        "state_rule": "persist action_id, intent hash and target; never persist execution permit or derived replay authority",
        "cases": cases,
        "all_pass": all(x["passed"] for x in cases.values()),
        "non_claims": [
            "does not prove AutoGen natively implements retry deduplication or external reconciliation",
            "does not prove crash recovery of AutoGen runtime internals",
            "does not prove global exactly-once execution",
            "does not prove Byzantine external targets",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("subject", "recovery"))
    ap.add_argument("--case", choices=CASES)
    ap.add_argument("--external-db")
    ap.add_argument("--state")
    ap.add_argument("--write-report")
    a = ap.parse_args()
    if a.phase:
        if not a.case or not a.external_db or not a.state:
            ap.error("phase requires case, external-db and state")
        result = asyncio.run(phase_subject(a.external_db, a.case, a.state) if a.phase == "subject" else phase_recovery(a.external_db, a.case, a.state))
        print(json.dumps(result, sort_keys=True))
        return 0
    report = run()
    print("REPORT_JSON=" + json.dumps(report, sort_keys=True, separators=(",", ":")))
    if a.write_report:
        Path(a.write_report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
