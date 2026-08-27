"""Build deterministic LTP fixtures from the CGQA-generated escrow input."""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "generated-pass-continuity-input.json"
CASES = ROOT / "cases"


def write(name: str, value: object) -> None:
    destination = CASES / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def request(source: dict[str, object], request_id: str, attempt_id: str) -> dict[str, object]:
    rows = source["requests"]
    assert isinstance(rows, list)
    result = next(
        copy.deepcopy(row)
        for row in rows
        if row["request_id"] == request_id and row["attempt_id"] == attempt_id
    )
    result["parent_request_id"] = None
    return result


def outcome(source: dict[str, object], outcome_id: str) -> dict[str, object]:
    rows = source["outcomes"]
    assert isinstance(rows, list)
    return next(copy.deepcopy(row) for row in rows if row["outcome_id"] == outcome_id)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    as_of = source["as_of"]
    release_1 = request(source, "release-escrow-42", "release-attempt-1")
    release_2 = request(source, "release-escrow-42", "release-attempt-2")
    canonical = outcome(source, "release-receipt-42")

    one_request = copy.deepcopy(release_2)
    one_request["retry_of_attempt_id"] = None
    write(
        "pass-one-request.json",
        {"as_of": as_of, "requests": [one_request], "outcomes": [canonical]},
    )
    write("pass-timeout-retry.json", source)

    write(
        "broken-missing-outcome.json",
        {"as_of": as_of, "requests": [release_1], "outcomes": []},
    )
    orphan = copy.deepcopy(canonical)
    orphan["request_id"] = "release-without-request"
    orphan["trace_id"] = "orphan-trace"
    orphan["attempt_id"] = "orphan-attempt"
    orphan["outcome_id"] = "orphan-release-event"
    write(
        "broken-orphan-response.json",
        {"as_of": as_of, "requests": [], "outcomes": [orphan]},
    )

    conflict = copy.deepcopy(canonical)
    conflict["outcome_id"] = "release-dispute-conflict-42"
    conflict["terminal_status"] = "CANCELLED"
    conflict["result_digest"] = "sha256:" + "f1" * 32
    write(
        "broken-conflicting-outcomes.json",
        {"as_of": as_of, "requests": [one_request], "outcomes": [canonical, conflict]},
    )

    retry_gap = copy.deepcopy(release_2)
    retry_gap["retry_of_attempt_id"] = "release-attempt-missing"
    write(
        "broken-retry-gap.json",
        {
            "as_of": as_of,
            "requests": [release_1, retry_gap],
            "outcomes": [canonical],
        },
    )

    trace_mismatch = copy.deepcopy(source)
    next(
        row
        for row in trace_mismatch["outcomes"]
        if row["outcome_id"] == "indexer-updated-42"
    )["trace_id"] = "wrong-indexer-trace"
    write("broken-trace-mismatch.json", trace_mismatch)

    missing_indexer = copy.deepcopy(source)
    missing_indexer["outcomes"] = [
        row
        for row in missing_indexer["outcomes"]
        if row["outcome_id"] != "indexer-updated-42"
    ]
    write("broken-indexer-missing-outcome.json", missing_indexer)

    second_payment = copy.deepcopy(canonical)
    second_payment["outcome_id"] = "release-receipt-attempt-1"
    second_payment["attempt_id"] = "release-attempt-1"
    second_payment["occurred_at"] = "2026-08-27T10:00:10Z"
    second_payment["result_digest"] = "sha256:" + "f2" * 32
    write(
        "broken-double-payment-attempts.json",
        {
            "as_of": as_of,
            "requests": [release_1, release_2],
            "outcomes": [second_payment, canonical],
        },
    )

    write(
        "replay-detected.json",
        {
            "as_of": as_of,
            "requests": [one_request],
            "outcomes": [canonical, copy.deepcopy(canonical)],
        },
    )

    duplicate_owner = copy.deepcopy(one_request)
    duplicate_owner["request_id"] = "different-logical-request"
    duplicate_owner["trace_id"] = "different-logical-trace"
    write(
        "invalid-duplicate-attempt-owner.json",
        {
            "as_of": as_of,
            "requests": [one_request, duplicate_owner],
            "outcomes": [canonical],
        },
    )
    invalid_schema = {
        "as_of": as_of,
        "requests": [one_request],
        "outcomes": [canonical],
        "unexpected": True,
    }
    write("invalid-schema.json", invalid_schema)

    matrix = {
        "schemaVersion": "cgqa-smart-contract-continuity-fixture-matrix-v0.1",
        "cases": [
            {"caseId": "one_request_completed", "file": "pass-one-request.json", "expectedExit": 0, "expectedStatus": "CONTINUOUS", "expectedFindingCodes": []},
            {"caseId": "timeout_retry_one_outcome", "file": "pass-timeout-retry.json", "expectedExit": 0, "expectedStatus": "CONTINUOUS", "expectedFindingCodes": []},
            {"caseId": "missing_outcome", "file": "broken-missing-outcome.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_MISSING_OUTCOME"]},
            {"caseId": "orphan_response", "file": "broken-orphan-response.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_ORPHAN_RESPONSE"]},
            {"caseId": "conflicting_outcomes", "file": "broken-conflicting-outcomes.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_CONFLICTING_OUTCOMES"]},
            {"caseId": "retry_gap", "file": "broken-retry-gap.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_RETRY_GAP"]},
            {"caseId": "trace_mismatch", "file": "broken-trace-mismatch.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_TRACE_MISMATCH"]},
            {"caseId": "indexer_missing_outcome", "file": "broken-indexer-missing-outcome.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_MISSING_OUTCOME"]},
            {"caseId": "both_attempts_paid", "file": "broken-double-payment-attempts.json", "expectedExit": 2, "expectedStatus": "BROKEN", "expectedFindingCodes": ["BROKEN_CONFLICTING_OUTCOMES"]},
            {"caseId": "exact_replay", "file": "replay-detected.json", "expectedExit": 0, "expectedStatus": "CONTINUOUS", "expectedFindingCodes": ["REPLAY_DETECTED"]},
            {"caseId": "attempt_reused_by_two_requests", "file": "invalid-duplicate-attempt-owner.json", "expectedExit": 1, "expectedStatus": None, "expectedFindingCodes": []},
            {"caseId": "invalid_schema", "file": "invalid-schema.json", "expectedExit": 1, "expectedStatus": None, "expectedFindingCodes": []}
        ]
    }
    write("fixture-matrix.json", matrix)


if __name__ == "__main__":
    main()
