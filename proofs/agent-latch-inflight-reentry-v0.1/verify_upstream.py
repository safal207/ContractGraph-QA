from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

UPSTREAM_REPO = "https://github.com/AaronDai23/agent-latch.git"
UPSTREAM_COMMIT = "2c8b3c64b6c4e8cf3f91899a28251a5867947a57"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(
            f"{' '.join(args)} failed ({p.returncode})\n--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
        )
    return p


def require(haystack: str, needle: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"missing expected evidence: {needle!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="agent-latch-inflight-") as td:
        root = Path(td) / "agent-latch"
        run(["git", "clone", "--quiet", UPSTREAM_REPO, str(root)], Path(td))
        run(["git", "checkout", "--quiet", UPSTREAM_COMMIT], root)
        head = run(["git", "rev-parse", "HEAD"], root).stdout.strip()
        assert head == UPSTREAM_COMMIT, (head, UPSTREAM_COMMIT)

        run(["npm", "ci", "--no-audit", "--no-fund"], root)

        tests = run(["npm", "run", "test", "-w", "agent-latch-idempotency"], root)
        test_output = tests.stdout + "\n" + tests.stderr
        require(test_output, "active lease blocks other workers")
        require(test_output, "active lease blocks same worker re-entry (LangGraph-style)")
        require(test_output, "finance mode refuses blind re-execute without reconcile")
        require(test_output, "reconcile hit commits and replays without second side effect")

        demo = run(["npm", "run", "example:langgraph"], root)
        demo_output = demo.stdout + "\n" + demo.stderr
        require(demo_output, "executeCount (real side effects): 1")
        require(demo_output, "dispatch-2 (concurrent):")
        require(demo_output, "error_kind: 'idempotency'")
        require(demo_output, "dispatch-3 (after commit):")
        require(demo_output, "replayed: true")
        require(demo_output, "OK — checkpoint re-dispatch did not double-charge.")

        report = {
            "schema": "contractgraph.agent-latch-inflight-reentry.v0.1",
            "result": "PASS",
            "upstream": {
                "repo": "AaronDai23/agent-latch",
                "commit": UPSTREAM_COMMIT,
                "surface": "packages/idempotency + examples/langgraph",
            },
            "observed": {
                "active_lease_blocks_other_worker": True,
                "active_lease_blocks_same_worker_reentry": True,
                "finance_expired_or_unknown_requires_reconcile": True,
                "reconcile_hit_replays_without_second_effect": True,
                "langgraph_shaped_example_effect_count": 1,
                "concurrent_redispatch_denied": True,
                "post_commit_dispatch_replayed": True,
            },
            "claims": {
                "inflight_redispatch_authority": False,
                "lease_expiry_alone_proves_not_executed": False,
            },
            "untested": [
                "real @langchain/langgraph runtime integration",
                "LangGraph Cloud scheduler / Runs.Sweep stale detection",
                "~180s production timing window",
                "distributed store failure modes beyond upstream tests",
            ],
            "non_claims": [
                "This does not prove LangGraph Cloud exactly-once execution.",
                "This does not replace the merged LangGraph b1 crash/recovery proof in PR #179.",
                "This characterizes the pinned agent-latch adapter/example and keeps the cloud scheduler boundary UNTESTED.",
            ],
        }

        out = Path(".artifacts") / "agent-latch-inflight-reentry-report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
