from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from contractgraph_qa.occurrence_portability import (
    ACTION_MISMATCH,
    ALREADY_CONSUMED,
    CONCURRENT_CONSUMPTION_CONFLICT,
    CONSUMED,
    OCCURRENCE_EXPIRED,
    OCCURRENCE_REVOKED,
    REPLAY_SAME_RECEIPT,
    AuthorizationOccurrence,
    OccurrenceLedger,
    OccurrencePortabilityError,
    RoutedOccurrence,
    route_occurrence,
    verify_consumption_receipt,
    verify_routed_occurrence,
)


def _base_occurrence(**overrides: object) -> AuthorizationOccurrence:
    values: dict[str, object] = {
        "decision_ref": "decision-A",
        "cites_event_id": "evt-42",
        "action_digest": "sha256:action-A",
        "authority_revision": "auth-rev-7",
        "issued_at_epoch": 900,
        "expires_at_epoch": 1100,
        "revoked": False,
    }
    values.update(overrides)
    return AuthorizationOccurrence(**values)  # type: ignore[arg-type]


def _case(case_id: str, lane: str, expected: str, observed: str, *, note: str) -> dict[str, object]:
    if expected != observed:
        raise AssertionError(f"{case_id}: expected {expected}, got {observed}")
    return {
        "case_id": case_id,
        "lane": lane,
        "expected": expected,
        "observed": observed,
        "decision": "PASS",
        "note": note,
        "side_effects_executed": False,
    }


