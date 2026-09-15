from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

SCHEMA = "contractgraph.crewai-identity-authority-adapter.v0.1"
ISSUE = "https://github.com/safal207/ContractGraph-QA/issues/174"
PREDECESSORS = [
    "https://github.com/safal207/ContractGraph-QA/pull/171",
    "https://github.com/safal207/ContractGraph-QA/pull/173",
]
CREWAI_VERSION = "1.15.21"
TARGET = "ledger-A"
INTENT = "append-local-marker"
ARGS = {"marker": "harmless"}
TOOL_RESULT = "guarded-effect-acknowledged"
FINAL_RESULT = "logical action complete"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_action_id() -> str:
    return "act_" + canonical_hash({"intent": INTENT, "target": TARGET, "args": ARGS})[:32]


def stable_intent_hash() -> str:
    return canonical_hash({"intent": INTENT, "args": ARGS})


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        with self._connect() as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS permits(
                  permit_id TEXT PRIMARY KEY,
                  action_id TEXT NOT NULL,
                  target TEXT NOT NULL,
                  intent_hash TEXT NOT NULL,
                  consumed INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS effects(
                  receipt_id TEXT PRIMARY KEY,
                  action_id TEXT NOT NULL,
                  target TEXT NOT NULL,
                  intent_hash TEXT NOT NULL,
                  attempt INTEGER NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def issue_permit(self, action_id: str, target: str, ih: str) -> str:
        permit_id = "permit_" + canonical_hash(
            {"action_id": action_id, "target": target, "intent_hash": ih, "serial": 1}
        )[:24]
        with self._connect() as cx:
            cx.execute(
                "INSERT INTO permits(permit_id, action_id, target, intent_hash, consumed) VALUES (?, ?, ?, ?, 0)",
                (permit_id, action_id, target, ih),
            )
        return permit_id

    def consume_permit(
        self, permit_id: str, action_id: str, target: str, ih: str
    ) -> tuple[bool, str]:
        with self._connect() as cx:
            row = cx.execute(
                "SELECT action_id, target, intent_hash, consumed FROM permits WHERE permit_id = ?",
                (permit_id,),
            ).fetchone()
            if row is None:
                return False, "unknown_permit"
            if row[3]:
                return False, "reused_permit"
            if row[0] != action_id:
                return False, "action_mismatch"
            if row[1] != target:
                return False, "target_mismatch"
            if row[2] != ih:
                return False, "intent_mismatch"
            cx.execute("UPDATE permits SET consumed = 1 WHERE permit_id = ?", (permit_id,))
        return True, "consumed"

    def permit_consumed(self, permit_id: str) -> bool:
        with self._connect() as cx:
            row = cx.execute(
                "SELECT consumed FROM permits WHERE permit_id = ?", (permit_id,)
            ).fetchone()
        return bool(row and row[0])

    def append_effect(
        self, action_id: str, target: str, ih: str, attempt: int
    ) -> dict[str, Any]:
        receipt_id = "rcpt_" + canonical_hash(
            {
                "action_id": action_id,
                "target": target,
                "intent_hash": ih,
                "attempt": attempt,
            }
        )[:24]
        with self._connect() as cx:
            cx.execute(
                "INSERT INTO effects(receipt_id, action_id, target, intent_hash, attempt) VALUES (?, ?, ?, ?, ?)",
                (receipt_id, action_id, target, ih, attempt),
            )
        return {
            "status": "CONFIRMED",
            "receipt_id": receipt_id,
            "action_id": action_id,
            "target": target,
            "intent_hash": ih,
            "attempt": attempt,
        }

    def readback(self, action_id: str) -> dict[str, Any]:
        with self._connect() as cx:
            rows = cx.execute(
                "SELECT receipt_id, target, intent_hash, attempt FROM effects WHERE action_id = ? ORDER BY attempt",
                (action_id,),
            ).fetchall()
        if not rows:
            return {"status": "NOT_EXECUTED", "action_id": action_id}
        if len(rows) > 1:
            return {"status": "MULTIPLE", "action_id": action_id, "effect_count": len(rows)}
        receipt_id, target, ih, attempt = rows[0]
        return {
            "status": "CONFIRMED",
            "receipt_id": receipt_id,
            "action_id": action_id,
            "target": target,
            "intent_hash": ih,
            "attempt": attempt,
        }

    def effect_count(self, action_id: str) -> int:
        with self._connect() as cx:
            row = cx.execute(
                "SELECT COUNT(*) FROM effects WHERE action_id = ?", (action_id,)
            ).fetchone()
        assert row is not None
        return int(row[0])


def run_crewai_case(case: str, db_path: Path) -> dict[str, Any]:
    from crewai import Agent, Crew, Task
    from crewai.llms.base_llm import BaseLLM
    from crewai.tools import tool
    from pydantic import PrivateAttr

    if case not in {"baseline", "guarded"}:
        raise ValueError(case)

    action_id = stable_action_id()
    ih = stable_intent_hash()
    store = Store(db_path)
    permit_id = store.issue_permit(action_id, TARGET, ih) if case == "guarded" else None
    tool_attempts = 0
    decisions: list[str] = []

    class ScriptedLLM(BaseLLM):
        _calls: int = PrivateAttr(default=0)

        def supports_function_calling(self) -> bool:
            return False

        def call(
            self,
            messages: Any,
            tools: Any = None,
            callbacks: Any = None,
            available_functions: Any = None,
            from_task: Any = None,
            from_agent: Any = None,
            response_model: Any = None,
        ) -> str:
            self._calls += 1
            if self._calls == 1:
                return "Thought: execute the assigned action.\nAction: local_action\nAction Input: {}"
            if self._calls == 2 and TOOL_RESULT in str(messages):
                return f"Thought: action is complete.\nFinal Answer: {FINAL_RESULT}"
            raise RuntimeError("unexpected scripted LLM state")

    llm = ScriptedLLM(model="contractgraph-scripted", temperature=0)
    agent: Any = None

    @tool("local_action")
    def local_action() -> str:
        """Perform one deterministic local external effect."""
        nonlocal tool_attempts
        tool_attempts += 1

        if case == "guarded":
            readback = store.readback(action_id)
            if readback["status"] == "CONFIRMED":
                if readback["target"] != TARGET or readback["intent_hash"] != ih:
                    decisions.append("reject_receipt_mismatch")
                    raise RuntimeError("receipt mismatch")
                decisions.append("return_prior")
                return TOOL_RESULT
            if readback["status"] != "NOT_EXECUTED":
                decisions.append("fail_closed")
                raise RuntimeError("ambiguous external state")
            assert permit_id is not None
            ok, verdict = store.consume_permit(permit_id, action_id, TARGET, ih)
            if not ok:
                decisions.append(verdict)
                raise RuntimeError(verdict)
            decisions.append("dispatch")

        store.append_effect(action_id, TARGET, ih, tool_attempts)
        if tool_attempts == 1:
            raise RuntimeError("injected after-effect failure before tool return")
        return TOOL_RESULT

    agent = Agent(
        role="Deterministic operator",
        goal="Perform the assigned action exactly as instructed",
        backstory="A credential-free reliability fixture.",
        llm=llm,
        tools=[local_action],
        max_iter=3,
        max_retry_limit=0,
        cache=True,
        allow_delegation=False,
        verbose=False,
        checkpoint=False,
    )
    task = Task(
        description="Perform the assigned local action once.",
        expected_output=FINAL_RESULT,
        agent=agent,
    )
    crew = Crew(
        agents=[agent],
        tasks=[task],
        cache=True,
        memory=False,
        verbose=False,
        tracing=False,
        checkpoint=False,
    )

    output = crew.kickoff()
    effect_count = store.effect_count(action_id)

    if case == "baseline":
        verdict = "DUPLICATED" if effect_count == 2 and tool_attempts == 2 else "UNEXPECTED"
        passed = (
            output.raw == FINAL_RESULT
            and tool_attempts == 2
            and llm._calls == 2
            and effect_count == 2
            and agent._times_executed == 0
        )
    else:
        verdict = (
            "RECONCILED_NO_DUPLICATE"
            if effect_count == 1
            and tool_attempts == 2
            and decisions == ["dispatch", "return_prior"]
            else "UNEXPECTED"
        )
        passed = (
            output.raw == FINAL_RESULT
            and tool_attempts == 2
            and llm._calls == 2
            and effect_count == 1
            and decisions == ["dispatch", "return_prior"]
            and permit_id is not None
            and store.permit_consumed(permit_id)
            and agent._times_executed == 0
        )

    return {
        "case": case,
        "action_id": action_id,
        "intent_hash": ih,
        "tool_attempts": tool_attempts,
        "llm_calls": llm._calls,
        "agent_retries": agent._times_executed,
        "effect_count": effect_count,
        "guard_decisions": decisions,
        "permit_id": permit_id,
        "permit_consumed": store.permit_consumed(permit_id) if permit_id else None,
        "runtime_result": output.raw,
        "verdict": verdict,
        "passed": passed,
    }


def run_suite() -> dict[str, Any]:
    actual_version = version("crewai")
    with tempfile.TemporaryDirectory(prefix="cgqa-crewai-") as td:
        root = Path(td)
        baseline = run_crewai_case("baseline", root / "baseline.sqlite")
        guarded = run_crewai_case("guarded", root / "guarded.sqlite")

    same_identity = baseline["action_id"] == guarded["action_id"]
    passed = (
        actual_version == CREWAI_VERSION
        and baseline["passed"]
        and guarded["passed"]
        and same_identity
    )

    return {
        "schema": SCHEMA,
        "issue": ISSUE,
        "predecessors": PREDECESSORS,
        "runtime": {"name": "crewai", "version": actual_version},
        "result": "PASS" if passed else "FAIL",
        "same_action_identity_across_ab": same_identity,
        "baseline": baseline,
        "guarded": guarded,
        "invariant": (
            "A CrewAI retry may re-enter the tool, but a matching external receipt for the "
            "same stable action identity is evidence to return the prior result, not authority "
            "to perform the side effect again."
        ),
        "claim_ceiling": [
            "same-process synchronous CrewAI 1.15.21 retry path only",
            "local SQLite is outside CrewAI runtime state but is not a separate host/process",
            "not a CrewAI framework fix",
            "no crash or fresh-worker recovery claim",
            "no checkpoint/resume claim",
            "no global exactly-once claim",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    report = run_suite()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        args.write_report.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
