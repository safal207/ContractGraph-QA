#!/usr/bin/env python3
"""Map Gonka CGQA reconciliation evidence into native LiminalDB transition inputs.

This bridge deliberately stores verification causality, not a claim about Gonka's
own authorization model. The LiminalDB Authorization record represents the
scope/authority of the local CGQA verification run. Execution observations are
kept one-per-internal-request so retries never collapse into one record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BUNDLE_SCHEMA = "cgqa-gonka-liminaldb-transition-bundle-v0.1"
SOURCE_SCHEMA = "gonka-safe-timeout-retry-v0.1"
SUBJECT_ID = "gonka:local-verification"


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
        raise ValueError(f"logical_operation_id has no embedded Unix-nanosecond timestamp: {logical_operation_id}")
    return int(match.group(1)) // 1_000_000


def dimensions(*, execution: str, causal: str, posture: str) -> dict[str, str]:
    return {
        "authority": "VALID",
        "execution": execution,
        "response_integrity": "NOT_EVALUATED",
        "causal_validity": causal,
        "continuity_posture": posture,
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


def empty_links() -> dict[str, Any]:
    return {
        "authorization_ref": None,
        "observation_refs": [],
        "response_integrity_ref": None,
        "causal_audit_ref": None,
        "previous_continuity_ref": None,
    }


def events_for_case(case: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    transition_id = str(case.get("logical_operation_id", "")).strip()
    if not transition_id:
        raise ValueError(f"{case.get('case_id')}: logical_operation_id missing")

    case_id = str(case.get("case_id", "")).strip()
    verdict = str(case.get("verdict", "")).upper()
    internal_ids = list(case.get("internal_request_ids") or [])
    winner_nonces = list(case.get("winner_nonces") or [])
    if len(internal_ids) != len(winner_nonces) or not internal_ids:
        raise ValueError(
            f"{case_id}: internal_request_ids/winner_nonces mismatch: "
            f"{len(internal_ids)} vs {len(winner_nonces)}"
        )

    base_ms = captured_base_ms(transition_id)
    events: list[dict[str, Any]] = []

    authorization_payload = {
        "case_id": case_id,
        "logical_operation_id": transition_id,
        "scope": "local Gonka devshard/testenv verification only",
        "upstream_revision": bundle.get("upstream_revision"),
        "environment": bundle.get("environment"),
        "client_correlation_ids": case.get("client_correlation_ids"),
        "safety_boundary": {
            "real_funds": False,
            "mainnet_fault_injection": False,
            "purpose": "causal verification",
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
    for index, (internal_id, nonce) in enumerate(zip(internal_ids, winner_nonces), start=1):
        executed = bool(case.get("all_accounting_resolved")) and int(nonce) != 0
        observation_payload = {
            "case_id": case_id,
            "logical_operation_id": transition_id,
            "internal_request_id": internal_id,
            "winner_nonce": nonce,
            "timeout_observed": case.get("timeout_observed"),
            "first_completion_observed": case.get("first_completion_observed"),
            "retry_http_status": case.get("retry_http_status"),
            "canonical_ids_distinct": case.get("canonical_ids_distinct"),
            "winner_nonces_distinct": case.get("winner_nonces_distinct"),
        }
        links = empty_links()
        links["authorization_ref"] = authorization_ref
        observation = make_event(
            transition_id=transition_id,
            kind="observation",
            ordinal=index,
            payload=observation_payload,
            links=links,
            captured_at_ms=base_ms + index,
            dims=dimensions(
                execution="OBSERVED_EXECUTED" if executed else "NOT_OBSERVED",
                causal="NOT_EVALUATED",
                posture="NOT_EVALUATED",
            ),
            side_effect_committed=executed,
        )
        events.append(observation)
        observation_refs.append(observation["record_ref"])

    all_executed = all(int(nonce) != 0 for nonce in winner_nonces) and bool(case.get("all_accounting_resolved"))
    response_payload = {
        "case_id": case_id,
        "logical_operation_id": transition_id,
        "status": "NOT_EVALUATED",
        "reason": (
            "G-002A/B verifies execution/accounting causality and addressability; "
            "it does not independently verify semantic fidelity of model response content"
        ),
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    response = make_event(
        transition_id=transition_id,
        kind="response_integrity",
        ordinal=len(events),
        payload=response_payload,
        links=links,
        captured_at_ms=base_ms + len(events),
        dims=dimensions(
            execution="OBSERVED_EXECUTED" if all_executed else "NOT_OBSERVED",
            causal="NOT_EVALUATED",
            posture="NOT_EVALUATED",
        ),
    )
    events.append(response)

    causal_state = "VALID" if verdict == "PASS" else "INVALID"
    posture = "REPORT_ONLY" if verdict == "PASS" else "REVALIDATE"
    causal_payload = {
        "case_id": case_id,
        "logical_operation_id": transition_id,
        "cgqa_verdict": verdict,
        "unexplained_effects": case.get("unexplained_effects") or [],
        "notes": case.get("notes"),
        "causal_claim": (
            "all observed post-timeout executions remain independently addressable "
            "under one logical operation"
        ),
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    links["response_integrity_ref"] = response["record_ref"]
    causal = make_event(
        transition_id=transition_id,
        kind="causal_audit",
        ordinal=len(events),
        payload=causal_payload,
        links=links,
        captured_at_ms=base_ms + len(events),
        dims=dimensions(
            execution="OBSERVED_EXECUTED" if all_executed else "NOT_OBSERVED",
            causal=causal_state,
            posture=posture,
        ),
    )
    events.append(causal)

    continuity_payload = {
        "case_id": case_id,
        "logical_operation_id": transition_id,
        "posture": posture,
        "side_effect_committed": all_executed,
        "retry_idempotency_assumed": False,
        "next_boundary": "money reconciliation / settlement",
    }
    links = empty_links()
    links["authorization_ref"] = authorization_ref
    links["observation_refs"] = observation_refs
    links["response_integrity_ref"] = response["record_ref"]
    links["causal_audit_ref"] = causal["record_ref"]
    continuity = make_event(
        transition_id=transition_id,
        kind="continuity_snapshot",
        ordinal=len(events),
        payload=continuity_payload,
        links=links,
        captured_at_ms=base_ms + len(events),
        dims=dimensions(
            execution="OBSERVED_EXECUTED" if all_executed else "NOT_OBSERVED",
            causal=causal_state,
            posture=posture,
        ),
        side_effect_committed=all_executed,
    )
    events.append(continuity)
    return events


def build(source_path: Path, liminaldb_revision: str) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source = json.loads(source_bytes)
    if source.get("schema_version") != SOURCE_SCHEMA:
        raise ValueError(f"unexpected source schema: {source.get('schema_version')}")
    cases = source.get("cases") or []
    if not cases:
        raise ValueError("source evidence has no cases")

    events: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda item: str(item.get("case_id", ""))):
        events.extend(events_for_case(case, source))

    return {
        "schema": BUNDLE_SCHEMA,
        "source_evidence_digest": sha256_ref_bytes(source_bytes),
        "liminaldb_revision": liminaldb_revision,
        "source_schema": SOURCE_SCHEMA,
        "transition_ids": [str(case["logical_operation_id"]) for case in cases],
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
        f"LiminalDB transition bundle: transitions={len(bundle['transition_ids'])} "
        f"events={len(bundle['events'])} source={bundle['source_evidence_digest']}"
    )


if __name__ == "__main__":
    main()
