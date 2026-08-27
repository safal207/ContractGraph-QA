from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from contractgraph_qa.witness_projection import project_witnesses

LANGGRAPH_SOURCE_REPOSITORY = "langchain-ai/langgraph"
LANGGRAPH_SOURCE_COMMIT = "f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f"
LANGGRAPH_STATEGRAPH_SOURCE = "libs/langgraph/langgraph/graph/state.py"
LANGGRAPH_CHECKPOINT_SOURCE = "libs/checkpoint/langgraph/checkpoint/base/__init__.py"

Witness = Mapping[str, Any]


def append_witnesses(
    current: Sequence[Witness] | None,
    update: Sequence[Witness] | Witness | None,
) -> list[dict[str, Any]]:
    """LangGraph-compatible reducer for an append-only witness state key.

    ``StateGraph`` reducers use the signature ``(Value, Value) -> Value``.
    This reducer accepts either one witness or a sequence of witnesses as the
    incoming update and always returns a fresh list so earlier evidence is not
    mutated in place.
    """

    result = [copy.deepcopy(dict(item)) for item in (current or [])]
    if update is None:
        return result

    if isinstance(update, Mapping):
        result.append(copy.deepcopy(dict(update)))
        return result

    result.extend(copy.deepcopy(dict(item)) for item in update)
    return result


def checkpoint_witness_state(witnesses: Sequence[Witness]) -> dict[str, Any]:
    """Create the minimal LangGraph checkpoint shape needed by this benchmark.

    At the pinned upstream source, ``Checkpoint`` stores user state snapshots in
    ``channel_values``. The benchmark intentionally models only that documented
    representability boundary; it does not pretend to run LangGraph internals.
    """

    return {
        "channel_values": {
            "witnesses": [copy.deepcopy(dict(item)) for item in witnesses]
        }
    }


def restore_witnesses_from_checkpoint(checkpoint: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Restore the append-only witness state from a checkpoint snapshot."""

    channel_values = checkpoint.get("channel_values")
    if not isinstance(channel_values, Mapping):
        raise ValueError("checkpoint must contain channel_values")

    witnesses = channel_values.get("witnesses")
    if not isinstance(witnesses, list):
        raise ValueError("checkpoint channel_values must contain witnesses list")

    return [copy.deepcopy(dict(item)) for item in witnesses]


def project_langgraph_hosted_boundary(
    witnesses: Sequence[Witness], now: int | float | None = None
) -> str:
    """Run v0.1 projection through a LangGraph-shaped hosted state boundary.

    This is deliberately a *hosted adapter* benchmark. LangGraph does not define
    the domain-specific ``sent``/``absence``/``response`` reducer. Instead, the
    pinned ``StateGraph`` API supports user reducers and checkpoints preserve
    state in ``channel_values``. We model that thin integration path, then apply
    the frozen ContractGraph-QA projection to the restored witness bytes.

    Passing this adapter therefore means "LangGraph can host the conformance
    contract without hidden wall-clock reads", not "LangGraph natively defines
    Witness Projection Conformance v0.1".
    """

    state: list[dict[str, Any]] = []
    for witness in witnesses:
        state = append_witnesses(state, witness)

    checkpoint = checkpoint_witness_state(state)
    restored = restore_witnesses_from_checkpoint(checkpoint)
    return project_witnesses(restored, now=now)
