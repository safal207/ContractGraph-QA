from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

CANONICAL_ROUTE = (
    "ProofPath",
    "CML",
    "LiminalDB",
    "RINSE",
    "ContractGraph-QA",
)

CONSUMED = "CONSUMED"
REPLAY_SAME_RECEIPT = "REPLAY_SAME_RECEIPT"
ALREADY_CONSUMED = "ALREADY_CONSUMED"
CONCURRENT_CONSUMPTION_CONFLICT = "CONCURRENT_CONSUMPTION_CONFLICT"
REQUEST_ID_CONFLICT = "REQUEST_ID_CONFLICT"
OCCURRENCE_IDENTITY_CONFLICT = "OCCURRENCE_IDENTITY_CONFLICT"
ACTION_MISMATCH = "ACTION_MISMATCH"
OCCURRENCE_EXPIRED = "OCCURRENCE_EXPIRED"
OCCURRENCE_REVOKED = "OCCURRENCE_REVOKED"
OCCURRENCE_NOT_YET_VALID = "OCCURRENCE_NOT_YET_VALID"


class OccurrencePortabilityError(ValueError):
    """Raised when an occurrence loses identity while moving across adapters."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_object(value: object) -> str:
    return _sha256_text(_canonical_json(value))


@dataclass(frozen=True)
class AuthorizationOccurrence:
    decision_ref: str
    cites_event_id: str
    action_digest: str
    authority_revision: str
    issued_at_epoch: int
    expires_at_epoch: int
    revoked: bool = False

    def validate(self) -> None:
        for name in ("decision_ref", "cites_event_id", "action_digest", "authority_revision"):
            if not getattr(self, name):
                raise OccurrencePortabilityError(f"{name} must be non-empty")
        if self.issued_at_epoch < 0 or self.expires_at_epoch < 0:
            raise OccurrencePortabilityError("occurrence timestamps must be non-negative")
        if self.expires_at_epoch < self.issued_at_epoch:
            raise OccurrencePortabilityError("expires_at_epoch precedes issued_at_epoch")

    def envelope(self) -> dict[str, object]:
        self.validate()
        return {
            "schema": "cgqa.authorization-occurrence.v0.1",
            "decision_ref": self.decision_ref,
            "cites_event_id": self.cites_event_id,
            "action_digest": self.action_digest,
            "authority_revision": self.authority_revision,
            "issued_at_epoch": self.issued_at_epoch,
            "expires_at_epoch": self.expires_at_epoch,
            "revoked": self.revoked,
        }

    def fingerprint(self) -> str:
        return _sha256_object(self.envelope())


@dataclass(frozen=True)
class RoutedHop:
    adapter: str
    envelope_json: str
    envelope_fingerprint: str


@dataclass(frozen=True)
class RoutedOccurrence:
    occurrence: AuthorizationOccurrence
    hops: tuple[RoutedHop, ...]
    route_fingerprint: str


@dataclass(frozen=True)
class ConsumptionReceipt:
    schema: str
    decision_ref: str
    cites_event_id: str
    consumer_id: str
    action_digest: str
    authority_revision: str
    route_fingerprint: str
    request_id: str
    consumed_at_epoch: int
    result: str
    receipt_digest: str

    @classmethod
    def create(
        cls,
        *,
        occurrence: AuthorizationOccurrence,
        routed: RoutedOccurrence,
        consumer_id: str,
        request_id: str,
        consumed_at_epoch: int,
    ) -> "ConsumptionReceipt":
        if not consumer_id:
            raise OccurrencePortabilityError("consumer_id must be non-empty")
        if not request_id:
            raise OccurrencePortabilityError("request_id must be non-empty")
        payload = {
            "schema": "cgqa.consumption-receipt.v0.1",
            "decision_ref": occurrence.decision_ref,
            "cites_event_id": occurrence.cites_event_id,
            "consumer_id": consumer_id,
            "action_digest": occurrence.action_digest,
            "authority_revision": occurrence.authority_revision,
            "route_fingerprint": routed.route_fingerprint,
            "request_id": request_id,
            "consumed_at_epoch": consumed_at_epoch,
            "result": CONSUMED,
        }
        return cls(**payload, receipt_digest=_sha256_object(payload))

    def payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "decision_ref": self.decision_ref,
            "cites_event_id": self.cites_event_id,
            "consumer_id": self.consumer_id,
            "action_digest": self.action_digest,
            "authority_revision": self.authority_revision,
            "route_fingerprint": self.route_fingerprint,
            "request_id": self.request_id,
            "consumed_at_epoch": self.consumed_at_epoch,
            "result": self.result,
        }


@dataclass(frozen=True)
class ConsumeResult:
    status: str
    receipt: ConsumptionReceipt | None = None


def route_occurrence(
    occurrence: AuthorizationOccurrence,
    route: Iterable[str] = CANONICAL_ROUTE,
) -> RoutedOccurrence:
    occurrence.validate()
    route_tuple = tuple(route)
    if route_tuple != CANONICAL_ROUTE:
        raise OccurrencePortabilityError(
            f"route mismatch: expected {CANONICAL_ROUTE!r}, got {route_tuple!r}"
        )

    envelope_json = _canonical_json(occurrence.envelope())
    envelope_fingerprint = _sha256_text(envelope_json)
    hops = tuple(
        RoutedHop(
            adapter=adapter,
            envelope_json=envelope_json,
            envelope_fingerprint=envelope_fingerprint,
        )
        for adapter in route_tuple
    )
    route_fingerprint = _sha256_object(
        {
            "schema": "cgqa.occurrence-route.v0.1",
            "route": list(route_tuple),
            "occurrence_fingerprint": occurrence.fingerprint(),
            "hop_fingerprints": [hop.envelope_fingerprint for hop in hops],
        }
    )
    routed = RoutedOccurrence(
        occurrence=occurrence,
        hops=hops,
        route_fingerprint=route_fingerprint,
    )
    verify_routed_occurrence(routed)
    return routed


def verify_routed_occurrence(routed: RoutedOccurrence) -> bool:
    routed.occurrence.validate()
    adapters = tuple(hop.adapter for hop in routed.hops)
    if adapters != CANONICAL_ROUTE:
        raise OccurrencePortabilityError("adapter route order changed")

    expected_envelope = routed.occurrence.envelope()
    expected_json = _canonical_json(expected_envelope)
    expected_fingerprint = _sha256_text(expected_json)

    for hop in routed.hops:
        if hop.envelope_json != expected_json:
            raise OccurrencePortabilityError(f"occurrence envelope drift at {hop.adapter}")
        if hop.envelope_fingerprint != expected_fingerprint:
            raise OccurrencePortabilityError(f"occurrence fingerprint drift at {hop.adapter}")
        try:
            parsed = json.loads(hop.envelope_json)
        except json.JSONDecodeError as exc:
            raise OccurrencePortabilityError(f"invalid envelope JSON at {hop.adapter}") from exc
        if parsed != expected_envelope:
            raise OccurrencePortabilityError(f"occurrence semantic drift at {hop.adapter}")

    expected_route_fingerprint = _sha256_object(
        {
            "schema": "cgqa.occurrence-route.v0.1",
            "route": list(CANONICAL_ROUTE),
            "occurrence_fingerprint": routed.occurrence.fingerprint(),
            "hop_fingerprints": [expected_fingerprint] * len(CANONICAL_ROUTE),
        }
    )
    if routed.route_fingerprint != expected_route_fingerprint:
        raise OccurrencePortabilityError("route fingerprint mismatch")
    return True


def verify_consumption_receipt(
    receipt: ConsumptionReceipt,
    *,
    routed: RoutedOccurrence | None = None,
) -> bool:
    if receipt.schema != "cgqa.consumption-receipt.v0.1":
        raise OccurrencePortabilityError("unsupported consumption receipt schema")
    if receipt.result != CONSUMED:
        raise OccurrencePortabilityError("receipt result is not CONSUMED")
    if not receipt.consumer_id or not receipt.request_id:
        raise OccurrencePortabilityError("receipt consumer_id/request_id must be non-empty")
    if receipt.consumed_at_epoch < 0:
        raise OccurrencePortabilityError("receipt consumed_at_epoch must be non-negative")
    if receipt.receipt_digest != _sha256_object(receipt.payload()):
        raise OccurrencePortabilityError("consumption receipt digest mismatch")

    if routed is not None:
        verify_routed_occurrence(routed)
        occurrence = routed.occurrence
        expected = {
            "decision_ref": occurrence.decision_ref,
            "cites_event_id": occurrence.cites_event_id,
            "action_digest": occurrence.action_digest,
            "authority_revision": occurrence.authority_revision,
            "route_fingerprint": routed.route_fingerprint,
        }
        actual = {
            "decision_ref": receipt.decision_ref,
            "cites_event_id": receipt.cites_event_id,
            "action_digest": receipt.action_digest,
            "authority_revision": receipt.authority_revision,
            "route_fingerprint": receipt.route_fingerprint,
        }
        if actual != expected:
            raise OccurrencePortabilityError("receipt is not bound to the routed occurrence")
    return True


class OccurrenceLedger:
    """Deterministic in-memory reference ledger for one-time occurrence consumption.

    This is a conformance model only. It deliberately performs no production writes or
    external effects. `expected_version` models compare-and-set race protection.
    """

    def __init__(self) -> None:
        self._states: dict[str, dict[str, object]] = {}
        self._receipts_by_request: dict[str, ConsumptionReceipt] = {}

    def register(self, routed: RoutedOccurrence) -> int:
        verify_routed_occurrence(routed)
        occurrence = routed.occurrence
        existing = self._states.get(occurrence.cites_event_id)
        if existing is None:
            self._states[occurrence.cites_event_id] = {
                "fingerprint": occurrence.fingerprint(),
                "route_fingerprint": routed.route_fingerprint,
                "version": 0,
                "consumed": False,
            }
            return 0
        if (
            existing["fingerprint"] != occurrence.fingerprint()
            or existing["route_fingerprint"] != routed.route_fingerprint
        ):
            raise OccurrencePortabilityError("cites_event_id re-registered with different identity")
        return int(existing["version"])

    def version(self, cites_event_id: str) -> int:
        state = self._states.get(cites_event_id)
        if state is None:
            raise KeyError(cites_event_id)
        return int(state["version"])

    def consume(
        self,
        routed: RoutedOccurrence,
        *,
        consumer_id: str,
        action_digest: str,
        request_id: str,
        now_epoch: int,
        expected_version: int | None = None,
    ) -> ConsumeResult:
        verify_routed_occurrence(routed)
        occurrence = routed.occurrence
        if not consumer_id or not request_id:
            raise OccurrencePortabilityError("consumer_id/request_id must be non-empty")
        if now_epoch < 0:
            raise OccurrencePortabilityError("now_epoch must be non-negative")

        replay = self._receipts_by_request.get(request_id)
        if replay is not None:
            if (
                replay.cites_event_id == occurrence.cites_event_id
                and replay.consumer_id == consumer_id
                and replay.action_digest == action_digest
                and replay.route_fingerprint == routed.route_fingerprint
            ):
                verify_consumption_receipt(replay, routed=routed)
                return ConsumeResult(REPLAY_SAME_RECEIPT, replay)
            return ConsumeResult(REQUEST_ID_CONFLICT)

        self.register(routed)
        state = self._states[occurrence.cites_event_id]

        if state["fingerprint"] != occurrence.fingerprint():
            return ConsumeResult(OCCURRENCE_IDENTITY_CONFLICT)
        if expected_version is not None and expected_version != int(state["version"]):
            return ConsumeResult(CONCURRENT_CONSUMPTION_CONFLICT)
        if occurrence.revoked:
            return ConsumeResult(OCCURRENCE_REVOKED)
        if now_epoch < occurrence.issued_at_epoch:
            return ConsumeResult(OCCURRENCE_NOT_YET_VALID)
        if now_epoch > occurrence.expires_at_epoch:
            return ConsumeResult(OCCURRENCE_EXPIRED)
        if action_digest != occurrence.action_digest:
            return ConsumeResult(ACTION_MISMATCH)
        if bool(state["consumed"]):
            return ConsumeResult(ALREADY_CONSUMED)

        receipt = ConsumptionReceipt.create(
            occurrence=occurrence,
            routed=routed,
            consumer_id=consumer_id,
            request_id=request_id,
            consumed_at_epoch=now_epoch,
        )
        verify_consumption_receipt(receipt, routed=routed)
        state["consumed"] = True
        state["version"] = int(state["version"]) + 1
        self._receipts_by_request[request_id] = receipt
        return ConsumeResult(CONSUMED, receipt)
