from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

AUTOGEN_SOURCE_REPOSITORY = "microsoft/autogen"
AUTOGEN_SOURCE_COMMIT = "027ecf0a379bcc1d09956d46d12d44a3ad9cee14"
AUTOGEN_AGENT_PROTOCOL_SOURCE = (
    "python/packages/autogen-core/src/autogen_core/_agent.py"
)
AUTOGEN_CHAT_CONTEXT_SOURCE = (
    "python/packages/autogen-core/src/autogen_core/model_context/_chat_completion_context.py"
)
AUTOGEN_ASSISTANT_AGENT_SOURCE = (
    "python/packages/autogen-agentchat/src/autogen_agentchat/agents/_assistant_agent.py"
)

Witness = Mapping[str, Any]


def save_witness_state(witnesses: Sequence[Witness]) -> dict[str, Any]:
    """Model an AutoGen-compatible JSON-serializable agent state payload.

    AutoGen's Agent protocol exposes save_state/load_state as JSON-serializable
    mappings. The hosted adapter stores the append-only witness log as one state
    field and intentionally stores no derived status or evaluator clock value.
    """

    payload = {"witnesses": [copy.deepcopy(dict(witness)) for witness in witnesses]}
    # Exercise the JSON-serializable contract rather than relying on Python
    # object identity. Tuples (for example witness windows) normalize to arrays.
    return json.loads(json.dumps(payload, sort_keys=True))


def load_witness_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Restore a witness log from an AutoGen-compatible state mapping."""

    raw = state.get("witnesses", [])
    if not isinstance(raw, list):
        raise ValueError("AutoGen hosted witness state must contain a list")

    restored: list[dict[str, Any]] = []
    for witness in raw:
        if not isinstance(witness, dict):
            raise ValueError("each restored witness must be a mapping")
        restored.append(copy.deepcopy(witness))
    return restored


def project_saved_autogen_state(
    witnesses: Sequence[Witness], now: int | float | None = None
) -> str:
    """Run the frozen witness projection after a save/load round trip.

    ``now`` is accepted only as the conformance probe. The projection never
    consults it. Time-dependent facts must already be represented by witnesses.

    This benchmark does not claim AutoGen natively defines these domain states;
    it measures whether its explicit save/load state boundary can host the
    frozen contract without semantic loss.
    """

    del now
    restored = load_witness_state(save_witness_state(witnesses))

    state = "pending"
    for witness in restored:
        kind = witness.get("kind")
        if kind == "sent":
            state = "awaiting_response"
            continue

        if kind == "absence":
            deadline = witness.get("deadline")
            checked_at = witness.get("checked_at")
            if deadline is None or checked_at is None:
                # Fail closed: an incomplete absence observation cannot create
                # an expiry fact.
                continue
            if witness.get("result") == "no_response" and checked_at >= deadline:
                state = "expired"
            continue

        if kind == "response":
            state = "accepted"
            continue

        raise ValueError(f"unsupported witness kind: {kind!r}")

    return state
