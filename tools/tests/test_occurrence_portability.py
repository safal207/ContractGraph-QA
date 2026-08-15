from __future__ import annotations

from dataclasses import replace
import json
import unittest

from contractgraph_qa.occurrence_portability import (
    ACTION_MISMATCH,
    ALREADY_CONSUMED,
    CANONICAL_ROUTE,
    CONCURRENT_CONSUMPTION_CONFLICT,
    CONSUMED,
    OCCURRENCE_EXPIRED,
    OCCURRENCE_NOT_YET_VALID,
    OCCURRENCE_REVOKED,
    REPLAY_SAME_RECEIPT,
    REQUEST_ID_CONFLICT,
    AuthorizationOccurrence,
    OccurrenceLedger,
    OccurrencePortabilityError,
    RoutedOccurrence,
    route_occurrence,
    verify_consumption_receipt,
    verify_routed_occurrence,
)


class OccurrencePortabilityTest(unittest.TestCase):
    def occurrence(self, **overrides: object) -> AuthorizationOccurrence:
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

    def test_p1_4_exact_occurrence_survives_every_adapter_hop(self) -> None:
        routed = route_occurrence(self.occurrence())
        self.assertEqual(tuple(h.adapter for h in routed.hops), CANONICAL_ROUTE)
        self.assertEqual(len({h.envelope_fingerprint for h in routed.hops}), 1)
        self.assertTrue(verify_routed_occurrence(routed))
        for hop in routed.hops:
            envelope = json.loads(hop.envelope_json)
            self.assertEqual(envelope["decision_ref"], "decision-A")
            self.assertEqual(envelope["cites_event_id"], "evt-42")
            self.assertEqual(envelope["action_digest"], "sha256:action-A")
            self.assertEqual(envelope["authority_revision"], "auth-rev-7")

    def test_p1_4_reordered_adapter_route_fails_closed(self) -> None:
        with self.assertRaisesRegex(OccurrencePortabilityError, "route mismatch"):
            route_occurrence(
                self.occurrence(),
                route=("ProofPath", "CML", "RINSE", "LiminalDB", "ContractGraph-QA"),
            )

    def test_p1_4_adapter_event_id_tamper_is_detected(self) -> None:
        routed = route_occurrence(self.occurrence())
        tampered_envelope = json.loads(routed.hops[2].envelope_json)
        tampered_envelope["cites_event_id"] = "evt-attacker"
        tampered_hop = replace(
            routed.hops[2],
            envelope_json=json.dumps(tampered_envelope, sort_keys=True, separators=(",", ":")),
        )
        hops = list(routed.hops)
        hops[2] = tampered_hop
        tampered = RoutedOccurrence(routed.occurrence, tuple(hops), routed.route_fingerprint)
        with self.assertRaisesRegex(OccurrencePortabilityError, "envelope drift"):
            verify_routed_occurrence(tampered)

    def test_p1_5_expired_occurrence_cannot_be_consumed(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence(expires_at_epoch=999))
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-expired",
            now_epoch=1000,
        )
        self.assertEqual(result.status, OCCURRENCE_EXPIRED)
        self.assertIsNone(result.receipt)

    def test_p1_5_revoked_occurrence_cannot_be_consumed(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence(revoked=True))
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-revoked",
            now_epoch=1000,
        )
        self.assertEqual(result.status, OCCURRENCE_REVOKED)

    def test_p1_5_not_yet_valid_occurrence_cannot_be_consumed(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence(issued_at_epoch=1001, expires_at_epoch=1100))
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-early",
            now_epoch=1000,
        )
        self.assertEqual(result.status, OCCURRENCE_NOT_YET_VALID)

    def test_p1_5_compare_and_set_race_allows_one_winner(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        self.assertEqual(ledger.register(routed), 0)

        winner = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-race-1",
            now_epoch=1000,
            expected_version=0,
        )
        loser = ledger.consume(
            routed,
            consumer_id="agent-2",
            action_digest="sha256:action-A",
            request_id="req-race-2",
            now_epoch=1000,
            expected_version=0,
        )

        self.assertEqual(winner.status, CONSUMED)
        self.assertEqual(loser.status, CONCURRENT_CONSUMPTION_CONFLICT)
        self.assertEqual(ledger.version("evt-42"), 1)

    def test_p1_5_timeout_retry_returns_same_receipt_not_second_consumption(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        first = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-timeout",
            now_epoch=1000,
            expected_version=0,
        )
        replay = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-timeout",
            now_epoch=1001,
            expected_version=0,
        )
        self.assertEqual(first.status, CONSUMED)
        self.assertEqual(replay.status, REPLAY_SAME_RECEIPT)
        self.assertIs(first.receipt, replay.receipt)
        self.assertEqual(first.receipt, replay.receipt)
        self.assertEqual(ledger.version("evt-42"), 1)

    def test_p1_5_changed_action_digest_is_rejected(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:different-action",
            request_id="req-action-drift",
            now_epoch=1000,
        )
        self.assertEqual(result.status, ACTION_MISMATCH)

    def test_p1_5_consumed_occurrence_cannot_be_reused_by_new_request(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        first = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-first",
            now_epoch=1000,
        )
        second = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-second",
            now_epoch=1001,
        )
        self.assertEqual(first.status, CONSUMED)
        self.assertEqual(second.status, ALREADY_CONSUMED)

    def test_p1_5_request_id_cannot_be_rebound_to_other_consumer(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        first = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-bound",
            now_epoch=1000,
        )
        rebound = ledger.consume(
            routed,
            consumer_id="agent-2",
            action_digest="sha256:action-A",
            request_id="req-bound",
            now_epoch=1001,
        )
        self.assertEqual(first.status, CONSUMED)
        self.assertEqual(rebound.status, REQUEST_ID_CONFLICT)

    def test_p1_6_consumption_receipt_binds_exact_occurrence_and_route(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-receipt",
            now_epoch=1000,
        )
        self.assertEqual(result.status, CONSUMED)
        self.assertIsNotNone(result.receipt)
        receipt = result.receipt
        assert receipt is not None
        self.assertEqual(receipt.decision_ref, "decision-A")
        self.assertEqual(receipt.cites_event_id, "evt-42")
        self.assertEqual(receipt.action_digest, "sha256:action-A")
        self.assertEqual(receipt.authority_revision, "auth-rev-7")
        self.assertEqual(receipt.route_fingerprint, routed.route_fingerprint)
        self.assertTrue(verify_consumption_receipt(receipt, routed=routed))

    def test_p1_6_tampered_receipt_digest_fails_verification(self) -> None:
        ledger = OccurrenceLedger()
        routed = route_occurrence(self.occurrence())
        result = ledger.consume(
            routed,
            consumer_id="agent-1",
            action_digest="sha256:action-A",
            request_id="req-tamper",
            now_epoch=1000,
        )
        assert result.receipt is not None
        tampered = replace(result.receipt, consumer_id="agent-attacker")
        with self.assertRaisesRegex(OccurrencePortabilityError, "digest mismatch"):
            verify_consumption_receipt(tampered, routed=routed)


if __name__ == "__main__":
    unittest.main()
