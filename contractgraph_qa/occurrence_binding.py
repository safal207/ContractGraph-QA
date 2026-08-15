from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

RESOLVED_ALLOW = "RESOLVED_ALLOW"
RESOLVED_DENY = "RESOLVED_DENY"
OCCURRENCE_AMBIGUOUS = "OCCURRENCE_AMBIGUOUS"
OCCURRENCE_NOT_FOUND = "OCCURRENCE_NOT_FOUND"
CONSUMED = "CONSUMED"
ALREADY_CONSUMED = "ALREADY_CONSUMED"
NOT_AUTHORIZED = "NOT_AUTHORIZED"


@dataclass(frozen=True, slots=True)
class DecisionOccurrence:
    """One concrete occurrence of a semantic authorization decision."""

    event_id: str
    decision_ref: str
    verdict: str

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id must be non-empty")
        if not self.decision_ref:
            raise ValueError("decision_ref must be non-empty")
        if self.verdict not in {"ALLOW", "DENY"}:
            raise ValueError("verdict must be ALLOW or DENY")


@dataclass(frozen=True, slots=True)
class OccurrenceResolution:
    """Result of binding a semantic decision to one exact occurrence."""

    status: str
    occurrence: DecisionOccurrence | None = None


def resolve_occurrence(
    decision_ref: str,
    cites_event_id: str | None,
    events: Iterable[DecisionOccurrence],
) -> OccurrenceResolution:
    """Resolve one exact authorization occurrence, failing closed on ambiguity.

    A semantic ``decision_ref`` may name more than one concrete event. When that
    happens, callers must provide ``cites_event_id``. A collision without an
    exact event citation is therefore not an authorization.
    """

    candidates = [event for event in events if event.decision_ref == decision_ref]

    if cites_event_id is not None:
        candidates = [event for event in candidates if event.event_id == cites_event_id]

    if not candidates:
        return OccurrenceResolution(OCCURRENCE_NOT_FOUND)

    if len(candidates) > 1:
        return OccurrenceResolution(OCCURRENCE_AMBIGUOUS)

    occurrence = candidates[0]
    status = RESOLVED_ALLOW if occurrence.verdict == "ALLOW" else RESOLVED_DENY
    return OccurrenceResolution(status, occurrence)


def attempt_consume(
    resolution: OccurrenceResolution,
    consumed_event_ids: set[str],
) -> str:
    """Consume a resolved ALLOW exactly once while preserving causal identity.

    A synchronous caller may run resolution and consumption in one function or
    transaction, but ``RESOLVED_ALLOW`` and ``CONSUMED`` remain distinct facts.
    """

    if resolution.status != RESOLVED_ALLOW or resolution.occurrence is None:
        return NOT_AUTHORIZED

    event_id = resolution.occurrence.event_id
    if event_id in consumed_event_ids:
        return ALREADY_CONSUMED

    consumed_event_ids.add(event_id)
    return CONSUMED
