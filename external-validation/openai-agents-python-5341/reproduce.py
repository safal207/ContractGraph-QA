#!/usr/bin/env python3
"""Independent public-boundary RunState checks for openai-agents-python #5341.

No SDK patch, live model, real credentials, network access, or privileged tools.
Save and resume execute in different Python processes; each builds a new graph.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def deny_network(event: str, args: tuple) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        raise RuntimeError(f"NETWORK_ATTEMPT_BLOCKED:{event}")


async def child(args: argparse.Namespace) -> None:
    sys.addaudithook(deny_network)
    from agents import Agent, AgentHooks, Runner, RunState, function_tool, set_tracing_disabled
    from agents.testing import ScriptedModel, assistant_message, function_call
    import agents

    set_tracing_disabled(True)
    effects: list[dict[str, str]] = []

    class CountingHooks(AgentHooks):
        def __init__(self) -> None:
            self.event_counter = 0

        async def on_start(self, context, agent) -> None:
            self.event_counter += 1

    def make_tool(owner: str):
        @function_tool(name_override="record_effect", needs_approval=True)
        def record_effect(operation: str) -> str:
            """Record a synthetic memory-only effect for an approved operation."""
            effects.append({"owner": owner, "operation": operation})
            return f"recorded-{owner}-{operation}"

        return record_effect

    def call(operation: str, call_id: str):
        return function_call("record_effect", {"operation": operation}, call_id=call_id)

    # Saving uses d1. A restored provider continuation emits d2, not d1 again.
    x_model = ScriptedModel([[call("follow-up-op", "d2")], [assistant_message("done-x")]])
    if args.phase == "save":
        y_model = ScriptedModel([[call("approved-op", "d1")], [assistant_message("done-y")]])
    else:
        y_model = ScriptedModel([[call("follow-up-op", "d2")], [assistant_message("done-y")]])
    same_names = args.names == "same"
    x = Agent(name="sub" if same_names else "sub-x", instructions="b",
              model=x_model, tools=[make_tool("x")], hooks=CountingHooks())
    y = Agent(name="sub" if same_names else "sub-y", instructions="a",
              model=y_model, tools=[make_tool("y")], hooks=CountingHooks())
    from agents import handoff
    root = Agent(name="root", model=ScriptedModel([[function_call("to_y", {}, call_id="h1")]]),
                 handoffs=[handoff(x, tool_name_override="to_x"),
                           handoff(y, tool_name_override="to_y")])
    module_root = Path(agents.__file__).resolve().parent
    identity_path = module_root / "_run_state_agent_identity.py"
    provenance = {
        "sdk_distribution_version": importlib.metadata.version("openai-agents"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "identity_source_sha256": hashlib.sha256(identity_path.read_bytes()).hexdigest(),
        "sdk_import_root": str(module_root),
        "identity_source_path": str(identity_path),
        "pid": os.getpid(),
        "network_policy": "Python audit denies connect/getaddrinfo/sendto; tracing disabled",
    }
    if args.phase == "save":
        first = await Runner.run(root, "Synthetic request", max_turns=5)
        if first.last_agent is not y or len(first.interruptions) != 1 or effects:
            raise RuntimeError("INVALID_SETUP: expected Y/d1 interruption before any effect")
        pending = first.interruptions[0]
        if (pending.agent is not y or pending.name != "record_effect"
                or pending.raw_item.call_id != "d1"
                or json.loads(pending.raw_item.arguments) != {"operation": "approved-op"}):
            raise RuntimeError("INVALID_SETUP: expected exact Y/record_effect/d1/approved-op")
        state = first.to_state()
        state.approve(first.interruptions[0], always_approve=args.approval == "sticky")
        data = json.loads(json.dumps(state.to_json()))
        write_json(args.case_dir / "state.json", data)
        write_json(args.case_dir / "save.json", {
            **provenance, "effects": effects, "saved_current_agent": data.get("current_agent"),
            "hook_counters": {"x": x.hooks.event_counter, "y": y.hooks.event_counter},
        })
        return

    saved = json.loads((args.case_dir / "save.json").read_text())
    data = json.loads((args.case_dir / "state.json").read_text())
    if args.hooks == "preserve":
        x.hooks.event_counter = saved["hook_counters"]["x"]
        y.hooks.event_counter = saved["hook_counters"]["y"]
    result = {
        **provenance, "fresh_graph": True, "separate_process": os.getpid() != saved["pid"],
        "initial_hook_counters": {"x": x.hooks.event_counter, "y": y.hooks.event_counter},
    }
    stage = "restore"
    try:
        restored = await RunState.from_json(root, data)
        # Private field is diagnostic only; the oracle below uses real tool effects.
        result["restored_owner_diagnostic"] = "y" if restored._current_agent is y else (
            "x" if restored._current_agent is x else "other")
        stage = "run"
        resumed = await Runner.run(root, restored, max_turns=5)
        stage = "collect_observation"
        result["last_agent_owner"] = "y" if resumed.last_agent is y else (
            "x" if resumed.last_agent is x else "other")
        result["final_output"] = resumed.final_output
        result["interruptions"] = [
            {"agent_owner": "y" if item.agent is y else "x" if item.agent is x else "other",
             "tool_name": item.name, "call_id": item.raw_item.call_id}
            for item in resumed.interruptions
        ]
        result["outcome"] = "RETURNED"
    except Exception as exc:
        result["outcome"] = "HARNESS_ERROR" if stage == "collect_observation" else "SDK_ERROR"
        result["error"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
    result["effects"] = effects
    result["model_calls"] = {"x": len(x_model.calls), "y": len(y_model.calls)}
    write_json(args.case_dir / "resume.json", result)


def expected(approval: str, owner: str = "y") -> dict:
    effects = [{"owner": owner, "operation": "approved-op"}]
    if approval == "sticky":
        effects.append({"owner": owner, "operation": "follow-up-op"})
    return {
        "effects": effects,
        "interruptions": [] if approval == "sticky" else [
            {"agent_owner": owner, "tool_name": "record_effect", "call_id": "d2"}],
        "final_output": f"done-{owner}" if approval == "sticky" else None,
        "last_agent_owner": owner,
    }


def matrix(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=False)
    runner = Path(__file__).resolve()
    env = {"PATH": "/usr/bin:/bin", "OPENAI_AGENTS_DISABLE_TRACING": "1",
           "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"}
    if args.sdk_src:
        env["PYTHONPATH"] = str(args.sdk_src.resolve())
    rows = []
    for names, hooks, approval in itertools.product(
        ("same", "unique"), ("preserve", "reset"), ("single", "sticky")
    ):
        case_id = f"{names}-{hooks}-{approval}"
        case_dir = args.output / case_id
        case_dir.mkdir()
        for phase in ("save", "resume"):
            command = [sys.executable, str(runner), "--phase", phase, "--case-dir", str(case_dir),
                       "--names", names, "--hooks", hooks, "--approval", approval]
            proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
            (case_dir / f"{phase}.stdout.txt").write_text(proc.stdout)
            (case_dir / f"{phase}.stderr.txt").write_text(proc.stderr)
            if proc.returncode:
                raise RuntimeError(f"HARNESS_ERROR:{case_id}:{phase}: see captured stderr")
        observed = json.loads((case_dir / "resume.json").read_text())
        wanted = expected(approval)
        checks = {key: observed.get(key) == value for key, value in wanted.items()}
        checks["separate_process"] = observed["separate_process"] is True
        checks["returned"] = observed["outcome"] == "RETURNED"
        row = {"case": case_id, "expected": wanted, "observed": observed,
               "checks": checks, "contract": "ERROR" if observed["outcome"] != "RETURNED" else (
                   "PASS" if all(checks.values()) else "FAIL")}
        rows.append(row)
        print(f"{case_id}: {row['contract']} effects={observed['effects']}", flush=True)
    write_json(args.output / "results.json", {"schema": "sdk-5341-fresh-graph-matrix/1",
               "sdk_source_label": args.label, "cases": rows,
               "pass_count": sum(r["contract"] == "PASS" for r in rows),
               "fail_count": sum(r["contract"] == "FAIL" for r in rows),
               "error_count": sum(r["contract"] == "ERROR" for r in rows)})
    # A completed measurement is not SDK conformance. --expect-known-bug validates
    # the separately stated baseline pattern and still preserves FAIL verdicts.
    if args.expect_known_bug:
        for row in rows:
            if row["case"].startswith("same-reset-"):
                approval = row["case"].rsplit("-", 1)[1]
                observed = row["observed"]
                if (row["contract"] != "FAIL" or observed["outcome"] != "RETURNED"
                        or not observed["separate_process"]
                        or any(observed.get(k) != v for k, v in expected(approval, "x").items())):
                    return 2
            elif row["contract"] != "PASS":
                return 2
        return 0
    return 0 if all(r["contract"] == "PASS" for r in rows) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("save", "resume"))
    parser.add_argument("--case-dir", type=Path)
    parser.add_argument("--names", choices=("same", "unique"))
    parser.add_argument("--hooks", choices=("preserve", "reset"))
    parser.add_argument("--approval", choices=("single", "sticky"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sdk-src", type=Path)
    parser.add_argument("--label", default="installed openai-agents")
    parser.add_argument("--expect-known-bug", action="store_true")
    args = parser.parse_args()
    if args.phase:
        asyncio.run(child(args))
        return 0
    if args.output is None:
        parser.error("matrix mode requires --output")
    return matrix(args)


if __name__ == "__main__":
    raise SystemExit(main())
