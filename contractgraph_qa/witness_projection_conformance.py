from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

Witness = Mapping[str, Any]
Projection = Callable[[Sequence[Witness], int | float | None], Any]

SPEC_ID = "witness-projection-conformance/v0.1"

T0, T1, T2, DEADLINE = 1000, 2000, 3000, 2500
SENT: dict[str, Any] = {"kind": "sent", "at": T0, "deadline": DEADLINE}
ABSENCE_BEFORE_DEADLINE: dict[str, Any] = {
    "kind": "absence",
    "checked_at": T1,
    "window": (T0, T1),
    "deadline": DEADLINE,
    "result": "no_response",
}
ABSENCE_AFTER_DEADLINE: dict[str, Any] = {
    "kind": "absence",
    "checked_at": T2,
    "window": (T0, T2),
    "deadline": DEADLINE,
    "result": "no_response",
}
RESPONSE: dict[str, Any] = {"kind": "response", "at": T1}


@dataclass(frozen=True)
class ConformanceCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ConformanceReport:
    spec: str
    conformant: bool
    checks: tuple[ConformanceCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec": self.spec,
            "conformant": self.conformant,
            "checks": [asdict(check) for check in self.checks],
        }


def run_witness_projection_conformance(projection: Projection) -> ConformanceReport:
    """Run the v0.1 witness-projection contract against a projection callable.

    The callable must expose ``projection(witnesses, now)``. The canonical
    fixtures intentionally pass ``now`` even though a conformant replayable
    projection must not let ambient evaluator time change its result.

    Framework-specific systems can satisfy this signature with a thin adapter
    that translates the canonical ``sent``/``absence``/``response`` witnesses
    into their native representation before calling their reducer.
    """

    checks = (
        _deterministic_across_evaluator_time(projection),
        _explicit_absence_required(projection),
        _replay_stable(projection),
        _prefix_stable(projection),
        _non_monotone_state_over_monotone_evidence(projection),
        _deadline_is_evidence(projection),
        _missing_deadline_fails_closed(projection),
        _projection_does_not_mutate_evidence(projection),
    )
    return ConformanceReport(
        spec=SPEC_ID,
        conformant=all(check.passed for check in checks),
        checks=checks,
    )


def _call(projection: Projection, witnesses: Sequence[Witness], now: int | float) -> Any:
    return projection(witnesses, now)


def _deterministic_across_evaluator_time(projection: Projection) -> ConformanceCheck:
    try:
        early = _call(projection, [copy.deepcopy(SENT)], T1)
        late = _call(projection, [copy.deepcopy(SENT)], T2 + 10_000)
        passed = early == late
        detail = f"early={early!r}, late={late!r}"
    except Exception as exc:  # pragma: no cover - exercised by external adapters
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("deterministic_across_evaluator_time", passed, detail)


def _explicit_absence_required(projection: Projection) -> ConformanceCheck:
    try:
        without_absence = _call(projection, [copy.deepcopy(SENT)], T2 + 10_000)
        with_absence = _call(
            projection,
            [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)],
            T2 + 10_000,
        )
        passed = without_absence != with_absence
        detail = f"without_absence={without_absence!r}, with_absence={with_absence!r}"
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("explicit_absence_enables_transition", passed, detail)


def _replay_stable(projection: Projection) -> ConformanceCheck:
    witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
    try:
        outcomes = tuple(
            _call(projection, copy.deepcopy(witnesses), now)
            for now in (T2, T2 + 1, T2 + 86_400, T2 + 10**9)
        )
        passed = len(set(map(repr, outcomes))) == 1
        detail = f"outcomes={outcomes!r}"
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("replay_stability", passed, detail)


def _prefix_stable(projection: Projection) -> ConformanceCheck:
    base = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
    extended = base + [copy.deepcopy(RESPONSE)]
    try:
        before = tuple(
            _call(projection, copy.deepcopy(base[:i]), T2)
            for i in range(len(base) + 1)
        )
        after = tuple(
            _call(projection, copy.deepcopy(extended[:i]), T2)
            for i in range(len(base) + 1)
        )
        passed = before == after
        detail = f"before={before!r}, after={after!r}"
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("prefix_stability", passed, detail)


def _non_monotone_state_over_monotone_evidence(projection: Projection) -> ConformanceCheck:
    try:
        expired_or_stale = _call(
            projection,
            [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)],
            T2,
        )
        recovered = _call(
            projection,
            [
                copy.deepcopy(SENT),
                copy.deepcopy(ABSENCE_AFTER_DEADLINE),
                copy.deepcopy(RESPONSE),
            ],
            T2,
        )
        direct_response = _call(
            projection,
            [copy.deepcopy(SENT), copy.deepcopy(RESPONSE)],
            T2,
        )
        passed = expired_or_stale != recovered and recovered == direct_response
        detail = (
            f"pre_response={expired_or_stale!r}, recovered={recovered!r}, "
            f"direct_response={direct_response!r}"
        )
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck(
        "non_monotone_state_over_monotone_evidence", passed, detail
    )


def _deadline_is_evidence(projection: Projection) -> ConformanceCheck:
    try:
        before = _call(
            projection,
            [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_BEFORE_DEADLINE)],
            T2,
        )
        after = _call(
            projection,
            [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)],
            T2,
        )
        passed = before != after
        detail = f"before_deadline={before!r}, after_deadline={after!r}"
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("deadline_bound_to_evidence", passed, detail)


def _missing_deadline_fails_closed(projection: Projection) -> ConformanceCheck:
    baseline_witnesses = [copy.deepcopy(SENT)]
    missing_deadline = copy.deepcopy(ABSENCE_AFTER_DEADLINE)
    del missing_deadline["deadline"]
    try:
        baseline = _call(projection, baseline_witnesses, T2)
        try:
            result = _call(
                projection,
                [copy.deepcopy(SENT), missing_deadline],
                T2,
            )
        except Exception as exc:
            return ConformanceCheck(
                "missing_deadline_fails_closed",
                True,
                f"rejected missing deadline with {type(exc).__name__}: {exc}",
            )
        passed = result == baseline
        detail = f"baseline={baseline!r}, missing_deadline_result={result!r}"
    except Exception as exc:
        passed = False
        detail = f"baseline projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("missing_deadline_fails_closed", passed, detail)


def _projection_does_not_mutate_evidence(projection: Projection) -> ConformanceCheck:
    witnesses = [copy.deepcopy(SENT), copy.deepcopy(ABSENCE_AFTER_DEADLINE)]
    before = copy.deepcopy(witnesses)
    try:
        _call(projection, witnesses, T2)
        passed = witnesses == before
        detail = "witness sequence unchanged" if passed else "projection mutated witnesses"
    except Exception as exc:
        passed = False
        detail = f"projection raised {type(exc).__name__}: {exc}"
    return ConformanceCheck("projection_does_not_mutate_evidence", passed, detail)
