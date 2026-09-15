#!/usr/bin/env python3
"""Run the six repository-owned PCT v0.1 fixtures deterministically."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contractgraph_qa.agent_trajectory import (  # noqa: E402
    evaluate_agent_trajectory_scenario,
    load_agent_trajectory_scenario,
)

CASES_DIR = Path(__file__).resolve().parent / "cases"
EXPECTED_CASE_NAMES = {
    "fail_handoff_after_unknown_redispatch.json",
    "fail_lost_ack_crash_resume_redispatch.json",
    "fail_stale_observer_retry.json",
    "pass_handoff_after_unknown_reconcile.json",
    "pass_lost_ack_crash_resume_reconcile.json",
    "pass_stale_observer_reconcile.json",
}


def main() -> int:
    rows: list[dict[str, object]] = []
    all_match = True

    paths = sorted(CASES_DIR.glob("*.json"))
    actual_case_names = {path.name for path in paths}
    if actual_case_names != EXPECTED_CASE_NAMES:
        summary = {
            "benchmark": "proof-carrying-agent-trajectories-v0.1",
            "matrixStatus": "invalid_matrix",
            "cases": len(paths),
            "matched": 0,
            "missingCases": sorted(EXPECTED_CASE_NAMES - actual_case_names),
            "unexpectedCases": sorted(actual_case_names - EXPECTED_CASE_NAMES),
            "results": [],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
        return 2

    for path in paths:
        scenario = load_agent_trajectory_scenario(path)
        expected_status = scenario.get("expectedStatus")
        expected_codes_raw = scenario.get("expectedViolationCodes", [])
        if expected_status not in {"pass", "fail"}:
            raise ValueError(f"{path.name}: expectedStatus must be pass or fail")
        if not isinstance(expected_codes_raw, list) or not all(
            isinstance(code, str) for code in expected_codes_raw
        ):
            raise ValueError(f"{path.name}: expectedViolationCodes must be an array of strings")

        result = evaluate_agent_trajectory_scenario(scenario)
        observed_codes = sorted(str(item["code"]) for item in result["violations"])
        expected_codes = sorted(expected_codes_raw)
        matched = result["status"] == expected_status and observed_codes == expected_codes
        all_match = all_match and matched

        rows.append(
            {
                "case": path.name,
                "policy": result["policy"],
                "expectedStatus": expected_status,
                "observedStatus": result["status"],
                "expectedViolationCodes": expected_codes,
                "observedViolationCodes": observed_codes,
                "match": matched,
            }
        )

    summary = {
        "benchmark": "proof-carrying-agent-trajectories-v0.1",
        "matrixStatus": "pass" if all_match else "mismatch",
        "cases": len(rows),
        "matched": sum(1 for row in rows if row["match"]),
        "results": rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
