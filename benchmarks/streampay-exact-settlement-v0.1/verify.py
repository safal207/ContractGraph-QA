#!/usr/bin/env python3
"""Bounded CGQA v1.8 evidence for StreamPay issue #153.

This executable model binds one exact StreamPay commit.  It includes an
independent earned-time oracle and a paused-state mutant.  Native Rust tests
remain required: bounded PASS is not a production proof.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

import contractgraph_qa
from contractgraph_qa import __version__
from contractgraph_qa.reachability import (
    reachability_model_from_dict,
    run_reachability_model,
)

TARGET_REPOSITORY = "Streampay-Org/StreamPay-Contracts"
TARGET_ISSUE = 153
TARGET_PR = 161
TARGET_SHA = "058f72f0517fbf892b24358244696c55258a1a94"
CGQA_VERSION = "1.8.0"
CGQA_TAG = "v1.8.0"
CGQA_CORE_SHA = "51c8e81a42e53ea8b26b396f0c1df4f64418c351"
VERIFIER_PATH = "benchmarks/streampay-exact-settlement-v0.1/verify.py"
MAX_DEPTH = 4

INVARIANTS = {
    "I1": "once-only settlement: paid temporal intervals never overlap",
    "I2": "bounded accrual never crosses configured end_time",
    "I3": (
        "initial = recipient_accounted + payer_returned + remaining_custody"
    ),
    "I4": "natural-end terminality and terminal economic immutability",
    "I5": "authorization semantics and rejected-action atomicity",
    "I6": "exact recipient accounting for independently eligible active time",
    "I7": "pause cursor, paused_at, and terminal allocation remain coherent",
}
TERMINAL = frozenset({"Cancelled", "Ended"})
AUTH_ACTIONS = frozenset({"start", "pause", "resume", "cancel"})
PUBLIC_SETTLEMENT = frozenset({"settle", "batch_settle"})
VALUE_ACTIONS = frozenset({"pause", "settle", "batch_settle", "cancel"})


@dataclass(frozen=True, slots=True)
class Config:
    id: str
    rate: int
    initial_balance: int
    end_time: int
    graph_witnesses: tuple[int, ...]


CONFIGS = {
    "bounded": Config("bounded", 10, 1_000, 10, (2, 10, 11)),
    "unlimited": Config("unlimited", 10, 1_000, 0, (2, 100)),
    "small_balance": Config("small_balance", 10, 15, 1, (1, 2)),
}


@dataclass(frozen=True, slots=True)
class State:
    phase: str
    now: int
    cursor: int
    paused_at: int
    remaining_custody: int
    recipient_accounted: int
    payer_returned: int
    eligible_active_seconds: int
    terminal_boundary: int | None = None
    paid_intervals: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    at: int
    actor: str = "payer"

    @property
    def label(self) -> str:
        return f"{self.kind}:{self.actor}@{self.at}"


@dataclass(frozen=True, slots=True)
class Outcome:
    state: State
    moved_to_recipient: int
    returned_to_payer: int
    accepted: bool
    accrual_boundary: int | None


def initial_state(config: Config) -> State:
    return State("Created", 0, 0, 0, config.initial_balance, 0, 0, 0)


def contract_state(state: State) -> tuple[object, ...]:
    """State used for atomicity; excludes external observation/earned oracle."""

    return (
        state.phase,
        state.cursor,
        state.paused_at,
        state.remaining_custody,
        state.recipient_accounted,
        state.payer_returned,
        state.terminal_boundary,
        state.paid_intervals,
    )


def state_id(config: Config, state: State) -> str:
    intervals = ",".join(f"{a}-{b}" for a, b in state.paid_intervals) or "none"
    return (
        f"{config.id}:{state.phase}|now={state.now}|cursor={state.cursor}"
        f"|paused={state.paused_at}|custody={state.remaining_custody}"
        f"|recipient={state.recipient_accounted}|payer={state.payer_returned}"
        f"|eligible={state.eligible_active_seconds}"
        f"|terminal={state.terminal_boundary}|intervals={intervals}"
    )


def end_bound(config: Config, now: int) -> int:
    return now if config.end_time == 0 else min(now, config.end_time)


def accrual_bound(config: Config, state: State, now: int) -> int:
    boundary = end_bound(config, now)
    return boundary if state.paused_at == 0 else min(boundary, state.paused_at)


def reached_end(config: Config, now: int) -> bool:
    return config.end_time != 0 and now >= config.end_time


def observe(config: Config, state: State, at: int) -> State:
    """Independent earned-time oracle: no cursor, payout, or paused_at input."""

    eligible = state.eligible_active_seconds
    if state.phase == "Active":
        left, right = state.now, at
        if config.end_time != 0:
            left, right = min(left, config.end_time), min(right, config.end_time)
        eligible += max(0, right - left)
    return replace(state, now=at, eligible_active_seconds=eligible)


def account(
    config: Config, state: State, boundary: int, advance_cursor: bool
) -> tuple[State, int]:
    elapsed = max(0, boundary - state.cursor)
    moved = min(elapsed * config.rate, state.remaining_custody)
    intervals = state.paid_intervals
    if moved > 0 and boundary > state.cursor:
        intervals = (*intervals, (state.cursor, boundary))
    return (
        replace(
            state,
            cursor=boundary if advance_cursor else state.cursor,
            remaining_custody=state.remaining_custody - moved,
            recipient_accounted=state.recipient_accounted + moved,
            paid_intervals=intervals,
        ),
        moved,
    )


def terminalize(
    state: State, phase: str, boundary: int, clear_pause: bool
) -> tuple[State, int]:
    returned = state.remaining_custody
    return (
        replace(
            state,
            phase=phase,
            paused_at=0 if clear_pause else state.paused_at,
            remaining_custody=0,
            payer_returned=state.payer_returned + returned,
            terminal_boundary=boundary,
        ),
        returned,
    )


def reject(state: State) -> Outcome:
    return Outcome(state, 0, 0, False, None)


def apply_action(
    config: Config, state: State, action: Action, semantics: str
) -> Outcome:
    if action.at < state.now:
        raise AssertionError("ledger witnesses must be monotone")
    if semantics not in {"fixed", "paused_bug"}:
        raise AssertionError(f"unknown semantics {semantics}")

    seen = observe(config, state, action.at)
    if action.kind == "start":
        if (
            state.phase != "Created"
            or action.actor != "payer"
            or (config.end_time != 0 and action.at >= config.end_time)
        ):
            return reject(seen)
        return Outcome(replace(seen, phase="Active", cursor=action.at), 0, 0, True, None)

    if action.kind in AUTH_ACTIONS and action.actor != "payer":
        return reject(seen)
    if state.phase in TERMINAL:
        return Outcome(seen, 0, 0, action.kind in PUBLIC_SETTLEMENT, None)

    if action.kind == "pause":
        if state.phase != "Active":
            return reject(seen)
        if semantics == "fixed":
            boundary = accrual_bound(config, state, action.at)
            accounted, moved = account(config, seen, boundary, True)
            if reached_end(config, action.at):
                terminal, returned = terminalize(
                    accounted, "Ended", config.end_time, True
                )
                return Outcome(terminal, moved, returned, True, boundary)
            return Outcome(
                replace(accounted, phase="Paused", paused_at=boundary),
                moved,
                0,
                True,
                boundary,
            )
        # Reviewed defect: raw now-start_time, cursor unchanged, no end terminal.
        accounted, moved = account(config, seen, action.at, False)
        return Outcome(
            replace(accounted, phase="Paused", paused_at=action.at),
            moved,
            0,
            True,
            action.at,
        )

    if action.kind == "resume":
        if state.phase != "Paused":
            return reject(seen)
        if semantics == "fixed" and reached_end(config, action.at):
            terminal, returned = terminalize(seen, "Ended", config.end_time, True)
            return Outcome(terminal, 0, returned, True, None)
        # Reviewed defect allowed resume to reset the cursor after natural end.
        return Outcome(
            replace(seen, phase="Active", cursor=action.at, paused_at=0),
            0,
            0,
            True,
            None,
        )

    if state.phase not in {"Active", "Paused"} or action.kind not in VALUE_ACTIONS:
        return reject(seen)

    if semantics == "fixed":
        boundary = accrual_bound(config, state, action.at)
        advance_cursor = True
    else:
        # Old settle/batch/cancel kept the end cap but ignored paused_at.
        boundary = end_bound(config, action.at)
        advance_cursor = action.kind in PUBLIC_SETTLEMENT
    accounted, moved = account(config, seen, boundary, advance_cursor)

    if action.kind in PUBLIC_SETTLEMENT:
        if reached_end(config, action.at):
            terminal, returned = terminalize(
                accounted, "Ended", config.end_time, semantics == "fixed"
            )
            return Outcome(terminal, moved, returned, True, boundary)
        return Outcome(
            replace(accounted, phase=state.phase, paused_at=state.paused_at),
            moved,
            0,
            True,
            boundary,
        )

    natural = reached_end(config, action.at)
    terminal, returned = terminalize(
        accounted,
        "Ended" if natural else "Cancelled",
        config.end_time if natural else action.at,
        semantics == "fixed",
    )
    return Outcome(terminal, moved, returned, True, boundary)


def has_overlap(intervals: tuple[tuple[int, int], ...]) -> bool:
    for index, (left_start, left_end) in enumerate(intervals):
        for right_start, right_end in intervals[:index]:
            if max(left_start, right_start) < min(left_end, right_end):
                return True
    return False


def violations(
    config: Config,
    before: State,
    action: Action,
    outcome: Outcome,
    semantics: str,
) -> tuple[str, ...]:
    after = outcome.state
    found: set[str] = set()
    if has_overlap(after.paid_intervals):
        found.add("I1")
    if (
        config.end_time != 0
        and outcome.accrual_boundary is not None
        and outcome.accrual_boundary > config.end_time
    ):
        found.add("I2")

    total = after.recipient_accounted + after.payer_returned + after.remaining_custody
    if total != config.initial_balance or min(
        after.recipient_accounted,
        after.payer_returned,
        after.remaining_custody,
    ) < 0:
        found.add("I3")

    terminal_changed = before.phase in TERMINAL and contract_state(before) != contract_state(after)
    terminal_missing = (
        outcome.accepted
        and action.kind in (VALUE_ACTIONS | {"resume"})
        and before.phase in {"Active", "Paused"}
        and reached_end(config, action.at)
        and after.phase not in TERMINAL
    )
    if terminal_changed or terminal_missing:
        found.add("I4")
    auth_changed = (
        action.kind in AUTH_ACTIONS
        and action.actor != "payer"
        and (outcome.accepted or contract_state(before) != contract_state(after))
    )
    rejected_changed = not outcome.accepted and contract_state(before) != contract_state(after)
    if auth_changed or rejected_changed:
        found.add("I5")

    earned_cap = min(
        config.initial_balance, config.rate * after.eligible_active_seconds
    )
    if (
        outcome.accepted
        and action.kind in VALUE_ACTIONS
        and after.recipient_accounted != earned_cap
    ):
        found.add("I6")

    pause_incoherent = (
        (after.phase == "Paused" and (after.paused_at == 0 or after.cursor != after.paused_at))
        or (after.phase != "Paused" and after.paused_at != 0)
        or (after.phase in TERMINAL and after.remaining_custody != 0)
    )
    if pause_incoherent:
        found.add("I7")
    return tuple(sorted(found))


def available_actions(config: Config, state: State) -> tuple[Action, ...]:
    if state.phase == "Created":
        return (Action("start", 0),)
    actions: list[Action] = []
    for witness in config.graph_witnesses:
        if witness < state.now:
            continue
        if state.phase == "Active":
            actions.extend(
                (
                    Action("settle", witness, "recipient"),
                    Action("batch_settle", witness, "recipient"),
                    Action("pause", witness),
                    Action("cancel", witness),
                    Action("pause", witness, "recipient"),
                    Action("cancel", witness, "recipient"),
                )
            )
        elif state.phase == "Paused":
            actions.extend(
                (
                    Action("settle", witness, "recipient"),
                    Action("batch_settle", witness, "recipient"),
                    Action("resume", witness),
                    Action("cancel", witness),
                    Action("resume", witness, "recipient"),
                    Action("cancel", witness, "recipient"),
                )
            )
        else:
            actions.extend(
                (
                    Action("settle", witness, "recipient"),
                    Action("batch_settle", witness, "recipient"),
                    Action("cancel", witness),
                )
            )
    return tuple(actions)


def build_graph(config: Config, semantics: str) -> tuple[dict[str, object], int, int]:
    root = initial_state(config)
    queue: deque[tuple[State, int]] = deque([(root, 0)])
    seen = {root}
    states = {state_id(config, root): root}
    transitions: list[dict[str, object]] = []
    edge_number = 0

    while queue:
        current, depth = queue.popleft()
        if depth >= MAX_DEPTH:
            continue
        source = state_id(config, current)
        for action in available_actions(config, current):
            outcome = apply_action(config, current, action, semantics)
            target = state_id(config, outcome.state)
            states[target] = outcome.state
            edge_number += 1
            transitions.append(
                {
                    "id": f"step-{edge_number:05d}-{action.label}",
                    "source": source,
                    "target": target,
                    "requiresViolations": [],
                    "invariantId": None,
                    "boundary": None,
                    "impact": None,
                }
            )
            for invariant in violations(config, current, action, outcome, semantics):
                edge_number += 1
                transitions.append(
                    {
                        "id": f"violation-{edge_number:05d}-{action.label}-{invariant}",
                        "source": source,
                        "target": f"violation:{invariant}",
                        "requiresViolations": [],
                        "invariantId": invariant,
                        "boundary": "settlement-lifecycle",
                        "impact": INVARIANTS[invariant],
                    }
                )
            if outcome.state not in seen:
                seen.add(outcome.state)
                queue.append((outcome.state, depth + 1))

    capabilities = [
        {
            "id": identifier,
            "description": f"Concrete {config.id} state {identifier}",
            "forbidden": False,
        }
        for identifier in sorted(states)
    ]
    capabilities.extend(
        {
            "id": f"violation:{key}",
            "description": f"Forbidden {description}",
            "forbidden": True,
        }
        for key, description in INVARIANTS.items()
    )
    return (
        {
            "assumptions": [],
            "capabilities": capabilities,
            "transitions": transitions,
            "initialCapabilities": [state_id(config, root)],
            "targetCapabilities": [f"violation:{key}" for key in INVARIANTS],
            "violatedAssumptions": [],
            "maxDepth": MAX_DEPTH,
        },
        len(states),
        len(transitions),
    )


def search_invariants(config: Config, semantics: str) -> dict[str, object]:
    graph, state_count, transition_count = build_graph(config, semantics)
    results = {}
    for invariant, name in INVARIANTS.items():
        one = dict(graph)
        one["targetCapabilities"] = [f"violation:{invariant}"]
        result = run_reachability_model(reachability_model_from_dict(one))
        results[invariant] = {
            "name": name,
            "status": result["status"],
            "modelSha256": result["modelSha256"],
            "counterexample": result["path"],
        }
    return {
        "stateCount": state_count,
        "transitionCount": transition_count,
        "maxDepth": MAX_DEPTH,
        "invariants": results,
    }


def sequence(*actions: Action) -> tuple[Action, ...]:
    return (Action("start", 0), *actions)


def execute(config: Config, semantics: str, actions: tuple[Action, ...]):
    state = initial_state(config)
    outcomes: list[Outcome] = []
    found: set[str] = set()
    for action in actions:
        before = state
        outcome = apply_action(config, before, action, semantics)
        found.update(violations(config, before, action, outcome, semantics))
        outcomes.append(outcome)
        state = outcome.state
    return tuple(outcomes), state, tuple(sorted(found))


def summary(state: State) -> dict[str, object]:
    return {
        "phase": state.phase,
        "cursor": state.cursor,
        "pausedAt": state.paused_at,
        "remainingCustody": state.remaining_custody,
        "recipientAccounted": state.recipient_accounted,
        "payerReturned": state.payer_returned,
        "eligibleActiveSeconds": state.eligible_active_seconds,
        "terminalBoundary": state.terminal_boundary,
    }


def scenario_suite(semantics: str) -> dict[str, object]:
    bounded = CONFIGS["bounded"]
    unlimited = CONFIGS["unlimited"]
    small = CONFIGS["small_balance"]
    cases: dict[str, dict[str, object]] = {}

    def add(
        name: str,
        config: Config,
        actions: tuple[Action, ...],
        moves: tuple[int, ...],
        expected: dict[str, object],
        *,
        accepted: tuple[bool, ...] | None = None,
        required: bool = False,
    ) -> None:
        outcomes, final, found = execute(config, semantics, actions)
        actual_moves = tuple(item.moved_to_recipient for item in outcomes)
        actual_accepted = tuple(item.accepted for item in outcomes)
        final_summary = summary(final)
        expected_state = all(final_summary[key] == value for key, value in expected.items())
        expected_result = (
            actual_moves == moves
            and expected_state
            and (accepted is None or actual_accepted == accepted)
        )
        passed = expected_result and not found
        cases[name] = {
            "pass": passed,
            "expectedResultMatched": expected_result,
            "requiredPausedRegression": required,
            "actions": [item.label for item in actions],
            "accepted": list(actual_accepted),
            "recipientMoves": list(actual_moves),
            "payerReturns": [item.returned_to_payer for item in outcomes],
            "violations": list(found),
            "final": final_summary,
        }

    add(
        "R1_bounded_pause_after_natural_end",
        bounded,
        sequence(Action("pause", 11)),
        (0, 100),
        {
            "phase": "Ended", "cursor": 10, "pausedAt": 0,
            "recipientAccounted": 100, "payerReturned": 900,
            "remainingCustody": 0,
        },
        required=True,
    )
    add(
        "R2_pause_then_settle",
        bounded,
        sequence(Action("pause", 2), Action("settle", 3, "recipient")),
        (0, 20, 0),
        {
            "phase": "Paused", "cursor": 2, "pausedAt": 2,
            "recipientAccounted": 20, "payerReturned": 0,
            "remainingCustody": 980,
        },
        accepted=(True, True, True),
        required=True,
    )
    add(
        "R3_pause_then_cancel",
        bounded,
        sequence(Action("pause", 2), Action("cancel", 3)),
        (0, 20, 0),
        {
            "phase": "Cancelled", "pausedAt": 0,
            "recipientAccounted": 20, "payerReturned": 980,
            "remainingCustody": 0,
        },
        required=True,
    )
    add(
        "R4_pause_settle_cancel",
        bounded,
        sequence(
            Action("pause", 2),
            Action("settle", 3, "recipient"),
            Action("cancel", 4),
        ),
        (0, 20, 0, 0),
        {
            "phase": "Cancelled", "pausedAt": 0,
            "recipientAccounted": 20, "payerReturned": 980,
            "remainingCustody": 0,
        },
        required=True,
    )
    add(
        "R5_unlimited_pause_very_late_settle",
        unlimited,
        sequence(Action("pause", 2), Action("settle", 100, "recipient")),
        (0, 20, 0),
        {
            "phase": "Paused", "cursor": 2, "pausedAt": 2,
            "recipientAccounted": 20, "payerReturned": 0,
            "remainingCustody": 980,
        },
        accepted=(True, True, True),
        required=True,
    )
    add(
        "R6_pause_then_batch_settle",
        bounded,
        sequence(Action("pause", 2), Action("batch_settle", 3, "recipient")),
        (0, 20, 0),
        {
            "phase": "Paused", "cursor": 2, "pausedAt": 2,
            "recipientAccounted": 20, "remainingCustody": 980,
        },
        accepted=(True, True, True),
        required=True,
    )
    add(
        "R7_pause_resume_after_end_then_pause",
        bounded,
        sequence(Action("pause", 2), Action("resume", 11), Action("pause", 12)),
        (0, 20, 0, 0),
        {
            "phase": "Ended", "cursor": 2, "pausedAt": 0,
            "recipientAccounted": 20, "payerReturned": 980,
            "remainingCustody": 0,
        },
        accepted=(True, True, True, False),
        required=True,
    )
    add(
        "R8_pause_exactly_at_natural_end",
        bounded,
        sequence(Action("pause", 10)),
        (0, 100),
        {
            "phase": "Ended", "cursor": 10, "pausedAt": 0,
            "recipientAccounted": 100, "payerReturned": 900,
            "remainingCustody": 0,
        },
        required=True,
    )
    add(
        "R9_small_balance_high_rate_pause_after_end",
        small,
        sequence(Action("pause", 2)),
        (0, 10),
        {
            "phase": "Ended", "cursor": 1, "pausedAt": 0,
            "recipientAccounted": 10, "payerReturned": 5,
            "remainingCustody": 0,
        },
        required=True,
    )

    for name, at, phase, recipient, payer, custody, cursor in (
        ("C_active_end_minus_1", 9, "Active", 90, 0, 910, 9),
        ("C_active_end", 10, "Ended", 100, 900, 0, 10),
        ("C_active_end_plus_1", 11, "Ended", 100, 900, 0, 10),
        ("C_active_very_late", 100, "Ended", 100, 900, 0, 10),
    ):
        add(
            name,
            bounded,
            sequence(Action("settle", at, "recipient")),
            (0, recipient),
            {
                "phase": phase, "cursor": cursor,
                "recipientAccounted": recipient, "payerReturned": payer,
                "remainingCustody": custody,
            },
        )

    add(
        "C_settle_then_settle",
        bounded,
        sequence(
            Action("settle", 2, "recipient"),
            Action("settle", 4, "recipient"),
        ),
        (0, 20, 20),
        {
            "phase": "Active", "cursor": 4,
            "recipientAccounted": 40, "payerReturned": 0,
            "remainingCustody": 960,
        },
    )
    add(
        "C_settle_then_cancel",
        bounded,
        sequence(Action("settle", 2, "recipient"), Action("cancel", 4)),
        (0, 20, 20),
        {
            "phase": "Cancelled", "cursor": 4, "pausedAt": 0,
            "recipientAccounted": 40, "payerReturned": 960,
            "remainingCustody": 0,
        },
    )
    add(
        "C_cancel_then_settle",
        bounded,
        sequence(Action("cancel", 2), Action("settle", 4, "recipient")),
        (0, 20, 0),
        {
            "phase": "Cancelled", "recipientAccounted": 20,
            "payerReturned": 980, "remainingCustody": 0,
        },
        accepted=(True, True, True),
    )
    add(
        "C_unauthorized_pause_atomic",
        bounded,
        sequence(Action("pause", 2, "recipient")),
        (0, 0),
        {
            "phase": "Active", "cursor": 0, "pausedAt": 0,
            "recipientAccounted": 0, "payerReturned": 0,
            "remainingCustody": 1_000,
        },
        accepted=(True, False),
    )
    add(
        "C_unauthorized_cancel_atomic",
        bounded,
        sequence(Action("cancel", 2, "recipient")),
        (0, 0),
        {
            "phase": "Active", "cursor": 0,
            "recipientAccounted": 0, "payerReturned": 0,
            "remainingCustody": 1_000,
        },
        accepted=(True, False),
    )
    add(
        "C_permissionless_settle",
        bounded,
        sequence(Action("settle", 2, "recipient")),
        (0, 20),
        {
            "phase": "Active", "cursor": 2,
            "recipientAccounted": 20, "payerReturned": 0,
            "remainingCustody": 980,
        },
        accepted=(True, True),
    )

    passed = sum(1 for item in cases.values() if item["pass"])
    required = [
        name for name, item in cases.items() if item["requiredPausedRegression"]
    ]
    return {
        "count": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "requiredPausedRegressionCount": len(required),
        "requiredPausedRegressions": required,
        "cases": cases,
    }


def file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def run_git(repo: Path, *args: str, binary: bool = False):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=not binary,
    )


def git_text(repo: Path, *args: str) -> tuple[int, str]:
    result = run_git(repo, *args)
    return result.returncode, result.stdout.strip()


def repository_root(path: Path) -> Path | None:
    code, output = git_text(path, "rev-parse", "--show-toplevel")
    return Path(output).resolve() if code == 0 and output else None


def runtime_binding() -> dict[str, object]:
    """Bind the imported CGQA package to an exact, clean tagged checkout."""

    source = Path(contractgraph_qa.__file__).resolve()
    root = repository_root(source.parent)
    if root is None:
        return {
            "valid": False,
            "reason": "imported contractgraph_qa is not inside a git checkout",
        }

    try:
        relative_source = source.relative_to(root).as_posix()
    except ValueError:
        return {
            "valid": False,
            "reason": "imported contractgraph_qa source is outside resolved checkout",
        }

    head_code, head = git_text(root, "rev-parse", "HEAD")
    status_code, tracked_status = git_text(
        root, "status", "--porcelain=v1", "--untracked-files=no"
    )
    tag_code, tags = git_text(root, "tag", "--points-at", "HEAD")
    tracked_code, tracked_path = git_text(
        root, "ls-files", "--error-unmatch", relative_source
    )
    checks = {
        "versionMatches": __version__ == CGQA_VERSION,
        "headResolved": head_code == 0,
        "headMatches": head == CGQA_CORE_SHA,
        "trackedWorktreeClean": status_code == 0 and tracked_status == "",
        "tagPointsAtHead": tag_code == 0 and CGQA_TAG in tags.splitlines(),
        "importedSourceTracked": tracked_code == 0 and tracked_path == relative_source,
        "importedSourceExpected": relative_source == "contractgraph_qa/__init__.py",
    }
    return {
        "valid": all(checks.values()),
        "expectedVersion": CGQA_VERSION,
        "actualVersion": __version__,
        "expectedCoreCommit": CGQA_CORE_SHA,
        "actualCoreCommit": head if head_code == 0 else None,
        "expectedTag": CGQA_TAG,
        "importedSource": relative_source,
        "checks": checks,
    }


def commit_blob(root: Path, commit: str, relative_path: str) -> bytes | None:
    result = run_git(root, "show", f"{commit}:{relative_path}", binary=True)
    return result.stdout if result.returncode == 0 else None


def evidence_binding(requested_commit: str | None) -> dict[str, object]:
    """Bind a publishable result to HEAD and exact committed benchmark bytes."""

    verifier = Path(__file__).resolve()
    readme = verifier.with_name("README.md")
    root = repository_root(verifier.parent)
    verifier_hash = file_sha(verifier)
    readme_hash = file_sha(readme)
    if root is None:
        return {
            "mode": "committed" if requested_commit else "development-unbound",
            "valid": False,
            "reason": "verifier is not inside a git checkout",
            "verifierSha256": verifier_hash,
            "readmeSha256": readme_hash,
        }

    verifier_path = verifier.relative_to(root).as_posix()
    readme_path = readme.relative_to(root).as_posix()
    head_code, head = git_text(root, "rev-parse", "HEAD")
    status_code, scoped_status = git_text(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
        "--",
        verifier_path,
        readme_path,
    )
    scoped_clean = status_code == 0 and scoped_status == ""

    if requested_commit is None:
        return {
            "mode": "development-unbound",
            "valid": False,
            "requestedCommit": None,
            "actualHead": head if head_code == 0 else None,
            "scopedTrackedClean": scoped_clean,
            "declaredPathMatches": verifier_path == VERIFIER_PATH,
            "verifierPath": verifier_path,
            "verifierSha256": verifier_hash,
            "readmePath": readme_path,
            "readmeSha256": readme_hash,
            "note": "semantic replay only; no publishable evidence commit supplied",
        }

    verifier_blob = commit_blob(root, requested_commit, verifier_path)
    readme_blob = commit_blob(root, requested_commit, readme_path)
    verifier_match = (
        verifier_blob is not None and sha256(verifier_blob).hexdigest() == verifier_hash
    )
    readme_match = readme_blob is not None and sha256(readme_blob).hexdigest() == readme_hash
    checks = {
        "headResolved": head_code == 0,
        "requestedCommitIsHead": requested_commit == head,
        "scopedTrackedClean": scoped_clean,
        "declaredPathMatches": verifier_path == VERIFIER_PATH,
        "commitContainsExactVerifier": verifier_match,
        "commitContainsExactReadme": readme_match,
    }
    return {
        "mode": "committed",
        "valid": all(checks.values()),
        "requestedCommit": requested_commit,
        "actualHead": head if head_code == 0 else None,
        "verifierPath": verifier_path,
        "verifierSha256": verifier_hash,
        "readmePath": readme_path,
        "readmeSha256": readme_hash,
        "checks": checks,
    }


def valid_commit(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-commit",
        default=None,
        help=(
            "40-hex CGQA HEAD containing exact verifier/README bytes; omit only "
            "for an explicitly UNBOUND development replay"
        ),
    )
    args = parser.parse_args(argv)
    if args.evidence_commit is not None and not valid_commit(args.evidence_commit):
        parser.error("--evidence-commit must be exactly 40 lowercase hex characters")

    core_binding = runtime_binding()
    commit_binding = evidence_binding(args.evidence_commit)

    fixed_scenarios = scenario_suite("fixed")
    negative_scenarios = scenario_suite("paused_bug")
    fixed_searches = {
        name: search_invariants(config, "fixed")
        for name, config in CONFIGS.items()
    }
    negative_searches = {
        name: search_invariants(config, "paused_bug")
        for name, config in CONFIGS.items()
    }
    fixed_clear = all(
        item["status"] == "not_found_within_bound"
        for search in fixed_searches.values()
        for item in search["invariants"].values()
    )
    required_failures = {
        f"R{number}_" for number in range(1, 10)
    }
    failed_names = {
        name
        for name, item in negative_scenarios["cases"].items()
        if not item["pass"]
    }
    all_nine_killed = all(
        any(name.startswith(prefix) for name in failed_names)
        for prefix in required_failures
    )
    reachable_negative = {
        invariant
        for search in negative_searches.values()
        for invariant, item in search["invariants"].items()
        if item["status"] == "reachable"
    }
    negative_killed = (
        all_nine_killed
        and {"I1", "I2", "I4", "I6", "I7"} <= reachable_negative
    )
    semantic_pass = (
        fixed_scenarios["failed"] == 0
        and fixed_clear
        and negative_killed
    )
    publishable_pass = semantic_pass and core_binding["valid"] and commit_binding["valid"]
    if publishable_pass:
        bounded_verdict = "PASS"
    elif semantic_pass and core_binding["valid"] and args.evidence_commit is None:
        bounded_verdict = "UNBOUND"
    else:
        bounded_verdict = "FAIL"

    report = {
        "schemaVersion": "streampay-153-cgqa-oracle-v0.4",
        "targetBinding": {
            "repository": TARGET_REPOSITORY,
            "issue": TARGET_ISSUE,
            "pullRequest": TARGET_PR,
            "commit": TARGET_SHA,
        },
        "verifierIdentity": {
            "repository": "safal207/ContractGraph-QA",
            "declaredPath": VERIFIER_PATH,
            "evidenceBinding": commit_binding,
        },
        "runtimeIdentity": {
            "pythonImplementation": sys.implementation.name,
            "pythonVersion": ".".join(str(item) for item in sys.version_info[:3]),
            "coreBinding": core_binding,
        },
        "deterministicBounds": {
            "maxTransitionDepth": MAX_DEPTH,
            "randomness": "none",
            "seed": None,
            "stateDeduplication": "exact immutable State equality",
            "configurations": {
                name: asdict(config) for name, config in CONFIGS.items()
            },
        },
        "scope": {
            "states": ["Created", "Active", "Paused", "Cancelled", "Ended"],
            "actions": [
                "start", "pause", "resume", "settle", "batch_settle", "cancel"
            ],
            "accounting": [
                "recipient_accounted", "payer_returned", "remaining_custody",
                "eligible_active_seconds (independent oracle)",
            ],
            "invariants": INVARIANTS,
        },
        "fixedSemantics": {
            "scenarioChecks": fixed_scenarios,
            "reachability": fixed_searches,
        },
        "pausedDefectNegativeControl": {
            "description": (
                "Mutant uses raw now-start_time in pause, leaves cursor stale, "
                "ignores paused_at in settle/batch/cancel, retains stale pause "
                "state, and permits resume after natural end."
            ),
            "scenarioChecksAgainstFixedExpectations": negative_scenarios,
            "reachableInvariantViolations": sorted(reachable_negative),
            "killed": negative_killed,
            "reachability": negative_searches,
        },
        "semanticVerdict": "PASS" if semantic_pass else "FAIL",
        "boundedVerdict": bounded_verdict,
        "publishable": publishable_pass,
        "claimBoundary": (
            "PASS requires semantic success, an exact clean CGQA v1.8.0 core "
            "checkout, and exact verifier/README bytes committed at the supplied "
            "evidence HEAD. UNBOUND is development-only. Even PASS is exact only "
            "over the declared finite configurations, witnesses, actions, and "
            "depth; it is not a production proof. Native Rust tests at the exact "
            "target commit remain required for source-to-model binding."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not semantic_pass or not core_binding["valid"]:
        return 1
    if args.evidence_commit is not None and not commit_binding["valid"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
