#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "contractgraph.execution-receipt-boundary.v0.1"
SYSTEM_CASE = "EXECUTION-RECEIPT-001"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


@dataclass(frozen=True)
class Binding:
    action_id: str
    target: str
    payload_digest: str
    trace_id: str
    decision_id: str
    execution_id: str
    evidence_id: str


class ReceiptLedger:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def append(
        self,
        *,
        binding: Binding,
        phase: str,
        local_outcome: str,
        external_effect_status: str,
        error_digest: str | None = None,
    ) -> dict[str, Any]:
        if phase not in {"PENDING", "TERMINAL"}:
            fail("unsupported receipt phase")
        if local_outcome not in {"NOT_OBSERVED", "RETURNED_SUCCESS", "THREW"}:
            fail("unsupported local outcome")
        if external_effect_status not in {"UNKNOWN", "UNVERIFIED"}:
            fail("unsupported external effect status")

        prior = [r for r in self.records if r["action_id"] == binding.action_id]
        if phase == "PENDING":
            if prior:
                fail("duplicate PENDING receipt for action")
            if local_outcome != "NOT_OBSERVED":
                fail("PENDING must not claim a terminal local outcome")
            if external_effect_status != "UNKNOWN":
                fail("PENDING external effect status must stay UNKNOWN")
        else:
            if len(prior) != 1 or prior[0]["phase"] != "PENDING":
                fail("TERMINAL requires exactly one prior PENDING receipt")
            pending = prior[0]
            for key, expected in {
                "target": binding.target,
                "payload_digest": binding.payload_digest,
                "trace_id": binding.trace_id,
                "decision_id": binding.decision_id,
                "execution_id": binding.execution_id,
                "evidence_id": binding.evidence_id,
            }.items():
                if pending[key] != expected:
                    fail(f"terminal binding mismatch: {key}")
            if local_outcome == "NOT_OBSERVED":
                fail("TERMINAL cannot remain NOT_OBSERVED")
            if local_outcome == "THREW" and external_effect_status != "UNKNOWN":
                fail("THREW is not proof of external absence; status must remain UNKNOWN")
            if local_outcome == "RETURNED_SUCCESS" and external_effect_status != "UNVERIFIED":
                fail("local success is not authoritative external readback")

        body = {
            "schema": SCHEMA,
            "action_id": binding.action_id,
            "target": binding.target,
            "payload_digest": binding.payload_digest,
            "trace_id": binding.trace_id,
            "decision_id": binding.decision_id,
            "execution_id": binding.execution_id,
            "evidence_id": binding.evidence_id,
            "phase": phase,
            "local_outcome": local_outcome,
            "external_effect_status": external_effect_status,
            "error_digest": error_digest,
            "previous_receipt_sha256": self.records[-1]["receipt_sha256"] if self.records else None,
        }
        body["receipt_sha256"] = sha256_json(body)
        self.records.append(body)
        return body

    def action_records(self, action_id: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r["action_id"] == action_id]

    def classify(self, action_id: str) -> dict[str, str]:
        records = self.action_records(action_id)
        if not records:
            return {
                "execution_state": "NOT_AUTHORIZED_FOR_DISPATCH",
                "external_effect_status": "NOT_EVALUATED",
                "continuity": "NO_EXECUTION_RECEIPT",
            }
        if len(records) == 1 and records[0]["phase"] == "PENDING":
            return {
                "execution_state": "UNKNOWN",
                "external_effect_status": "UNKNOWN",
                "continuity": "REVALIDATE",
            }
        if len(records) == 2 and records[-1]["phase"] == "TERMINAL":
            terminal = records[-1]
            if terminal["local_outcome"] == "RETURNED_SUCCESS":
                return {
                    "execution_state": "LOCAL_RETURNED_SUCCESS",
                    "external_effect_status": "UNVERIFIED",
                    "continuity": "EXTERNAL_READBACK_REQUIRED",
                }
            if terminal["local_outcome"] == "THREW":
                return {
                    "execution_state": "LOCAL_THREW",
                    "external_effect_status": "UNKNOWN",
                    "continuity": "REVALIDATE",
                }
        fail("invalid receipt history")


def binding(action_id: str, target: str = "provider:openai") -> Binding:
    return Binding(
        action_id=action_id,
        target=target,
        payload_digest=sha256_json({"prompt": "bounded", "model": "test"}),
        trace_id="trace-" + action_id,
        decision_id="decision-" + action_id,
        execution_id="execution-" + action_id,
        evidence_id="evidence-" + action_id,
    )


