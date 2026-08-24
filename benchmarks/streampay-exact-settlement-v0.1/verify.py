#!/usr/bin/env python3
"""Bounded ContractGraph-QA oracle for StreamPay issue #153.

This is an external verification harness. It does not import into or modify the
StreamPay contract. The model is intentionally limited to the issue's bounded
Created -> Active -> Cancelled/Ended lifecycle and three timestamp witnesses.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import json

from contractgraph_qa import __version__
from contractgraph_qa.lifecycle_liveness import (
    lifecycle_liveness_model_from_dict,
    run_lifecycle_liveness_model,
)
from contractgraph_qa.reachability import (
    reachability_model_from_dict,
    run_reachability_model,
)


RATE = 10
INITIAL_BALANCE = 1_000
END_TIME = 10
WITNESSES = (END_TIME - 1, END_TIME, END_TIME + 1)
MAX_DEPTH = 4
INVARIANTS = {
    "I1": "once-only settlement",
    "I2": "end-time cap",
    "I3": "value conservation",
    "I4": "terminal immutability",
    "I5": "determinism",
    "I6": "payer-only cancellation authorization",
}
TERMINAL_PHASES = frozenset({"Cancelled", "Ended"})


@dataclass(frozen=True, slots=True)
class State:
    phase: str
    now: int
    cursor: int
    remaining: int
    cumulative: int
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
    moved: int
    accepted: bool
    settlement_time: int | None


INITIAL_STATE = State(
    phase="Created",
    now=0,
    cursor=0,
    remaining=INITIAL_BALANCE,
    cumulative=0,
)


def economic_state(state: State) -> tuple[object, ...]:
    return (
        state.phase,
        state.cursor,
        state.remaining,
        state.cumulative,
        state.terminal_boundary,
        state.paid_intervals,
    )


def state_id(state: State) -> str:
    intervals = ",".join(f"{start}-{end}" for start, end in state.paid_intervals) or "none"
    boundary = "none" if state.terminal_boundary is None else str(state.terminal_boundary)
    return (
        f"{state.phase}|now={state.now}|cursor={state.cursor}|remaining={state.remaining}"
        f"|settled={state.cumulative}|boundary={boundary}|intervals={intervals}"
    )


def _settle_value(state: State, settlement_time: int) -> tuple[int, tuple[tuple[int, int], ...]]:
    elapsed = max(0, settlement_time - state.cursor)
    moved = min(elapsed * RATE, state.remaining)
    intervals = state.paid_intervals
    if moved > 0:
        intervals = (*intervals, (state.cursor, settlement_time))
    return moved, intervals


def apply_action(state: State, action: Action, semantics: str) -> Outcome:
    if action.at < state.now:
        raise AssertionError("ledger witnesses must be monotone")

    observed = replace(state, now=action.at)

    if action.kind == "start":
        if state.phase != "Created" or action.actor != "payer" or action.at >= END_TIME:
            return Outcome(observed, 0, False, None)
        return Outcome(replace(observed, phase="Active", cursor=action.at), 0, True, None)

    if action.kind == "cancel" and action.actor != "payer":
        return Outcome(observed, 0, False, None)

    if state.phase in TERMINAL_PHASES:
        return Outcome(observed, 0, action.kind == "settle", None)

    if state.phase != "Active" or action.kind not in {"settle", "cancel"}:
        return Outcome(observed, 0, False, None)

    settlement_time = min(action.at, END_TIME) if semantics == "fixed" else action.at
    moved, intervals = _settle_value(state, settlement_time)
    remaining = state.remaining - moved
    cumulative = state.cumulative + moved

    if action.kind == "settle":
        reached_end = semantics == "fixed" and settlement_time == END_TIME
        return Outcome(
            State(
                phase="Ended" if reached_end else "Active",
                now=action.at,
                cursor=settlement_time,
                remaining=remaining,
                cumulative=cumulative,
                terminal_boundary=END_TIME if reached_end else None,
                paid_intervals=intervals,
            ),
            moved,
            True,
            settlement_time,
        )

    natural_end_wins = semantics == "fixed" and action.at >= END_TIME
    return Outcome(
        State(
            phase="Ended" if natural_end_wins else "Cancelled",
            now=action.at,
            cursor=state.cursor,
            remaining=remaining,
            cumulative=cumulative,
            terminal_boundary=settlement_time,
            paid_intervals=intervals,
        ),
        moved,
        True,
        settlement_time,
    )


def _has_overlap(intervals: tuple[tuple[int, int], ...]) -> bool:
    for index, (left_start, left_end) in enumerate(intervals):
        for right_start, right_end in intervals[:index]:
            if max(left_start, right_start) < min(left_end, right_end):
                return True
    return False


def transition_violations(
    before: State,
    action: Action,
    outcome: Outcome,
    semantics: str,
) -> tuple[str, ...]:
    after = outcome.state
    violations: list[str] = []

    if _has_overlap(after.paid_intervals):
        violations.append("I1")

    if outcome.settlement_time is not None and outcome.settlement_time > END_TIME:
        violations.append("I2")

    if after.cumulative + after.remaining != INITIAL_BALANCE:
        violations.append("I3")

    natural_terminal_missing = (
        outcome.accepted
        and action.kind in {"settle", "cancel"}
        and after.phase == "Active"
        and after.now >= END_TIME
    )
    terminal_value_changed = (
        before.phase in TERMINAL_PHASES
        and economic_state(before) != economic_state(after)
    )
    if natural_terminal_missing or terminal_value_changed:
        violations.append("I4")

    if outcome != apply_action(before, action, semantics):
        violations.append("I5")

    unauthorized_cancel_changed_state = (
        action.kind == "cancel"
        and action.actor != "payer"
        and (outcome.accepted or economic_state(before) != economic_state(after))
    )
    if unauthorized_cancel_changed_state:
        violations.append("I6")

    return tuple(sorted(set(violations)))


def available_actions(state: State) -> tuple[Action, ...]:
    if state.phase == "Created":
        return (Action("start", 0),)
    actions: list[Action] = []
    for witness in WITNESSES:
        if witness < state.now:
            continue
        actions.extend(
            (
                Action("settle", witness),
                Action("cancel", witness, "payer"),
                Action("cancel", witness, "recipient"),
            )
        )
    return tuple(actions)


def build_reachability_graph(semantics: str) -> tuple[dict[str, object], int, int]:
    queue: deque[tuple[State, int]] = deque([(INITIAL_STATE, 0)])
    seen = {INITIAL_STATE}
    states = {state_id(INITIAL_STATE): INITIAL_STATE}
    transitions: list[dict[str, object]] = []
    edge_number = 0

    while queue:
        current, depth = queue.popleft()
        if depth >= MAX_DEPTH:
            continue
        source = state_id(current)
        for action in available_actions(current):
            outcome = apply_action(current, action, semantics)
            target = state_id(outcome.state)
            states[target] = outcome.state
            edge_number += 1
            transitions.append(
                {
                    "id": f"step-{edge_number:04d}-{action.label}",
                    "source": source,
                    "target": target,
                    "requiresViolations": [],
                    "invariantId": None,
                    "boundary": None,
                    "impact": None,
                }
            )

            for invariant in transition_violations(current, action, outcome, semantics):
                edge_number += 1
                transitions.append(
                    {
                        "id": f"violation-{edge_number:04d}-{action.label}-{invariant}",
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
            "description": f"Concrete bounded state {identifier}",
            "forbidden": False,
        }
        for identifier in sorted(states)
    ]
    capabilities.extend(
        {
            "id": f"violation:{invariant}",
            "description": f"Forbidden {description} violation",
            "forbidden": True,
        }
        for invariant, description in INVARIANTS.items()
    )

    graph = {
        "assumptions": [],
        "capabilities": capabilities,
        "transitions": transitions,
        "initialCapabilities": [state_id(INITIAL_STATE)],
        "targetCapabilities": [f"violation:{key}" for key in INVARIANTS],
        "violatedAssumptions": [],
        "maxDepth": MAX_DEPTH,
    }
    return graph, len(states), len(transitions)


def run_invariant_searches(semantics: str) -> dict[str, object]:
    graph, state_count, transition_count = build_reachability_graph(semantics)
    results: dict[str, object] = {}
    for invariant in INVARIANTS:
        single_target = dict(graph)
        single_target["targetCapabilities"] = [f"violation:{invariant}"]
        result = run_reachability_model(reachability_model_from_dict(single_target))
        results[invariant] = {
            "name": INVARIANTS[invariant],
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


def started_state(semantics: str) -> State:
    return apply_action(INITIAL_STATE, Action("start", 0), semantics).state


def boundary_checks(semantics: str) -> dict[str, bool]:
    active = started_state(semantics)

    before = apply_action(active, Action("settle", END_TIME - 1), semantics)
    exact_after_before = apply_action(before.state, Action("settle", END_TIME), semantics)
    after = apply_action(active, Action("settle", END_TIME + 1), semantics)
    settle_repeat = apply_action(after.state, Action("settle", END_TIME + 1), semantics)

    cancel_before = apply_action(active, Action("cancel", END_TIME - 1), semantics)
    cancel_exact = apply_action(active, Action("cancel", END_TIME), semantics)
    cancel_after = apply_action(active, Action("cancel", END_TIME + 1), semantics)
    cancel_repeat = apply_action(
        cancel_after.state,
        Action("cancel", END_TIME + 1),
        semantics,
    )
    settle_after_cancel = apply_action(
        cancel_after.state,
        Action("settle", END_TIME + 1),
        semantics,
    )
    unauthorized = apply_action(
        active,
        Action("cancel", END_TIME - 1, "recipient"),
        semantics,
    )
    legacy = State(
        phase="Active",
        now=END_TIME + 1,
        cursor=END_TIME + 1,
        remaining=890,
        cumulative=110,
        paid_intervals=((0, END_TIME + 1),),
    )
    legacy_settle = apply_action(legacy, Action("settle", END_TIME + 2), semantics)
    legacy_cancel = apply_action(legacy, Action("cancel", END_TIME + 2), semantics)

    return {
        "A_settle_before": (
            before.moved == 90
            and before.state.phase == "Active"
            and before.state.remaining == 910
        ),
        "B_settle_exact": (
            exact_after_before.moved == 10
            and exact_after_before.state.phase == "Ended"
            and exact_after_before.state.remaining == 900
        ),
        "C_settle_after_and_repeat": (
            after.moved == 100
            and after.state.phase == "Ended"
            and after.state.terminal_boundary == END_TIME
            and settle_repeat.moved == 0
            and economic_state(settle_repeat.state) == economic_state(after.state)
        ),
        "D_cancel_before": (
            cancel_before.moved == 90
            and cancel_before.state.phase == "Cancelled"
            and cancel_before.state.terminal_boundary == END_TIME - 1
            and cancel_before.state.remaining == 910
        ),
        "E_cancel_exact": (
            cancel_exact.moved == 100
            and cancel_exact.state.phase == "Ended"
            and cancel_exact.state.terminal_boundary == END_TIME
            and cancel_exact.state.remaining == 900
        ),
        "F_cancel_after_and_repeats": (
            cancel_after.moved == 100
            and cancel_after.state.phase == "Ended"
            and cancel_after.state.terminal_boundary == END_TIME
            and cancel_repeat.moved == 0
            and not cancel_repeat.accepted
            and settle_after_cancel.moved == 0
            and economic_state(cancel_repeat.state) == economic_state(cancel_after.state)
            and economic_state(settle_after_cancel.state) == economic_state(cancel_after.state)
        ),
        "G_payer_only": (
            not unauthorized.accepted
            and unauthorized.moved == 0
            and economic_state(unauthorized.state) == economic_state(active)
        ),
        "H_conservation_all_scenarios": all(
            outcome.state.cumulative + outcome.state.remaining == INITIAL_BALANCE
            for outcome in (
                before,
                exact_after_before,
                after,
                settle_repeat,
                cancel_before,
                cancel_exact,
                cancel_after,
                cancel_repeat,
                settle_after_cancel,
                unauthorized,
            )
        ),
        "Additional_legacy_cursor_compatibility": (
            legacy_settle.moved == 0
            and legacy_settle.state.phase == "Ended"
            and legacy_settle.state.remaining == 890
            and legacy_cancel.moved == 0
            and legacy_cancel.state.phase == "Ended"
            and legacy_cancel.state.remaining == 890
        ),
    }


def lifecycle_result() -> dict[str, object]:
    model = lifecycle_liveness_model_from_dict(
        {
            "states": [
                {
                    "id": "Created",
                    "description": "Configured stream value awaits activation.",
                    "holdsValue": True,
                    "safeTerminal": False,
                },
                {
                    "id": "Active",
                    "description": "Value accrues under the configured temporal boundary.",
                    "holdsValue": True,
                    "safeTerminal": False,
                },
                {
                    "id": "Cancelled",
                    "description": "Accrued and remaining value are terminally allocated at cancellation.",
                    "holdsValue": False,
                    "safeTerminal": True,
                },
                {
                    "id": "Ended",
                    "description": "Accrued and remaining value are terminally allocated at natural end.",
                    "holdsValue": False,
                    "safeTerminal": True,
                },
            ],
            "transitions": [
                {"id": "start", "source": "Created", "target": "Active"},
                {"id": "cancel-before-end", "source": "Active", "target": "Cancelled"},
                {"id": "settle-at-or-after-end", "source": "Active", "target": "Ended"},
                {"id": "cancel-at-or-after-end", "source": "Active", "target": "Ended"},
                {"id": "settle-ended-noop", "source": "Ended", "target": "Ended"},
                {"id": "cancel-ended-rejected", "source": "Ended", "target": "Ended"},
                {"id": "settle-cancelled-noop", "source": "Cancelled", "target": "Cancelled"},
                {"id": "cancel-cancelled-rejected", "source": "Cancelled", "target": "Cancelled"},
            ],
            "initialState": "Created",
            "invariantId": "STREAMPAY-153-TERMINAL-LIVENESS",
        }
    )
    return run_lifecycle_liveness_model(model)


def main() -> int:
    fixed_boundaries = boundary_checks("fixed")
    baseline_boundaries = boundary_checks("baseline")
    fixed_search = run_invariant_searches("fixed")
    baseline_search = run_invariant_searches("baseline")
    liveness = lifecycle_result()

    fixed_invariants_clear = all(
        item["status"] == "not_found_within_bound"
        for item in fixed_search["invariants"].values()
    )
    negative_control_killed = (
        baseline_search["invariants"]["I2"]["status"] == "reachable"
        and baseline_search["invariants"]["I4"]["status"] == "reachable"
        and not all(baseline_boundaries.values())
    )
    bounded_pass = (
        liveness["status"] == "pass"
        and all(fixed_boundaries.values())
        and fixed_invariants_clear
        and negative_control_killed
    )

    report = {
        "schemaVersion": "streampay-153-cgqa-oracle-v0.1",
        "contractGraphQa": {
            "repository": "safal207/ContractGraph-QA",
            "version": __version__,
        },
        "scope": {
            "states": ["Created", "Active", "Cancelled", "Ended"],
            "witnesses": {
                "T_before": END_TIME - 1,
                "T_exact": END_TIME,
                "T_after": END_TIME + 1,
            },
            "rate": RATE,
            "initialBalance": INITIAL_BALANCE,
            "configuredEndTime": END_TIME,
        },
        "lifecycleLiveness": liveness,
        "fixedSemantics": {
            "boundaryChecks": fixed_boundaries,
            "reachability": fixed_search,
        },
        "preFixSemanticsNegativeControl": {
            "boundaryChecks": baseline_boundaries,
            "reachability": baseline_search,
        },
        "boundedVerdict": "PASS" if bounded_pass else "FAIL",
        "scopeNote": (
            "Exact over the declared finite model and three timestamp witnesses. "
            "Native Rust tests remain the source-to-implementation binding; this "
            "oracle is not an exhaustive proof of all StreamPay features."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if bounded_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
