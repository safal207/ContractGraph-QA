from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class WitnessProjectionError(ValueError):
    """Raised when a witness log is insufficient or malformed for projection."""


Witness = Mapping[str, Any]


def project_witnesses(witnesses: Sequence[Witness], now: int | float | None = None) -> str:
    """Project an outcome from an append-only witness sequence.

    ``now`` is accepted deliberately as a conformance probe. A conformant
    projection must not use ambient wall-clock time: identical witnesses must
    produce identical outcomes regardless of when replay occurs.

    Time-dependent transitions are enabled only by explicit witnesses. In
    particular, an ``absence`` witness must carry the deadline it evaluated;
    the projection never reads deadline configuration from ambient state.
    """

    del now  # Explicitly unreachable to the projection logic.

    state = "pending"
    for witness in witnesses:
        kind = witness.get("kind")

        if kind == "sent":
            _require_number(witness, "at", kind)
            _require_number(witness, "deadline", kind)
            state = "awaiting_response"
            continue

        if kind == "response":
            _require_number(witness, "at", kind)
            state = "accepted"
            continue

        if kind == "absence":
            if state != "awaiting_response":
                continue
            if witness.get("result") != "no_response":
                raise WitnessProjectionError(
                    "absence witness must carry result='no_response'"
                )
            deadline = _require_number(witness, "deadline", kind)
            window = witness.get("window")
            if not isinstance(window, (list, tuple)) or len(window) != 2:
                raise WitnessProjectionError(
                    "absence witness must carry a two-element window"
                )
            start = _coerce_number(window[0], "absence.window[0]")
            end = _coerce_number(window[1], "absence.window[1]")
            _require_number(witness, "checked_at", kind)
            if end < start:
                raise WitnessProjectionError(
                    "absence witness window end must be >= window start"
                )
            state = "expired" if end >= deadline else "stale"
            continue

        raise WitnessProjectionError(f"unsupported witness kind: {kind!r}")

    return state


def _require_number(witness: Witness, field: str, kind: str) -> int | float:
    if field not in witness:
        raise WitnessProjectionError(
            f"{kind} witness must carry {field}; ambient configuration is not evidence"
        )
    return _coerce_number(witness[field], f"{kind}.{field}")


def _coerce_number(value: Any, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WitnessProjectionError(f"{field} must be numeric")
    return value
