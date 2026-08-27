from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


CREWAI_SOURCE_REPOSITORY = "crewAIInc/crewAI"
CREWAI_SOURCE_COMMIT = "f4731f5025f861c78e3af0487cc80bf5e7c64782"
CREWAI_TOOL_EVENT_SOURCE = (
    "lib/crewai/src/crewai/events/types/tool_usage_events.py"
)
CREWAI_TOOLS_HANDLER_SOURCE = "lib/crewai/src/crewai/agents/tools_handler.py"

# Event classes present at the pinned upstream commit. This adapter intentionally
# models the current native vocabulary only; it does not invent an absence or
# deadline-observation event that CrewAI does not currently expose here.
CREWAI_NATIVE_TOOL_EVENT_TYPES = frozenset(
    {
        "tool_usage_started",
        "tool_usage_finished",
        "tool_usage_error",
        "tool_failure_detected",
        "tool_validate_input_error",
        "tool_selection_error",
        "tool_execution_error",
    }
)

Witness = Mapping[str, Any]
NativeEvent = dict[str, Any]


def canonical_witness_to_crewai_event(witness: Witness) -> NativeEvent | None:
    """Translate a conformance witness into the pinned CrewAI event vocabulary.

    ``absence`` deliberately returns ``None``. At the pinned source boundary,
    CrewAI exposes started/finished/error/failure tool lifecycle events but no
    native event whose semantics are "checked this time window and observed no
    response" together with the deadline used for that observation.
    """

    kind = witness.get("kind")
    if kind == "sent":
        return {
            "type": "tool_usage_started",
            "started_at": witness.get("at"),
        }
    if kind == "response":
        return {
            "type": "tool_usage_finished",
            "finished_at": witness.get("at"),
            "output": "response_observed",
        }
    if kind == "absence":
        return None
    raise ValueError(f"unsupported canonical witness kind: {kind!r}")


def project_crewai_tool_events(events: Sequence[Mapping[str, Any]]) -> str:
    """Reduce the native CrewAI tool-event vocabulary to a simple lifecycle state."""

    state = "pending"
    for event in events:
        event_type = event.get("type")
        if event_type not in CREWAI_NATIVE_TOOL_EVENT_TYPES:
            raise ValueError(f"unsupported CrewAI tool event type: {event_type!r}")

        if event_type == "tool_usage_started":
            state = "running"
        elif event_type == "tool_usage_finished":
            state = "finished"
        elif event_type in {
            "tool_usage_error",
            "tool_failure_detected",
            "tool_validate_input_error",
            "tool_selection_error",
            "tool_execution_error",
        }:
            state = "failed"
    return state


def project_pinned_crewai_tool_boundary(
    witnesses: Sequence[Witness], now: int | float | None = None
) -> str:
    """Adapter from the v0.1 conformance signature to current CrewAI events.

    ``now`` is accepted only because the conformance API deliberately exposes it
    as a probe. The adapter does not use ambient time.

    This is a capability benchmark, not a claim that CrewAI currently defines a
    witness-projection reducer. The current ``ToolsHandler`` is a post-use
    callback/cache handler, while the tool event vocabulary is observational.
    We therefore test the closest native evidence substrate without adding
    semantics that are absent from the pinned upstream source.
    """

    del now
    native_events: list[NativeEvent] = []
    for witness in witnesses:
        event = canonical_witness_to_crewai_event(witness)
        if event is not None:
            native_events.append(event)
    return project_crewai_tool_events(native_events)
