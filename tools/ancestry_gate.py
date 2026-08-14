#!/usr/bin/env python3
"""Evaluate the machine-only P0-4 exact-subject and ancestry gate."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "cgqa.p0-4-ancestry-gate.v0.1"
PASS = "PASS"
HOLD = "HOLD"
NOT_RUN = "NOT_RUN"
INCOMPLETE = "INCOMPLETE"


class AncestryGateError(ValueError):
    """Raised when the ancestry gate cannot produce a valid report."""


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AncestryGateError(f"{field} must be a non-empty string")
    return value.strip()


def _check_equal(actual: object, expected: object, field: str) -> dict[str, Any]:
    if not isinstance(actual, str) or not actual.strip() or not isinstance(expected, str) or not expected.strip():
        return {"status": INCOMPLETE, "actual": actual, "expected": expected}
    status = PASS if actual == expected else HOLD
    return {"status": status, "actual": actual, "expected": expected}


def evaluate_gate(
    *,
    initial_subject: object,
    final_subject: object,
    expected_subject: object,
    expected_base: object,
    ancestry: object,
    workflow_name: object,
    workflow_ref: object,
    run_id: object,
    run_attempt: object,
    expected_workflow_file: object,
    artifact_subject: object,
) -> dict[str, Any]:
    """Return an explicit PASS/HOLD/NOT_RUN/INCOMPLETE report.

    `ancestry` is a tri-state value: True means the git command proved ancestry,
    False means it disproved ancestry, and None means the command was not run or
    its result was unavailable.
    """

    expected_subject_text = expected_subject if isinstance(expected_subject, str) else None
    expected_base_text = expected_base if isinstance(expected_base, str) else None
    checks: dict[str, dict[str, Any]] = {
        "initial_subject": _check_equal(initial_subject, expected_subject, "initial_subject"),
        "final_subject": _check_equal(final_subject, expected_subject, "final_subject"),
        "artifact_subject": _check_equal(artifact_subject, expected_subject, "artifact_subject"),
    }

    if not isinstance(expected_base_text, str) or not expected_base_text.strip():
        checks["ancestry"] = {"status": INCOMPLETE, "expected_base": expected_base}
    elif ancestry is True:
        checks["ancestry"] = {"status": PASS, "expected_base": expected_base_text, "subject": expected_subject_text}
    elif ancestry is False:
        checks["ancestry"] = {"status": HOLD, "expected_base": expected_base_text, "subject": expected_subject_text}
    else:
        checks["ancestry"] = {"status": NOT_RUN, "expected_base": expected_base_text, "subject": expected_subject_text}

    workflow_values = [workflow_name, workflow_ref, run_id, run_attempt, expected_workflow_file]
    if not all(isinstance(value, str) and value.strip() for value in workflow_values):
        checks["workflow_identity"] = {
            "status": INCOMPLETE,
            "workflow_name": workflow_name,
            "workflow_ref": workflow_ref,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "expected_workflow_file": expected_workflow_file,
        }
    elif str(expected_workflow_file) not in str(workflow_ref):
        checks["workflow_identity"] = {
            "status": HOLD,
            "workflow_name": workflow_name,
            "workflow_ref": workflow_ref,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "expected_workflow_file": expected_workflow_file,
        }
    else:
        checks["workflow_identity"] = {
            "status": PASS,
            "workflow_name": _text(workflow_name, "workflow_name"),
            "workflow_ref": _text(workflow_ref, "workflow_ref"),
            "run_id": _text(run_id, "run_id"),
            "run_attempt": _text(run_attempt, "run_attempt"),
            "expected_workflow_file": _text(expected_workflow_file, "expected_workflow_file"),
        }

    statuses = [item["status"] for item in checks.values()]
    if all(status == PASS for status in statuses):
        decision = PASS
    elif HOLD in statuses:
        decision = HOLD
    elif INCOMPLETE in statuses:
        decision = INCOMPLETE
    else:
        decision = NOT_RUN

    return {
        "schema": SCHEMA,
        "decision": decision,
        "checks": checks,
        "unknown_state_policy": "unknown_never_becomes_pass",
        "authority": "advisory only; no merge, deployment, production or security authorization",
    }


def _git_head(repo: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AncestryGateError(f"cannot resolve final git subject: {exc}") from exc


def _git_ancestry(repo: Path, base: str, subject: str) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", base, subject],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def capture_report(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo)
    final_subject = _git_head(repo)
    ancestry = _git_ancestry(repo, args.expected_base, args.expected_subject)
    report = evaluate_gate(
        initial_subject=args.initial_subject,
        final_subject=final_subject,
        expected_subject=args.expected_subject,
        expected_base=args.expected_base,
        ancestry=ancestry,
        workflow_name=args.workflow_name,
        workflow_ref=args.workflow_ref,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        expected_workflow_file=args.expected_workflow_file,
        artifact_subject=args.artifact_subject,
    )
    report.update(
        {
            "repository": args.repository,
            "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "initial_subject": args.initial_subject,
            "final_subject": final_subject,
            "expected_subject": args.expected_subject,
            "expected_base": args.expected_base,
            "artifact_subject": args.artifact_subject,
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--initial-subject", required=True)
    parser.add_argument("--expected-subject", required=True)
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--workflow-ref", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--expected-workflow-file", required=True)
    parser.add_argument("--artifact-subject", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = capture_report(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"P0_4_ANCESTRY_GATE_{report['decision']}")
        return 0 if report["decision"] == PASS else 2
    except (OSError, AncestryGateError) as exc:
        print(f"P0_4_ANCESTRY_GATE_{INCOMPLETE} {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
