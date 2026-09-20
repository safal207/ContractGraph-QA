#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SYSTEM_CASE = "EXECUTION-RECEIPT-AEGISORA-001"
UPSTREAM_COMMIT = "2bac618215671f6f0ac8ebddf169830d4fc0f9b3"


def fail(message: str) -> None:
    raise SystemExit(f"{SYSTEM_CASE} FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_receipt_hash(receipt: dict) -> None:
    supplied = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    actual = hashlib.sha256(canonical(body)).hexdigest()
    require(supplied == actual, "receipt SHA-256 mismatch")


def verify_pair(receipts: list[dict], *, expected_terminal: str, expected_external: str) -> None:
    require(len(receipts) == 2, "expected PENDING + TERMINAL receipt pair")
    pending, terminal = receipts
    require(pending.get("phase") == "PENDING", "first receipt is not PENDING")
    require(pending.get("local_outcome") == "NOT_OBSERVED", "PENDING upgraded local outcome")
    require(pending.get("external_effect_status") == "UNKNOWN", "PENDING upgraded external truth")

    require(terminal.get("phase") == "TERMINAL", "second receipt is not TERMINAL")
    require(terminal.get("local_outcome") == expected_terminal, "terminal local outcome drift")
    require(
        terminal.get("external_effect_status") == expected_external,
        "terminal external effect semantics drift",
    )

    for field in (
        "action_id",
        "adapter_call_id",
        "target",
        "payload_digest",
        "trace_id",
        "decision_id",
        "execution_id",
        "evidence_id",
    ):
        require(pending.get(field) == terminal.get(field), f"receipt pair binding mismatch: {field}")

    verify_receipt_hash(pending)
    verify_receipt_hash(terminal)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.report.read_bytes()
    report = json.loads(raw)

    require(report.get("system_case") == SYSTEM_CASE, "wrong system_case")
    require(report.get("status") == "PASS", "subject RED->GREEN probe did not PASS")
    require(
        report.get("upstream", {}).get("repository") == "aegisora-ai/aegisora",
        "wrong upstream repository",
    )
    require(
        report.get("upstream", {}).get("commit") == UPSTREAM_COMMIT,
        "wrong upstream commit",
    )
    require(
        report.get("red_green")
        == "RED(native current execution evidence coverage) -> GREEN(minimal external receipt adapter)",
        "unexpected RED->GREEN declaration",
    )

    contract = report.get("contract", {})
    require(
        "PENDING/UNKNOWN" in str(contract.get("pending_semantics", "")),
        "PENDING semantics missing",
    )
    require(
        "UNVERIFIED" in str(contract.get("terminal_success_semantics", "")),
        "success external-truth ceiling missing",
    )
    require(
        "UNKNOWN" in str(contract.get("terminal_throw_semantics", "")),
        "throw uncertainty ceiling missing",
    )

    native = report.get("native", {})
    require(native.get("verdict") == "RED", "native subject did not reproduce RED")
    require(native.get("expected_red") is True, "native RED was not expected/frozen")
    require(native.get("terminal_coverage") == 1, "native terminal coverage is not 1/3")
    require(native.get("total_allowed_cases") == 3, "native case count drift")

    native_cases = native.get("cases", {})
    n_usage = native_cases.get("success_with_usage", {})
    n_no_usage = native_cases.get("success_without_usage", {})
    n_throw = native_cases.get("provider_throws", {})

    require(n_usage.get("allow_audit") is True, "native usage case missing ALLOW audit")
    require(
        n_usage.get("terminal_execution_evidence") is True,
        "native usage case missing terminal evidence",
    )
    require(n_usage.get("local_provider_calls") == 1, "native usage provider calls drift")

    require(n_no_usage.get("allow_audit") is True, "native no-usage case missing ALLOW audit")
    require(
        n_no_usage.get("terminal_execution_evidence") is False,
        "native no-usage unexpectedly has terminal evidence",
    )
    require(n_no_usage.get("usage_event_count_delta") == 0, "native no-usage event delta drift")
    require(n_no_usage.get("local_provider_calls") == 1, "native no-usage provider calls drift")

    require(n_throw.get("allow_audit") is True, "native throw case missing ALLOW audit")
    require(
        n_throw.get("terminal_execution_evidence") is False,
        "native throw unexpectedly has terminal evidence",
    )
    require(n_throw.get("usage_event_count_delta") == 0, "native throw event delta drift")
    require(n_throw.get("local_provider_calls") == 1, "native throw provider calls drift")
    require(
        "synthetic-provider-failure" in str(n_throw.get("error", "")),
        "native throw error drift",
    )

    adapter = report.get("adapter", {})
    require(adapter.get("verdict") == "GREEN", "adapter did not reach GREEN")
    require(adapter.get("expected_green") is True, "adapter GREEN was not frozen")
    require(adapter.get("terminal_coverage") == 3, "adapter terminal coverage is not 3/3")
    require(adapter.get("total_allowed_cases") == 3, "adapter case count drift")
    require(adapter.get("receipt_count") == 6, "adapter receipt count drift")

    adapter_cases = adapter.get("cases", {})
    a_usage = adapter_cases.get("success_with_usage", {})
    a_no_usage = adapter_cases.get("success_without_usage", {})
    a_throw = adapter_cases.get("provider_throws", {})

    require(a_usage.get("provider_calls") == 1, "adapter usage provider calls drift")
    verify_pair(
        a_usage.get("receipts", []),
        expected_terminal="RETURNED_SUCCESS",
        expected_external="UNVERIFIED",
    )
    require(
        a_usage.get("receipts", [None, {}])[1].get("usage_present") is True,
        "usage-bearing terminal lost usage presence",
    )

    require(a_no_usage.get("provider_calls") == 1, "adapter no-usage provider calls drift")
    verify_pair(
        a_no_usage.get("receipts", []),
        expected_terminal="RETURNED_SUCCESS",
        expected_external="UNVERIFIED",
    )
    require(
        a_no_usage.get("receipts", [None, {}])[1].get("usage_present") is False,
        "no-usage terminal incorrectly claims usage",
    )

    require(a_throw.get("provider_calls") == 1, "adapter throw provider calls drift")
    require(
        "synthetic-provider-failure" in str(a_throw.get("error", "")),
        "adapter throw error drift",
    )
    verify_pair(
        a_throw.get("receipts", []),
        expected_terminal="THREW",
        expected_external="UNKNOWN",
    )
    throw_terminal = a_throw.get("receipts", [None, {}])[1]
    require(
        isinstance(throw_terminal.get("error_digest"), str)
        and len(throw_terminal.get("error_digest")) == 64,
        "throw terminal missing error digest",
    )

    all_receipts = (
        a_usage.get("receipts", [])
        + a_no_usage.get("receipts", [])
        + a_throw.get("receipts", [])
    )
    prior = None
    for receipt in all_receipts:
        require(
            receipt.get("previous_receipt_sha256") == prior,
            "global append-only receipt chain discontinuity",
        )
        prior = receipt.get("receipt_sha256")

    subject_sha256 = hashlib.sha256(raw).hexdigest()
    verified = {
        "system_case": SYSTEM_CASE,
        "status": "PASS",
        "finding": "NATIVE_RED_ADAPTER_GREEN",
        "upstream_commit": UPSTREAM_COMMIT,
        "subject_report_sha256": subject_sha256,
        "native": {
            "verdict": "RED",
            "terminal_coverage": "1/3",
            "missing_terminal_cases": [
                "successful provider response without usage",
                "provider invocation that throws",
            ],
        },
        "adapter": {
            "verdict": "GREEN",
            "terminal_coverage": "3/3",
            "receipt_model": "PENDING -> TERMINAL",
            "success_external_effect_status": "UNVERIFIED",
            "throw_external_effect_status": "UNKNOWN",
            "hash_chain": "PASS",
        },
        "interpretation":
            "The minimal external adapter closes local return/throw receipt completeness for the tested Aegisora provider gateway without treating local return as authoritative external effect truth or provider throw as proof of NO_EFFECT.",
        "claim_ceiling":
            "No Aegisora source patch, no crash-atomic durability guarantee, no authoritative external readback, no recipient identity, and no payment/settlement binding.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verified, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verified, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