def run_contract() -> dict[str, Any]:
    ledger = ReceiptLedger()

    blocked = ledger.classify("blocked")
    if blocked["execution_state"] != "NOT_AUTHORIZED_FOR_DISPATCH":
        fail("blocked path fabricated execution evidence")

    usage = binding("success-with-usage")
    ledger.append(
        binding=usage,
        phase="PENDING",
        local_outcome="NOT_OBSERVED",
        external_effect_status="UNKNOWN",
    )
    ledger.append(
        binding=usage,
        phase="TERMINAL",
        local_outcome="RETURNED_SUCCESS",
        external_effect_status="UNVERIFIED",
    )

    no_usage = binding("success-without-usage", "provider:gemini")
    ledger.append(
        binding=no_usage,
        phase="PENDING",
        local_outcome="NOT_OBSERVED",
        external_effect_status="UNKNOWN",
    )
    ledger.append(
        binding=no_usage,
        phase="TERMINAL",
        local_outcome="RETURNED_SUCCESS",
        external_effect_status="UNVERIFIED",
    )

    throwing = binding("provider-throws", "provider:groq")
    ledger.append(
        binding=throwing,
        phase="PENDING",
        local_outcome="NOT_OBSERVED",
        external_effect_status="UNKNOWN",
    )
    ledger.append(
        binding=throwing,
        phase="TERMINAL",
        local_outcome="THREW",
        external_effect_status="UNKNOWN",
        error_digest=sha256_json({"error": "synthetic-provider-failure"}),
    )

    lost_terminal = binding("lost-terminal", "provider:anthropic")
    ledger.append(
        binding=lost_terminal,
        phase="PENDING",
        local_outcome="NOT_OBSERVED",
        external_effect_status="UNKNOWN",
    )

    expected = {
        "success-with-usage": {
            "execution_state": "LOCAL_RETURNED_SUCCESS",
            "external_effect_status": "UNVERIFIED",
            "continuity": "EXTERNAL_READBACK_REQUIRED",
        },
        "success-without-usage": {
            "execution_state": "LOCAL_RETURNED_SUCCESS",
            "external_effect_status": "UNVERIFIED",
            "continuity": "EXTERNAL_READBACK_REQUIRED",
        },
        "provider-throws": {
            "execution_state": "LOCAL_THREW",
            "external_effect_status": "UNKNOWN",
            "continuity": "REVALIDATE",
        },
        "lost-terminal": {
            "execution_state": "UNKNOWN",
            "external_effect_status": "UNKNOWN",
            "continuity": "REVALIDATE",
        },
    }
    observed = {key: ledger.classify(key) for key in expected}
    if observed != expected:
        fail("contract classification drift")

    mutants: list[dict[str, Any]] = []

    def detect(name: str, fn) -> None:
        try:
            fn()
        except ValueError as exc:
            mutants.append({"name": name, "detected": True, "reason": str(exc)})
            return
        mutants.append({"name": name, "detected": False})
        fail(f"unsafe mutant survived: {name}")

    def mutant_throw_means_no_effect() -> None:
        m = ReceiptLedger()
        b = binding("m-throw-no-effect")
        m.append(
            binding=b,
            phase="PENDING",
            local_outcome="NOT_OBSERVED",
            external_effect_status="UNKNOWN",
        )
        m.append(
            binding=b,
            phase="TERMINAL",
            local_outcome="THREW",
            external_effect_status="UNVERIFIED",
        )

    def mutant_terminal_without_pending() -> None:
        m = ReceiptLedger()
        m.append(
            binding=binding("m-no-pending"),
            phase="TERMINAL",
            local_outcome="RETURNED_SUCCESS",
            external_effect_status="UNVERIFIED",
        )

    def mutant_target_rebind() -> None:
        m = ReceiptLedger()
        original = binding("m-target", "provider:openai")
        m.append(
            binding=original,
            phase="PENDING",
            local_outcome="NOT_OBSERVED",
            external_effect_status="UNKNOWN",
        )
        changed = Binding(
            action_id=original.action_id,
            target="provider:anthropic",
            payload_digest=original.payload_digest,
            trace_id=original.trace_id,
            decision_id=original.decision_id,
            execution_id=original.execution_id,
            evidence_id=original.evidence_id,
        )
        m.append(
            binding=changed,
            phase="TERMINAL",
            local_outcome="RETURNED_SUCCESS",
            external_effect_status="UNVERIFIED",
        )

    detect("throw_must_not_imply_external_absence", mutant_throw_means_no_effect)
    detect("terminal_requires_pending", mutant_terminal_without_pending)
    detect("terminal_target_must_match_pending", mutant_target_rebind)

    return {
        "schema": SCHEMA,
        "system_case": SYSTEM_CASE,
        "status": "PASS",
        "invariant":
            "Authorization creates PENDING evidence, not proof of execution. Every observed return/throw appends a terminal receipt independent of usage. Missing terminal remains UNKNOWN/REVALIDATE; provider throw never proves NO_EFFECT.",
        "cases": {
            "blocked": blocked,
            **observed,
        },
        "receipt_count": len(ledger.records),
        "mutants": mutants,
        "claim_ceiling": [
            "Framework-neutral executable contract; not a runtime integration.",
            "RETURNED_SUCCESS is local provider-call evidence, not authoritative external-effect proof.",
            "THREW does not establish that no external effect occurred.",
            "PENDING without terminal remains UNKNOWN and requires revalidation.",
            "No distributed durability or crash-atomicity claim.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    report = run_contract()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