def build_matrix() -> dict[str, object]:
    cases: list[dict[str, object]] = []

    # P1-4: exact occurrence identity survives every canonical adapter hop.
    routed = route_occurrence(_base_occurrence())
    verify_routed_occurrence(routed)
    cases.append(
        _case(
            "P1-4-01",
            "occurrence-portability",
            "ROUTE_IDENTITY_PRESERVED",
            "ROUTE_IDENTITY_PRESERVED",
            note="decision_ref, cites_event_id, action_digest and authority_revision are identical across all five hops",
        )
    )

    try:
        route_occurrence(
            _base_occurrence(),
            route=("ProofPath", "CML", "RINSE", "LiminalDB", "ContractGraph-QA"),
        )
    except OccurrencePortabilityError:
        observed = "ROUTE_REJECTED"
    else:
        observed = "UNEXPECTED_ACCEPT"
    cases.append(
        _case(
            "P1-4-02",
            "occurrence-portability",
            "ROUTE_REJECTED",
            observed,
            note="adapter reordering fails closed",
        )
    )

    tampered_payload = json.loads(routed.hops[2].envelope_json)
    tampered_payload["cites_event_id"] = "evt-tampered"
    tampered_hop = replace(
        routed.hops[2],
        envelope_json=json.dumps(tampered_payload, sort_keys=True, separators=(",", ":")),
    )
    tampered_hops = list(routed.hops)
    tampered_hops[2] = tampered_hop
    tampered_route = RoutedOccurrence(routed.occurrence, tuple(tampered_hops), routed.route_fingerprint)
    try:
        verify_routed_occurrence(tampered_route)
    except OccurrencePortabilityError:
        observed = "TAMPER_REJECTED"
    else:
        observed = "UNEXPECTED_ACCEPT"
    cases.append(
        _case(
            "P1-4-03",
            "occurrence-portability",
            "TAMPER_REJECTED",
            observed,
            note="cites_event_id drift at LiminalDB hop is detected",
        )
    )

    # P1-5: replay, lifecycle and race matrix.
    expired = route_occurrence(_base_occurrence(expires_at_epoch=999))
    expired_result = OccurrenceLedger().consume(
        expired,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-expired",
        now_epoch=1000,
    )
    cases.append(
        _case(
            "P1-5-01",
            "race-replay",
            OCCURRENCE_EXPIRED,
            expired_result.status,
            note="stale authorization occurrence cannot be consumed",
        )
    )

    revoked = route_occurrence(_base_occurrence(revoked=True))
    revoked_result = OccurrenceLedger().consume(
        revoked,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-revoked",
        now_epoch=1000,
    )
    cases.append(
        _case(
            "P1-5-02",
            "race-replay",
            OCCURRENCE_REVOKED,
            revoked_result.status,
            note="revoked authorization occurrence cannot be consumed",
        )
    )

    race_ledger = OccurrenceLedger()
    race_routed = route_occurrence(_base_occurrence())
    race_ledger.register(race_routed)
    winner = race_ledger.consume(
        race_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-race-1",
        now_epoch=1000,
        expected_version=0,
    )
    loser = race_ledger.consume(
        race_routed,
        consumer_id="agent-2",
        action_digest="sha256:action-A",
        request_id="req-race-2",
        now_epoch=1000,
        expected_version=0,
    )
    observed = "ONE_WINNER_ONE_CONFLICT" if (
        winner.status == CONSUMED
        and loser.status == CONCURRENT_CONSUMPTION_CONFLICT
        and race_ledger.version("evt-42") == 1
    ) else "RACE_INVARIANT_BROKEN"
    cases.append(
        _case(
            "P1-5-03",
            "race-replay",
            "ONE_WINNER_ONE_CONFLICT",
            observed,
            note="CAS-style version gate permits exactly one concurrent consumer",
        )
    )

    retry_ledger = OccurrenceLedger()
    retry_routed = route_occurrence(_base_occurrence())
    first = retry_ledger.consume(
        retry_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-timeout",
        now_epoch=1000,
        expected_version=0,
    )
    replay = retry_ledger.consume(
        retry_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-timeout",
        now_epoch=1001,
        expected_version=0,
    )
    observed = "SAME_RECEIPT" if (
        first.status == CONSUMED
        and replay.status == REPLAY_SAME_RECEIPT
        and first.receipt is replay.receipt
        and retry_ledger.version("evt-42") == 1
    ) else "RETRY_MINTED_NEW_CONSUMPTION"
    cases.append(
        _case(
            "P1-5-04",
            "race-replay",
            "SAME_RECEIPT",
            observed,
            note="same request after a timeout replays the existing receipt instead of consuming twice",
        )
    )

    action_result = OccurrenceLedger().consume(
        route_occurrence(_base_occurrence()),
        consumer_id="agent-1",
        action_digest="sha256:changed-action",
        request_id="req-action-drift",
        now_epoch=1000,
    )
    cases.append(
        _case(
            "P1-5-05",
            "race-replay",
            ACTION_MISMATCH,
            action_result.status,
            note="permission cannot be rebound to a different action digest",
        )
    )

    reuse_ledger = OccurrenceLedger()
    reuse_routed = route_occurrence(_base_occurrence())
    reuse_ledger.consume(
        reuse_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-first",
        now_epoch=1000,
    )
    reuse = reuse_ledger.consume(
        reuse_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-new",
        now_epoch=1001,
    )
    cases.append(
        _case(
            "P1-5-06",
            "race-replay",
            ALREADY_CONSUMED,
            reuse.status,
            note="new request cannot reuse an already consumed authorization occurrence",
        )
    )

    # P1-6: immutable receipt binds exact permission, consumer, action and route.
    receipt_ledger = OccurrenceLedger()
    receipt_routed = route_occurrence(_base_occurrence())
    receipt_result = receipt_ledger.consume(
        receipt_routed,
        consumer_id="agent-1",
        action_digest="sha256:action-A",
        request_id="req-receipt",
        now_epoch=1000,
    )
    if receipt_result.receipt is None:
        raise AssertionError("P1-6-01: missing receipt")
    verify_consumption_receipt(receipt_result.receipt, routed=receipt_routed)
    cases.append(
        _case(
            "P1-6-01",
            "consumption-receipt",
            "RECEIPT_VERIFIED",
            "RECEIPT_VERIFIED",
            note="receipt binds decision_ref, cites_event_id, consumer_id, action_digest, authority_revision, route and request",
        )
    )

    tampered_receipt = replace(receipt_result.receipt, consumer_id="agent-attacker")
    try:
        verify_consumption_receipt(tampered_receipt, routed=receipt_routed)
    except OccurrencePortabilityError:
        observed = "RECEIPT_TAMPER_REJECTED"
    else:
        observed = "UNEXPECTED_ACCEPT"
    cases.append(
        _case(
            "P1-6-02",
            "consumption-receipt",
            "RECEIPT_TAMPER_REJECTED",
            observed,
            note="receipt mutation invalidates its digest and fails verification",
        )
    )

    passed = sum(1 for case in cases if case["decision"] == "PASS")
    result = {
        "schema": "cgqa.occurrence-portability-matrix.v0.1",
        "decision": "PASS" if passed == len(cases) else "FAIL",
        "canonical_route": ["ProofPath", "CML", "LiminalDB", "RINSE", "ContractGraph-QA"],
        "case_count": len(cases),
        "passed_cases": passed,
        "failed_cases": len(cases) - passed,
        "p1_4_portability_verified": True,
        "p1_5_race_replay_verified": True,
        "p1_6_consumption_receipt_verified": True,
        "side_effects_executed": False,
        "production_ledger_mutated": False,
        "cases": cases,
    }
    if result["decision"] != "PASS":
        raise AssertionError("occurrence portability matrix failed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the P1-4/P1-5/P1-6 occurrence portability matrix")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_matrix()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
