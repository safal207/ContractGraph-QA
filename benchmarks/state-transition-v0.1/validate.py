#!/usr/bin/env python3
"""Validate the repository-owned ContractGraph-QA state-transition benchmark suite."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    suite = load_json(ROOT / "suite.json")
    invariant_doc = load_json(ROOT / "invariants.json")

    invariants = {item["id"]: item for item in invariant_doc["invariants"]}
    seen_case_ids: set[str] = set()
    failures: list[str] = []

    case_paths = suite.get("cases", [])
    if suite.get("expected_summary", {}).get("case_count") != len(case_paths):
        failures.append("suite expected_summary.case_count does not match cases length")

    for relative in case_paths:
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing case file: {relative}")
            continue

        case = load_json(path)
        case_id = case.get("id")
        if not case_id:
            failures.append(f"case without id: {relative}")
            continue
        if case_id in seen_case_ids:
            failures.append(f"duplicate case id: {case_id}")
        seen_case_ids.add(case_id)

        invariant_id = case.get("invariant")
        if invariant_id not in invariants:
            failures.append(f"{case_id}: unknown invariant {invariant_id!r}")

        if case.get("function_verification") != "PASS":
            failures.append(f"{case_id}: benchmark contract requires function_verification=PASS")
        if case.get("state_transition_verification") != "FAIL":
            failures.append(f"{case_id}: benchmark contract requires state_transition_verification=FAIL")
        if case.get("expected_verdict") != "FAIL":
            failures.append(f"{case_id}: benchmark contract requires expected_verdict=FAIL")

        counterexample = case.get("counterexample")
        if not isinstance(counterexample, list) or len(counterexample) < 2:
            failures.append(f"{case_id}: counterexample must contain at least two steps")

    if failures:
        print("state-transition-v0.1: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"state-transition-v0.1: PASS ({len(seen_case_ids)} cases, {len(invariants)} invariants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
