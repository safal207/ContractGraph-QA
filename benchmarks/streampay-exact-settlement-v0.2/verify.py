#!/usr/bin/env python3
"""Independent second-audit model for StreamPay issue #153 / PR #161.

The economic oracle replays attempted actions into its own lifecycle and forms
the union of eligible active intervals.  It never reads the candidate cursor,
pause marker, payout arithmetic, or lifecycle phase.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Iterable

import contractgraph_qa


TARGET_REPOSITORY = "Streampay-Org/StreamPay-Contracts"
TARGET_SHA = "2baa37b533c07790d6aa38ab0a5c0170fcbbb44f"
TARGET_TREE = "3eb31ad4643617d37e07ac0ad03412bf7f237aa4"
TARGET_BASE = "d887b9a8fa410dcccb59ee364e9e19d0666dce23"
TARGET_FILES = {
    "src/lib.rs": "fb16000550ca2a31036af721c3607d4e71ef2f40fc2994e34a0cf1d5d621e7da",
    "tests/issue153_paused_regressions.rs": "96afb4a790032c38c8ef70dead081f96ad3f67c86e521aea9bc087b4f4555e65",
}
CGQA_VERSION = "1.9.0"
CGQA_TAG = "v1.9.0"
CGQA_COMMIT = "6ab1f8b79a3211a7139e6f52da6b3fb7a75c0fb9"
CGQA_RELEASE_FILES = {
    "pyproject.toml": "f2d056cd51a96851cd10665c3742aec262d09e041f0042f4121894ae40d59506",
    "AGENTS.md": "17f8a837881e813165a1d1ad7e34f8410bb290450b60458284f25129a8a00958",
    "contractgraph_qa/__init__.py": "70c4e29b82aa2aac8a1b671463da2f4162e477cec6bc5f6071c36b2580ce7398",
    "contractgraph_qa/cli.py": "67d56568173bb2f966968da15399d9e12c4c52c9a853e3a6777ad2fc35a408ac",
    "contractgraph_qa/proof_integrity.py": "e98d16aee965afa8015070c961b28e9a0b0d4aebba3906570a5de15157226dec",
    "contractgraph_qa/transition_geometry.py": "8b4976d6110f71676c1f8ac24905150682524c9acc6280ad0d2a627edde56fdb",
}
CGQA_RELEASE_TREE_FILE_COUNT = 523
CGQA_RELEASE_TREE_TOTAL_BYTES = 7_782_031
CGQA_RELEASE_TREE_MANIFEST_SHA256 = "25ef98993d124175a5b82a367a037ee5d73a2553231cb1526e72216aeb95f65f"
MAX_BATCH = 25
U64_MAX = (1 << 64) - 1
I128_MAX = (1 << 127) - 1


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode()).hexdigest()


def sat_mul(left: int, right: int) -> int:
    return min(I128_MAX, max(0, left) * max(0, right))


@dataclass(frozen=True)
class Config:
    rate: int
    initial: int
    end: int


@dataclass(frozen=True)
class Attempt:
    kind: str
    at: int
    actor: str
    accepted: bool


@dataclass(frozen=True)
class Flags:
    no_end_cap: bool = False
    pause_advances_cursor: bool = True
    paused_cursor_floor: bool = True
    stop_accounts: bool = True
    late_resume_resurrection: bool = False
    duplicate_interval_pay: bool = False
    partial_batch_mutation: bool = False
    wrong_actor_terminalization: bool = False
    pause_resume_underpayment: bool = False
    zero_pause_sentinel: bool = True  # exact 2baa37b representation


@dataclass
class Machine:
    config: Config
    flags: Flags = field(default_factory=Flags)
    phase: str = "Created"
    cursor: int = 0
    paused_at: int = 0
    paused: bool = False
    balance: int = 0
    paid: int = 0
    now: int = 0
    resurrected: bool = False
    stored_end: int | None = None
    attempts: list[Attempt] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.balance == 0 and self.paid == 0:
            self.balance = self.config.initial
        if self.stored_end is None:
            self.stored_end = self.config.end

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.phase,
            self.cursor,
            self.paused_at,
            self.paused,
            self.balance,
            self.paid,
            self.now,
            self.resurrected,
            self.stored_end,
            tuple(self.attempts),
        )

    def _record(self, kind: str, at: int, actor: str, accepted: bool) -> None:
        self.now = at
        self.attempts.append(Attempt(kind, at, actor, accepted))

    def _authorized(self, kind: str, actor: str) -> bool:
        if kind in {"start", "pause", "resume", "cancel", "stop"}:
            if actor != "payer":
                return self.flags.wrong_actor_terminalization and kind in {"cancel", "stop"}
        return True

    def _end_bound(self, at: int) -> int:
        if self.stored_end == 0 or self.flags.no_end_cap or self.resurrected:
            return at
        return min(at, int(self.stored_end))

    def _boundary(self, at: int) -> int:
        bound = self._end_bound(at)
        return min(bound, self.paused_at) if self.paused else bound

    def _account(self, at: int, kind: str) -> int:
        boundary = self._boundary(at)
        cursor = self.cursor
        if self.paused and self.flags.paused_cursor_floor:
            cursor = max(cursor, self.paused_at)
        amount = min(self.balance, sat_mul(self.config.rate, max(0, boundary - cursor)))
        self.balance -= amount
        self.paid += amount
        if not (self.flags.duplicate_interval_pay and kind in {"settle", "batch_settle"}):
            self.cursor = boundary
        return amount

    def act(self, kind: str, at: int, actor: str = "payer") -> tuple[bool, int]:
        before = self.snapshot()
        if at < self.now:
            self._record(kind, at, actor, False)
            return False, 0
        if not self._authorized(kind, actor):
            self._record(kind, at, actor, False)
            return False, 0

        if kind == "start":
            accepted = self.phase != "Live" and (self.stored_end == 0 or at < int(self.stored_end))
            if accepted:
                self.phase, self.cursor, self.paused, self.paused_at = "Live", at, False, 0
            self._record(kind, at, actor, accepted)
            return accepted, 0

        if kind in {"settle", "batch_settle"} and self.phase == "Created":
            self._record(kind, at, actor, True)
            return True, 0
        if kind in {"settle", "batch_settle"} and self.phase == "Terminal":
            self._record(kind, at, actor, True)
            return True, 0
        if kind in {"pause", "resume", "cancel", "stop"} and self.phase != "Live":
            self._record(kind, at, actor, False)
            return False, 0
        if kind == "pause" and self.paused:
            self._record(kind, at, actor, False)
            return False, 0
        if kind == "resume" and not self.paused:
            self._record(kind, at, actor, False)
            return False, 0
        if kind not in {"pause", "resume", "settle", "batch_settle", "cancel", "stop"}:
            self._record(kind, at, actor, False)
            return False, 0

        moved = 0
        reached_end = self.stored_end != 0 and at >= int(self.stored_end)
        if kind == "pause":
            old_cursor = self.cursor
            moved = self._account(at, kind)
            if not self.flags.pause_advances_cursor:
                self.cursor = old_cursor
            if reached_end and not self.flags.no_end_cap:
                self.phase, self.paused, self.paused_at = "Terminal", False, 0
            else:
                boundary = self._end_bound(at)
                self.paused_at = boundary
                self.paused = not (self.flags.zero_pause_sentinel and boundary == 0)
        elif kind == "resume":
            if reached_end and not self.flags.late_resume_resurrection:
                self.phase, self.paused, self.paused_at = "Terminal", False, 0
            else:
                self.cursor = at
                if self.flags.late_resume_resurrection and reached_end:
                    self.resurrected = True
                if not self.flags.pause_resume_underpayment:
                    self.paused, self.paused_at = False, 0
        else:
            if kind != "stop" or self.flags.stop_accounts:
                moved = self._account(at, kind)
            if kind in {"cancel", "stop"} or (reached_end and not self.flags.no_end_cap):
                self.phase, self.paused, self.paused_at = "Terminal", False, 0
                if kind in {"cancel", "stop"}:
                    self.stored_end = self._end_bound(at)

        self._record(kind, at, actor, True)
        assert before != self.snapshot()
        return True, moved


@dataclass(frozen=True)
class OracleProjection:
    accepted: tuple[bool, ...]
    intervals: tuple[tuple[int, int], ...]
    eligible_seconds: int
    phase: str


def oracle_projection(config: Config, attempts: Iterable[Attempt], observed_at: int) -> OracleProjection:
    """Replay action history without consulting candidate state or arithmetic."""

    phase = "Created"
    opened: int | None = None
    intervals: list[tuple[int, int]] = []
    accepted_rows: list[bool] = []

    def close(at: int) -> None:
        nonlocal opened
        if opened is None:
            return
        right = at if config.end == 0 else min(at, config.end)
        left = opened if config.end == 0 else min(opened, config.end)
        if right > left:
            intervals.append((left, right))
        opened = None

    for attempt in attempts:
        kind, at, actor = attempt.kind, attempt.at, attempt.actor
        auth = actor == "payer" or kind in {"settle", "batch_settle"}
        if kind == "start":
            accepted = auth and phase == "Created" and (config.end == 0 or at < config.end)
        elif kind == "pause":
            accepted = auth and phase == "Active"
        elif kind == "resume":
            accepted = auth and phase == "Paused"
        elif kind in {"cancel", "stop"}:
            accepted = auth and phase in {"Active", "Paused"}
        elif kind in {"settle", "batch_settle"}:
            accepted = True
        else:
            accepted = False
        accepted_rows.append(accepted)
        if not accepted:
            continue
        if kind == "start":
            phase, opened = "Active", at
        elif kind == "pause":
            close(at)
            phase = "Terminal" if config.end != 0 and at >= config.end else "Paused"
        elif kind == "resume":
            if config.end != 0 and at >= config.end:
                phase = "Terminal"
            else:
                phase, opened = "Active", at
        elif kind in {"cancel", "stop"}:
            close(at)
            phase = "Terminal"
        elif kind in {"settle", "batch_settle"} and config.end != 0 and at >= config.end:
            close(config.end)
            phase = "Terminal"

    if phase == "Active" and opened is not None:
        right = observed_at if config.end == 0 else min(observed_at, config.end)
        if right > opened:
            intervals.append((opened, right))
    merged: list[tuple[int, int]] = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
        else:
            merged.append((left, right))
    eligible = sum(right - left for left, right in merged)
    return OracleProjection(tuple(accepted_rows), tuple(merged), eligible, phase)


def expected_paid(machine: Machine) -> int:
    oracle = oracle_projection(machine.config, machine.attempts, machine.now)
    return min(machine.config.initial, sat_mul(machine.config.rate, oracle.eligible_seconds))


def economic_tuple(machine: Machine) -> tuple[int, int, int]:
    payer_returned = machine.balance if machine.phase == "Terminal" else 0
    custody = 0 if machine.phase == "Terminal" else machine.balance
    return machine.paid, payer_returned, custody


def geometry_matrix(flags: Flags) -> list[dict[str, object]]:
    """Compute the declared H5 pair classifications from fresh candidate paths."""

    rows: list[dict[str, object]] = []

    def classify(pair_id: str, left_actions: list[tuple[str, str]], right_actions: list[tuple[str, str]]) -> None:
        left = started(Config(1, 100, 10), 1, flags)
        right = started(Config(1, 100, 10), 1, flags)
        for kind, actor in left_actions:
            left.act(kind, 3, actor)
        for kind, actor in right_actions:
            right.act(kind, 3, actor)
        left_semantic = (left.phase, left.paused, left.cursor, left.stored_end, economic_tuple(left), tuple(item.accepted for item in left.attempts[1:]))
        right_semantic = (right.phase, right.paused, right.cursor, right.stored_end, economic_tuple(right), tuple(item.accepted for item in right.attempts[1:]))
        left_history = tuple(item.kind for item in left.attempts)
        right_history = tuple(item.kind for item in right.attempts)
        classification = "TORSION_DETECTED" if left_semantic != right_semantic else "HISTORY_DIVERGENT" if left_history != right_history else "CLOSED"
        rows.append({"id": pair_id, "classification": classification, "leftSemantic": left_semantic, "rightSemantic": right_semantic, "leftHistory": left_history, "rightHistory": right_history})

    classify("settle-cancel", [("settle", "public"), ("cancel", "payer")], [("cancel", "payer"), ("settle", "public")])
    classify("settle-stop", [("settle", "public"), ("stop", "payer")], [("stop", "payer"), ("settle", "public")])
    classify("pause-settle", [("pause", "payer"), ("settle", "public")], [("settle", "public"), ("pause", "payer")])
    classify("settle-batch", [("settle", "public")], [("batch_settle", "public")])
    classify("pause-cancel", [("pause", "payer"), ("cancel", "payer")], [("cancel", "payer"), ("pause", "payer")])
    classify("pause-stop", [("pause", "payer"), ("stop", "payer")], [("stop", "payer"), ("pause", "payer")])
    classify("pause-resume-settle", [("pause", "payer"), ("resume", "payer"), ("settle", "public")], [("settle", "public"), ("pause", "payer"), ("resume", "payer")])
    classify("settle-then-batch-order", [("settle", "public"), ("batch_settle", "public")], [("batch_settle", "public"), ("settle", "public")])

    forward = BatchWorld({1: started(Config(1, 100, 10), 1, flags), 2: started(Config(2, 100, 10), 1, flags)}, flags)
    reverse = copy.deepcopy(forward)
    ok_f, values_f = forward.settle([1, 2], 3)
    ok_r, values_r = reverse.settle([2, 1], 3)
    by_id_f = dict(zip([1, 2], values_f)); by_id_r = dict(zip([2, 1], values_r))
    closed = ok_f and ok_r and by_id_f == by_id_r and forward.snapshot() == reverse.snapshot()
    rows.append({"id": "batch-permutation", "classification": "CLOSED" if closed else "TORSION_DETECTED", "leftById": by_id_f, "rightById": by_id_r})
    return rows


@dataclass
class CheckBook:
    rows: list[dict[str, object]] = field(default_factory=list)

    def check(self, check_id: str, ok: bool, *, hypothesis: str, detail: str = "", applicability: str = "PRODUCTION") -> None:
        self.rows.append({
            "id": check_id,
            "hypothesis": hypothesis,
            "status": "pass" if ok else "fail",
            "applicability": applicability,
            "detail": detail,
        })


def started(config: Config, at: int, flags: Flags | None = None) -> Machine:
    machine = Machine(config, flags or Flags())
    accepted, _ = machine.act("start", at)
    assert accepted
    return machine


def exact(book: CheckBook, check_id: str, machine: Machine, hypothesis: str, applicability: str = "PRODUCTION") -> None:
    oracle = oracle_projection(machine.config, machine.attempts, machine.now)
    acceptance_ok = tuple(row.accepted for row in machine.attempts) == oracle.accepted
    accounting_ok = machine.paid == expected_paid(machine)
    conservation_ok = sum(economic_tuple(machine)) == machine.config.initial
    book.check(
        check_id,
        acceptance_ok and accounting_ok and conservation_ok,
        hypothesis=hypothesis,
        applicability=applicability,
        detail=f"actualPaid={machine.paid}, expectedPaid={expected_paid(machine)}, intervals={oracle.intervals}, acceptanceParity={acceptance_ok}, conservation={economic_tuple(machine)}",
    )


@dataclass
class BatchWorld:
    streams: dict[int, Machine]
    flags: Flags = field(default_factory=Flags)

    def snapshot(self) -> tuple[tuple[int, tuple[object, ...]], ...]:
        return tuple((key, value.snapshot()) for key, value in sorted(self.streams.items()))

    def settle(self, ids: list[int], at: int) -> tuple[bool, list[int]]:
        if len(ids) > MAX_BATCH:
            return False, []
        stage = copy.deepcopy(self.streams)
        amounts: list[int] = []
        for stream_id in ids:
            if stream_id not in stage:
                if self.flags.partial_batch_mutation:
                    self.streams = stage
                return False, []
            _, amount = stage[stream_id].act("batch_settle", at, "public")
            amounts.append(amount)
        self.streams = stage
        return True, amounts


def run_hypotheses(flags: Flags = Flags()) -> CheckBook:
    book = CheckBook()

    # H1: absolute end with non-zero/delayed starts.
    bounded = started(Config(1, 100, 110), 100, flags)
    bounded.act("settle", 109, "public")
    bounded.act("settle", 111, "public")
    exact(book, "H1.bounded-nonzero-start", bounded, "absolute end caps eligible [100,110]")
    unlimited = started(Config(3, 100, 0), 100, flags)
    unlimited.act("settle", 105, "public")
    exact(book, "H1.unlimited-nonzero-start", unlimited, "unlimited stream accrues from delayed start")
    delayed = Machine(Config(1, 20, 110), flags, now=100)
    delayed.act("start", 109); delayed.act("settle", 110, "public")
    exact(book, "H1.created-then-delayed-start", delayed, "Created at t=100, start at t=109, settle at absolute end earns one second")
    rejected = Machine(Config(1, 100, 110), flags)
    before = (rejected.phase, rejected.cursor, rejected.paused_at, rejected.paused, rejected.balance, rejected.paid)
    rejected.act("start", 110)
    after = (rejected.phase, rejected.cursor, rejected.paused_at, rejected.paused, rejected.balance, rejected.paid)
    book.check("H1.start-at-end-atomic", rejected.phase == "Created" and rejected.balance == 100 and before == after, hypothesis="start at configured end rejects without economic mutation")

    # H2: exact-head sentinel ambiguity exists only at test-host timestamp zero.
    zero = started(Config(1, 10, 10), 0, flags)
    zero.act("pause", 0)
    zero.act("settle", 2, "public")
    zero.act("resume", 3)
    exact(book, "H2.timestamp-zero-pause", zero, "pause at zero must freeze and remain resumable", "TEST_HOST_ONLY_CORE_REJECTS_ZERO_CLOSE_TIME")
    zero_terminal_rows: list[dict[str, object]] = []
    for terminal_kind in ("cancel", "stop"):
        candidate = started(Config(1, 10, 10), 0, flags)
        candidate.act(terminal_kind, 0)
        restart_accepted, _ = candidate.act("start", 1)
        _, resurrected_paid = candidate.act("settle", 2, "public")
        oracle = oracle_projection(candidate.config, candidate.attempts, candidate.now)
        zero_terminal_rows.append({"kind": terminal_kind, "storedEnd": candidate.stored_end, "restartAccepted": restart_accepted, "resurrectedPaid": resurrected_paid, "actualPaid": candidate.paid, "expectedPaid": min(candidate.config.initial, sat_mul(candidate.config.rate, oracle.eligible_seconds)), "acceptanceParity": tuple(item.accepted for item in candidate.attempts) == oracle.accepted})
    terminal_zero_safe = all(not row["restartAccepted"] and row["resurrectedPaid"] == 0 and row["acceptanceParity"] for row in zero_terminal_rows)
    book.check("H2.timestamp-zero-terminal-end-sentinel", terminal_zero_safe, hypothesis="cancel/stop at zero must not rewrite a bounded end into the unlimited sentinel and permit restart", applicability="TEST_HOST_ONLY_CORE_REJECTS_ZERO_CLOSE_TIME", detail=json.dumps(zero_terminal_rows, sort_keys=True))

    # H3: persisted legacy shapes before/exactly/after end and irreversible old overpayment.
    for pause_at, observe_at, paid, balance in ((105, 109, 5, 15), (110, 110, 10, 10)):
        legacy = Machine(Config(1, 20, 110), flags, phase="Live", cursor=100, paused_at=pause_at, paused=True, balance=balance, paid=paid, now=pause_at)
        legacy.attempts = [Attempt("start", 100, "payer", True), Attempt("pause", pause_at, "payer", True)]
        legacy.act("settle", observe_at, "public")
        exact(book, f"H3.legacy-paused-{pause_at}", legacy, "already-paid legacy interval cannot replay")
    overpaid = Machine(Config(1, 20, 110), flags, phase="Live", cursor=100, paused_at=112, paused=True, balance=8, paid=12, now=112)
    overpaid.attempts = [Attempt("start", 100, "payer", True), Attempt("pause", 112, "payer", True)]
    detected = overpaid.paid > expected_paid(overpaid)
    accepted_overpaid, added_overpaid = overpaid.act("settle", 113, "public")
    book.check("H3.irreversible-historical-overpayment", detected and accepted_overpaid and added_overpaid == 0 and overpaid.paid == 12 and overpaid.phase == "Terminal", hypothesis="historical value already paid past end is detectable but not recoverable by cursor repair", applicability="PERSISTED_PRE_FIX_HISTORY_DEPLOYMENT_UNPROVEN")

    # H4: stop and cancel have equal economics but distinct causal history.
    stop = started(Config(1, 100, 10), 1, flags)
    cancel = started(Config(1, 100, 10), 1, flags)
    stop.act("stop", 4)
    cancel.act("cancel", 4)
    exact(book, "H4.stop-exact", stop, "stop accounts earned time")
    exact(book, "H4.cancel-exact", cancel, "cancel accounts earned time")
    book.check("H4.history-divergent", economic_tuple(stop) == economic_tuple(cancel) and stop.attempts[-1].kind != cancel.attempts[-1].kind, hypothesis="stop/cancel are economically closed but history-divergent")

    # H5: same-ledger geometry and duplicate IDs.
    left = started(Config(1, 100, 10), 1, flags)
    right = copy.deepcopy(left)
    left.act("settle", 3, "public"); left.act("pause", 3)
    right.act("pause", 3); right.act("settle", 3, "public")
    book.check("H5.same-ledger-geometry", economic_tuple(left) == economic_tuple(right) and left.attempts != right.attempts, hypothesis="same-ledger settle/pause order is HISTORY_DIVERGENT, not economic torsion")
    duplicate = BatchWorld({1: started(Config(1, 100, 10), 1, flags)}, flags)
    accepted, amounts = duplicate.settle([1, 1], 3)
    book.check("H5.duplicate-batch-id", accepted and amounts == [2, 0], hypothesis="duplicate id pays interval at most once")
    repeated = started(Config(1, 100, 10), 1, flags)
    first_repeat_ok, first_repeat_amount = repeated.act("settle", 3, "public")
    second_repeat_ok, second_repeat_amount = repeated.act("settle", 3, "public")
    book.check("H5.direct-repeat-settle", first_repeat_ok and second_repeat_ok and (first_repeat_amount, second_repeat_amount) == (2, 0) and repeated.paid == 2, hypothesis="direct settle→settle at one ledger time pays the interval once")
    expected_geometry = {
        "settle-cancel": "HISTORY_DIVERGENT",
        "settle-stop": "HISTORY_DIVERGENT",
        "pause-settle": "HISTORY_DIVERGENT",
        "settle-batch": "HISTORY_DIVERGENT",
        "pause-cancel": "TORSION_DETECTED",
        "pause-stop": "TORSION_DETECTED",
        "pause-resume-settle": "HISTORY_DIVERGENT",
        "settle-then-batch-order": "HISTORY_DIVERGENT",
        "batch-permutation": "CLOSED",
    }
    for row in geometry_matrix(flags):
        book.check(f"H5.geometry-{row['id']}", row["classification"] == expected_geometry[row["id"]], hypothesis=f"computed geometry classification is {expected_geometry[row['id']]}", detail=json.dumps(row, sort_keys=True))

    # H6: collection-level atomicity and bounds.
    active = started(Config(1, 100, 10), 1, flags)
    paused = started(Config(1, 100, 10), 1, flags); paused.act("pause", 2)
    terminal = started(Config(1, 100, 10), 1, flags); terminal.act("cancel", 2)
    mixed = BatchWorld({1: active, 2: paused, 3: terminal}, flags)
    ok, values = mixed.settle([1, 2, 3], 3)
    book.check("H6.mixed-batch", ok and values == [2, 0, 0], hypothesis="active/paused/terminal ordered batch preserves item semantics")
    def mixed_world() -> BatchWorld:
        a = started(Config(1, 100, 10), 1, flags)
        p = started(Config(1, 100, 10), 1, flags); p.act("pause", 2)
        t = started(Config(1, 100, 10), 1, flags); t.act("cancel", 2)
        return BatchWorld({1: a, 2: p, 3: t}, flags)
    forward = mixed_world(); reverse = mixed_world()
    ok_f, amounts_f = forward.settle([1, 2, 3], 3); ok_r, amounts_r = reverse.settle([3, 2, 1], 3)
    normalized_f = dict(zip([1, 2, 3], amounts_f)); normalized_r = dict(zip([3, 2, 1], amounts_r))
    book.check("H6.mixed-batch-reverse-closed", ok_f and ok_r and normalized_f == normalized_r and forward.snapshot() == reverse.snapshot(), hypothesis="reversing independent stream IDs is CLOSED after normalization by stream id")
    rollback = BatchWorld({1: started(Config(1, 100, 10), 1, flags)}, flags)
    before = rollback.snapshot(); accepted, _ = rollback.settle([1, 99], 3)
    book.check("H6.missing-id-rollback", not accepted and rollback.snapshot() == before, hypothesis="missing id after valid id rolls back full state")
    twenty_five = BatchWorld({i: started(Config(1, 100, 10), 1, flags) for i in range(25)}, flags)
    accepted25, values25 = twenty_five.settle(list(range(25)), 2)
    book.check("H6.bound-25", accepted25 and len(values25) == 25, hypothesis="exact maximum batch succeeds")
    twenty_six = BatchWorld({i: started(Config(1, 100, 10), 1, flags) for i in range(26)}, flags)
    before26 = twenty_six.snapshot(); accepted26, _ = twenty_six.settle(list(range(26)), 2)
    book.check("H6.bound-26-rollback", not accepted26 and twenty_six.snapshot() == before26, hypothesis="oversized batch rejects atomically")
    empty = BatchWorld({1: started(Config(1, 100, 10), 1, flags)}, flags)
    before_empty = empty.snapshot(); empty_ok, empty_values = empty.settle([], 2)
    book.check("H6.empty", empty_ok and empty_values == [] and empty.snapshot() == before_empty, hypothesis="empty batch is no-op")

    # H7: exhaustion on every value path never resurrects principal.
    for kind in ("settle", "pause", "cancel", "stop"):
        exhausted = started(Config(10, 15, 0), 1, flags)
        exhausted.act(kind, 3, "public" if kind == "settle" else "payer")
        after = exhausted.paid
        exhausted.act("settle", 100, "public")
        book.check(f"H7.exhaustion-{kind}", after == 15 and exhausted.paid == 15 and exhausted.balance == 0, hypothesis=f"{kind} respects balance cap and later calls cannot resurrect value")
    exhausted_batch = BatchWorld({1: started(Config(10, 15, 0), 1, flags)}, flags)
    _, first = exhausted_batch.settle([1], 3); _, second = exhausted_batch.settle([1], 100)
    book.check("H7.exhaustion-batch", first == [15] and second == [0], hypothesis="batch respects exhaustion")

    # H8: actor and failure matrix, exact state equality excluding attempt receipts.
    for kind, prepare in (
        ("start", lambda: Machine(Config(1, 100, 10), flags)),
        ("pause", lambda: started(Config(1, 100, 10), 1, flags)),
        ("resume", lambda: (lambda m: (m.act("pause", 2), m)[1])(started(Config(1, 100, 10), 1, flags))),
        ("cancel", lambda: started(Config(1, 100, 10), 1, flags)),
        ("stop", lambda: started(Config(1, 100, 10), 1, flags)),
    ):
        candidate = prepare(); before = (candidate.phase, candidate.cursor, candidate.paused_at, candidate.paused, candidate.balance, candidate.paid)
        candidate.act(kind, max(2, candidate.now), "intruder")
        after = (candidate.phase, candidate.cursor, candidate.paused_at, candidate.paused, candidate.balance, candidate.paid)
        book.check(f"H8.unauthorized-{kind}", before == after and not candidate.attempts[-1].accepted, hypothesis=f"unauthorized {kind} rejects without state mutation")
    public = started(Config(1, 100, 10), 1, flags); public.act("settle", 2, "intruder")
    exact(book, "H8.permissionless-settle", public, "settlement remains permissionless")
    invalid = started(Config(1, 100, 10), 1, flags); before_invalid = economic_tuple(invalid); invalid.act("resume", 2)
    book.check("H8.invalid-resume-atomic", economic_tuple(invalid) == before_invalid and not invalid.attempts[-1].accepted, hypothesis="invalid lifecycle call is atomic")
    inactive = Machine(Config(1, 100, 10), flags); inactive.act("settle", 3, "public")
    exact(book, "H8.permissionless-inactive-settle-zero", inactive, "permissionless settlement of an inactive Created stream returns zero and does not accrue")

    # H9: saturation and metamorphic relations.
    extreme = started(Config(I128_MAX, I128_MAX, 0), 1, flags); extreme.act("settle", U64_MAX, "public")
    book.check("H9.i128-u64-saturation", extreme.paid == I128_MAX and extreme.balance == 0, hypothesis="extreme product saturates then caps at balance")
    one = started(Config(3, 100, 20), 5, flags); one.act("settle", 11, "public")
    split = started(Config(3, 100, 20), 5, flags); split.act("settle", 8, "public"); split.act("settle", 11, "public")
    book.check("H9.split-settlement", economic_tuple(one) == economic_tuple(split), hypothesis="splitting a settlement preserves economics")
    shifted = started(Config(3, 100, 120), 105, flags); shifted.act("settle", 111, "public")
    book.check("H9.time-translation", economic_tuple(one) == economic_tuple(shifted), hypothesis="translating start/end/action by a constant preserves economics")

    # H10: derive the explicit lifecycle consequence while keeping token custody/TTL out of claim.
    archived = started(Config(1, 100, 110), 100, flags)
    first_ok, first_paid = archived.act("settle", 110, "public")
    second_ok, second_paid = archived.act("settle", 120, "public")
    restart_ok, _ = archived.act("start", 121)
    archive_policy_accepts = archived.phase == "Terminal" and archived.balance == 0
    book.check("H10.archive-out-of-scope-watchpoint", first_ok and first_paid == 10 and second_ok and second_paid == 0 and not restart_ok and not archive_policy_accepts and economic_tuple(archived) == (10, 90, 0), hypothesis="natural-end retained balance activates an explicit lifecycle/archive watchpoint", applicability="OUT_OF_SCOPE_WATCHPOINT", detail="model derives terminal balance=90, repeat settle=0, restart rejected, archive policy rejects nonzero balance; token custody lock and TTL behavior are not modeled or claimed")

    return book


MUTANTS = {
    "no_end_cap": Flags(no_end_cap=True, zero_pause_sentinel=False),
    "stale_pause_cursor": Flags(pause_advances_cursor=False, paused_cursor_floor=False, zero_pause_sentinel=False),
    "ignore_legacy_cursor": Flags(paused_cursor_floor=False, zero_pause_sentinel=False),
    "stop_without_earned_accounting": Flags(stop_accounts=False, zero_pause_sentinel=False),
    "late_resume_accrual_resurrection": Flags(late_resume_resurrection=True, zero_pause_sentinel=False),
    "duplicate_interval_pay": Flags(duplicate_interval_pay=True, zero_pause_sentinel=False),
    "partial_batch_mutation": Flags(partial_batch_mutation=True, zero_pause_sentinel=False),
    "wrong_actor_terminalization": Flags(wrong_actor_terminalization=True, zero_pause_sentinel=False),
    "pause_resume_underpayment": Flags(pause_resume_underpayment=True, zero_pause_sentinel=False),
}


def mutant_probe(name: str, flags: Flags) -> tuple[bool, str]:
    if name == "no_end_cap":
        m = started(Config(1, 10, 1), 0, flags); m.act("settle", 2, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "stale_pause_cursor":
        m = started(Config(1, 10, 10), 0, flags); m.act("pause", 2); m.act("settle", 3, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "ignore_legacy_cursor":
        m = Machine(Config(1, 10, 10), flags, phase="Live", cursor=0, paused_at=2, paused=True, balance=8, paid=2, now=2)
        m.attempts = [Attempt("start", 0, "payer", True), Attempt("pause", 2, "payer", True)]; m.act("settle", 3, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "stop_without_earned_accounting":
        m = started(Config(1, 10, 10), 0, flags); m.act("stop", 2)
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "late_resume_accrual_resurrection":
        m = started(Config(1, 100, 10), 0, flags); m.act("pause", 2); m.act("resume", 11); m.act("settle", 12, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "duplicate_interval_pay":
        m = started(Config(1, 10, 10), 0, flags); m.act("settle", 2, "public"); m.act("settle", 2, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    if name == "partial_batch_mutation":
        world = BatchWorld({1: started(Config(1, 10, 10), 0, flags)}, flags); before = world.snapshot(); accepted, _ = world.settle([1, 99], 2)
        return (not accepted and world.snapshot() != before), "rejected batch mutated prefix"
    if name == "wrong_actor_terminalization":
        m = started(Config(1, 10, 10), 0, flags); m.act("cancel", 2, "intruder")
        oracle = oracle_projection(m.config, m.attempts, m.now)
        return tuple(row.accepted for row in m.attempts) != oracle.accepted, "wrong actor accepted terminal action"
    if name == "pause_resume_underpayment":
        m = started(Config(1, 10, 10), 0, flags); m.act("pause", 2); m.act("resume", 3); m.act("settle", 5, "public")
        return m.paid != expected_paid(m), f"actual={m.paid}, expected={expected_paid(m)}"
    raise AssertionError(name)


def git(root: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        capture_output=True,
        text=not binary,
        check=False,
    )


def bind_target(root: Path) -> dict[str, object]:
    root = root.resolve()
    head = git(root, "rev-parse", "HEAD").stdout.strip()
    tree = git(root, "rev-parse", f"{TARGET_SHA}^{{tree}}").stdout.strip()
    merge_base = git(root, "merge-base", TARGET_BASE, TARGET_SHA).stdout.strip()
    diff_result = git(root, "diff", "--name-only", f"{TARGET_BASE}...{TARGET_SHA}")
    diff_paths = sorted(line.strip() for line in diff_result.stdout.splitlines() if line.strip())
    tracked_status = git(root, "status", "--porcelain=v1", "--untracked-files=no").stdout.strip()
    files: dict[str, object] = {}
    valid = head == TARGET_SHA and tree == TARGET_TREE and merge_base == TARGET_BASE and diff_paths == sorted(TARGET_FILES) and tracked_status == ""
    for relative, expected in TARGET_FILES.items():
        blob = git(root, "show", f"{TARGET_SHA}:{relative}", binary=True)
        actual = sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None
        commit_oid = git(root, "rev-parse", f"{TARGET_SHA}:{relative}").stdout.strip()
        work_oid = git(root, "hash-object", relative).stdout.strip()
        row_valid = actual == expected and commit_oid == work_oid
        files[relative] = {"expectedSha256": expected, "actualSha256": actual, "workingCanonicalMatches": commit_oid == work_oid, "valid": row_valid}
        valid = valid and row_valid
    return {"valid": valid, "repository": TARGET_REPOSITORY, "expectedCommit": TARGET_SHA, "actualCommit": head, "expectedTree": TARGET_TREE, "actualTree": tree, "expectedBase": TARGET_BASE, "actualMergeBase": merge_base, "expectedDiffPaths": sorted(TARGET_FILES), "actualDiffPaths": diff_paths, "trackedWorktreeClean": tracked_status == "", "untrackedFilesExcluded": True, "files": files, "claimBoundary": "The exact Git tree binds the complete committed subject; merge-base, PR diff paths, all tracked-worktree cleanliness, and the two changed-file bytes are checked. Untracked audit artifacts are explicitly outside this binding."}


def release_tree_fingerprint(root: Path) -> dict[str, object]:
    """Hash every extracted release file except VCS/interpreter cache metadata."""
    excluded_parts = {".git", "__pycache__", ".pytest_cache"}
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if not path.is_file() or path.suffix == ".pyc" or any(part in excluded_parts for part in relative.parts):
            continue
        payload = path.read_bytes()
        entries.append({"path": relative.as_posix(), "size": len(payload), "sha256": sha256(payload).hexdigest()})
    return {
        "fileCount": len(entries),
        "totalBytes": sum(int(row["size"]) for row in entries),
        "manifestSha256": canonical_hash(entries),
        "algorithm": "SHA-256 of canonical JSON [{path,size,sha256}], sorted by POSIX-relative path",
        "exclusions": [".git/", "__pycache__/", ".pytest_cache/", "*.pyc"],
    }


def bind_runtime(root: Path) -> dict[str, object]:
    root = root.resolve()
    files: dict[str, object] = {}
    expected_import = (root / "contractgraph_qa" / "__init__.py").resolve()
    actual_import = Path(contractgraph_qa.__file__).resolve()
    try:
        actual_import_relative = actual_import.relative_to(root).as_posix()
    except ValueError:
        actual_import_relative = None
    valid = contractgraph_qa.__version__ == CGQA_VERSION and actual_import == expected_import
    for relative, expected in CGQA_RELEASE_FILES.items():
        path = root / relative
        actual = sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        files[relative] = {"expectedSha256": expected, "actualSha256": actual, "valid": actual == expected}
        valid = valid and actual == expected
    release_tree = release_tree_fingerprint(root)
    release_tree_valid = (
        release_tree["fileCount"] == CGQA_RELEASE_TREE_FILE_COUNT
        and release_tree["totalBytes"] == CGQA_RELEASE_TREE_TOTAL_BYTES
        and release_tree["manifestSha256"] == CGQA_RELEASE_TREE_MANIFEST_SHA256
    )
    valid = valid and release_tree_valid
    git_present = (root / ".git").exists()
    git_head = git(root, "rev-parse", "HEAD") if git_present else None
    actual_commit = git_head.stdout.strip() if git_head and git_head.returncode == 0 else None
    if git_present:
        valid = valid and git_head is not None and git_head.returncode == 0 and actual_commit == CGQA_COMMIT
    return {"valid": valid, "expectedVersion": CGQA_VERSION, "actualVersion": contractgraph_qa.__version__, "expectedTag": CGQA_TAG, "expectedCommit": CGQA_COMMIT, "actualCommit": actual_commit, "expectedImportedSource": "contractgraph_qa/__init__.py", "actualImportedSourceRelativeToRoot": actual_import_relative, "importedSourceMatchesRoot": actual_import == expected_import, "gitMetadataPresent": git_present, "gitResolutionValid": (not git_present) or (git_head is not None and git_head.returncode == 0 and actual_commit == CGQA_COMMIT), "selectedCriticalFileFingerprint": files, "completeReleaseTreeFingerprint": {"valid": release_tree_valid, "expectedFileCount": CGQA_RELEASE_TREE_FILE_COUNT, "expectedTotalBytes": CGQA_RELEASE_TREE_TOTAL_BYTES, "expectedManifestSha256": CGQA_RELEASE_TREE_MANIFEST_SHA256, **release_tree}, "commitBoundary": "The imported package must resolve under the supplied root. A checkout with .git must resolve exactly to the declared commit; an extracted release is bound by every regular source file through the complete release-tree fingerprint. VCS metadata and generated interpreter caches are excluded explicitly."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-checkout", type=Path, required=True)
    parser.add_argument("--cgqa-root", type=Path, required=True)
    args = parser.parse_args()

    target = bind_target(args.target_checkout)
    runtime = bind_runtime(args.cgqa_root)
    baseline = run_hypotheses()
    production_failures = [row for row in baseline.rows if row["status"] == "fail" and row["applicability"] == "PRODUCTION"]
    boundary_failures = [row for row in baseline.rows if row["status"] == "fail" and row["applicability"] != "PRODUCTION"]
    mutants = []
    for name, flags in MUTANTS.items():
        killed, detail = mutant_probe(name, flags)
        mutants.append({"id": name, "status": "killed" if killed else "survived", "detail": detail})

    verdict = "FAIL_BINDING" if not (target["valid"] and runtime["valid"]) else "COUNTEREXAMPLE_WITHIN_PRODUCTION_BOUND" if production_failures else "HOLD_TEST_HOST_BOUNDARY" if boundary_failures else "NO_NEW_COUNTEREXAMPLE_WITHIN_BOUND"
    output = {
        "schema": "cgqa/streampay-exact-settlement-second-audit/v0.2",
        "verdict": verdict,
        "targetBinding": target,
        "runtimeBinding": runtime,
        "oracle": {
            "kind": "accepted-action-history active-interval union",
            "readsCandidateCursor": False,
            "readsCandidatePausedAt": False,
            "readsCandidateLifecycle": False,
            "absoluteConfiguredEnd": True,
            "balanceCap": True,
        },
        "bounds": {"randomSeed": None, "deterministic": True, "hypotheses": "H1-H10", "scenarioChecks": len(baseline.rows), "mutants": len(mutants), "maxBatch": MAX_BATCH, "numericWitnesses": [0, 1, 2, 3, 9, 10, 11, 100, 105, 109, 110, 111, U64_MAX]},
        "checks": baseline.rows,
        "counts": {"passed": sum(row["status"] == "pass" for row in baseline.rows), "failed": sum(row["status"] == "fail" for row in baseline.rows), "productionFailures": len(production_failures), "boundaryFailures": len(boundary_failures)},
        "counterexamples": production_failures + boundary_failures,
        "mutants": mutants,
        "mutantsKilled": sum(row["status"] == "killed" for row in mutants),
        "geometry": {"source": "computed by geometry_matrix from fresh candidate paths", "pairs": geometry_matrix(Flags())},
        "compatibility": {"H4": "stop and cancel are economically equivalent in the modeled bound but preserve distinct action history; no terminal-enum redesign is inferred", "H10": "natural-end retained balance is an explicit lifecycle consequence and activates an out-of-scope archive watchpoint; token custody lock and TTL behavior remain unproven"},
        "watchpoints": [{"id": "archive-retained-balance", "status": "ACTIVATED", "observedShape": "terminal balance remains 90, repeat settle returns 0, restart rejects, archive policy rejects nonzero balance", "nonClaims": ["token custody lock", "TTL persistence/exhaustion"]}],
        "limitations": ["This is a supplemental bounded model, not exhaustive H1-H10 coverage; the native audit carries broader H1/H7/H8 matrices.", "The nine mutants are killed by dedicated independent-oracle probes; the main scenario suite is not claimed to kill each mutant.", "Model evidence is not native Rust execution.", "Timestamp zero is admitted by the Soroban test host but Stellar Core close-time monotonicity excludes a deployed ledger close at zero.", "A pre-fix transfer past configured end is detectable in storage/history but cannot be clawed back by a cursor-only repair.", "Batch rollback is modeled transactionally; native host tests remain authoritative for Soroban rollback."],
        "claimBoundary": "Bounded deterministic second-audit evidence for one exact target. It is not production proof, a security certification, or a substitute for native tests and GitHub CI.",
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    all_mutants_killed = all(row["status"] == "killed" for row in mutants)
    return 0 if target["valid"] and runtime["valid"] and not production_failures and all_mutants_killed else 1


if __name__ == "__main__":
    raise SystemExit(main())
