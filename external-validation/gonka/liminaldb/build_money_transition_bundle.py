#!/usr/bin/env python3
"""Map G-004 causal money reconciliation into native LiminalDB transition inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BUNDLE_SCHEMA = "cgqa-gonka-liminaldb-transition-bundle-v0.1"
SOURCE_SCHEMA = "gonka-causal-money-reconciliation-v0.1"
SUBJECT_ID = "gonka:local-financial-verification"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_ref_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    return sha256_ref_bytes(canonical_bytes(value))


def record_ref(transition_id: str, kind: str, ordinal: int, payload_digest: str) -> str:
    return digest(
        {
            "transition_id": transition_id,
            "kind": kind,
            "ordinal": ordinal,
            "payload_digest": payload_digest,
        }
    )


def captured_base_ms(logical_operation_id: str) -> int:
    match = re.search(r"-(\d{16,})$", logical_operation_id)
    if not match:
        raise ValueError(
            f"logical_operation_id has no embedded Unix-nanosecond timestamp: {logical_operation_id}"
        )
    return int(match.group(1)) // 1_000_000


def dimensions(*, execution: str, causal: str, posture: str) -> dict[str, str]:
    return {
        "authority": "VALID",
        "execution": execution,
        "response_integrity": "NOT_EVALUATED",
        "causal_validity": causal,
        "continuity_posture": posture,
    }


def empty_links() -> dict[str, Any]:
    return {
        "authorization_ref": None,
        "observation_refs": [],
        "response_integrity_ref": None,
        "causal_audit_ref": None,
        "previous_continuity_ref": None,
    }


def make_event(
    *,
    transition_id: str,
    kind: str,
    ordinal: int,
    payload: dict[str, Any],
    links: dict[str, Any],
    captured_at_ms: int,
    dims: dict[str, str] | None = None,
    side_effect_committed: bool | None = None,
) -> dict[str, Any]:
    payload_digest = digest(payload)
    return {
        "transition_id": transition_id,
        "subject_id": SUBJECT_ID,
        "kind": kind,
        "record_ref": record_ref(transition_id, kind, ordinal, payload_digest),
        "payload_digest": payload_digest,
        "links": links,
        "dimensions": dims,
        "side_effect_committed": side_effect_committed,
        "captured_at_ms": captured_at_ms,
    }


def build(source_path: Path, liminaldb_revision: str) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError(f"unexpected source schema: {source.get('schema_version')}")
    if source.get("case_id") != "G-004":
        raise ValueError(f"unexpected case: {source.get('case_id')}")

    transition_id = str(source.get("logical_operation_id", "")).strip()
    if not transition_id:
        raise ValueError("logical_operation_id missing")
    requests = source.get("requests") or []
    if len(requests) != 2:
        raise ValueError(f"expected exactly two internal request lineages, got {len(requests)}")

    verdict = str(source.get("verdict", "")).upper()
    causal_state = "VALID" if verdict == "PASS" else "INVALID"
    posture = "REPORT_ONLY" if verdict == "PASS" else "REVALIDATE"
    base_ms = captured_base_ms(transition_id)
    events: list[dict[str, Any]] = []

    authorization_payload = {
        "case_id": "G-004",
        "logical_operation_id": transition_id,
        "scope": "local Gonka devshard/testenv financial verification only",
        "upstream_revision": source.get("upstream_revision"),
        "environment": source.get("environment"),
        "client_correlation_id": source.get("client_correlation_id"),
        "safety_boundary": {
            "real_funds": False,
            "mainnet_fault_injection": False,
            "challenge_invalidation_semantics": "excluded_from_v0.1",
        },
    }
    authorization = make_event(
        transition_id=transition_id,
        kind="authorization",
        ordinal=0,
        payload=authorization_payload,
        links=empty_links(),
        captured_at_ms=base_ms,
    )
    events.append(authorization)
    authorization_ref = authorization["record_ref"]

    observation_refs: list[str] = []
    for index, request in enumerate(requests, start=1):
        payload = {
            "case_id": "G-004",
            "logical_operation_id": transition_id,
            "internal_request_id": request.get("internal_request_id"),
            "winner_nonce": request.get("winner_nonce"),
            "attempt_nonces": request.get("attempt_nonces"),
            "attempt_actual_cost": request.get("attempt_actual_cost"),
            "reported_all_attempts_actual_cost": request.get("reported_all_attempts_actual_cost"),
            "arithmetic_reconciles": request.get("arithmetic_reconciles"),
        }
        links = empty_links()
        links["authorization_ref"] = authorization_ref
        observation = make_event(
            transition_id=transition_id,
            kind="observation",
            ordinal=index,
            payload=payload,
            links=links,
            captured_at_ms=base_ms + index,
            dims=dimensions(
                execution="OBSERVED_EXECUTED",
                causal="NOT_EVALUATED",
                posture="NOT_EVALUATED",
            ),
            side_effect_committed=True,
        )
        events.append(observation)
        observation_refs.append(observation["record_ref"])

    financial_payload = {
        "case_id": "G-004",
        "logical_operation_id": transition_id,
        "attempt_nonces": source.get("attempt_nonces"),
        "terminal_inference_statuses": source.get("terminal_inference_statuses"),
        "accounting_attempt_cost": source.get("accounting_attempt_cost"),
        "accounting_reported_cost": source.get("accounting_reported_cost"),
        "inference_actual_cost": source.get("inference_actual_cost"),
        "host_cost_before": source.get("host_cost_before"),
        "host_cost_after": source.get("host_cost_after"),
        "host_cost_delta": source.get("host_cost_delta"),
        "balance_before": source.get("balance_before"),
        "balance_after": source.get("balance_after"),
        "balance_debit": source.get("balance_debit"),
        "four_way_reconciles": source.get("four_way_reconciles"),
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    financial_observation = make_event(
        transition_id=transition_id,
        kind="observation",
        ordinal=3,
        payload=financial_payload,
        links=links,
        captured_at_ms=base_ms + 3,
        dims=dimensions(
            execution="OBSERVED_EXECUTED",
            causal="NOT_EVALUATED",
            posture="NOT_EVALUATED",
        ),
        side_effect_committed=True,
    )
    events.append(financial_observation)
    observation_refs.append(financial_observation["record_ref"])

    response_payload = {
        "case_id": "G-004",
        "logical_operation_id": transition_id,
        "status": "NOT_EVALUATED",
        "reason": "G-004 reconciles financial execution effects; model response semantic fidelity is outside this case",
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    response = make_event(
        transition_id=transition_id,
        kind="response_integrity",
        ordinal=4,
        payload=response_payload,
        links=links,
        captured_at_ms=base_ms + 4,
        dims=dimensions(
            execution="OBSERVED_EXECUTED",
            causal="NOT_EVALUATED",
            posture="NOT_EVALUATED",
        ),
    )
    events.append(response)

    causal_payload = {
        "case_id": "G-004",
        "logical_operation_id": transition_id,
        "cgqa_verdict": verdict,
        "four_way_reconciles": source.get("four_way_reconciles"),
        "unexplained_financial_effects": source.get("unexplained_financial_effects") or [],
        "causal_claim": (
            "request accounting, per-inference actual cost, aggregate host cost, and escrow balance debit "
            "describe the same isolated timeout/retry financial effect"
        ),
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    links["response_integrity_ref"] = response["record_ref"]
    causal = make_event(
        transition_id=transition_id,
        kind="causal_audit",
        ordinal=5,
        payload=causal_payload,
        links=links,
        captured_at_ms=base_ms + 5,
        dims=dimensions(
            execution="OBSERVED_EXECUTED",
            causal=causal_state,
            posture=posture,
        ),
    )
    events.append(causal)

    continuity_payload = {
        "case_id": "G-004",
        "logical_operation_id": transition_id,
        "posture": posture,
        "side_effect_committed": True,
        "retry_idempotency_assumed": False,
        "next_boundary": "settlement / epoch / recovery reconciliation",
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    links["response_integrity_ref"] = response["record_ref"]
    links["causal_audit_ref"] = causal["record_ref"]
    continuity = make_event(
        transition_id=transition_id,
        kind="continuity_snapshot",
        ordinal=6,
        payload=continuity_payload,
        links=links,
        captured_at_ms=base_ms + 6,
        dims=dimensions(
            execution="OBSERVED_EXECUTED",
            causal=causal_state,
            posture=posture,
        ),
        side_effect_committed=True,
    )
    events.append(continuity)

    return {
        "schema": BUNDLE_SCHEMA,
        "source_evidence_digest": sha256_ref_bytes(source_bytes),
        "liminaldb_revision": liminaldb_revision,
        "source_schema": SOURCE_SCHEMA,
        "transition_ids": [transition_id],
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--liminaldb-revision", required=True)
    args = parser.parse_args()

    bundle = build(args.input, args.liminaldb_revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"G-004 LiminalDB bundle: transitions={len(bundle['transition_ids'])} "
        f"events={len(bundle['events'])} source={bundle['source_evidence_digest']}"
    )


if __name__ == "__main__":
    main()
