from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from typing import Any

from contractgraph_qa.witness_projection import project_witnesses

MS_AGENT_FRAMEWORK_SOURCE_REPOSITORY = "microsoft/agent-framework"
MS_AGENT_FRAMEWORK_SOURCE_COMMIT = "d9d3fb6252f7ae9e7f8104edce7266f0782a813c"
MS_AGENT_FRAMEWORK_CHECKPOINT_SOURCE = (
    "python/packages/core/agent_framework/_workflows/_checkpoint.py"
)
MS_AGENT_FRAMEWORK_CHECKPOINT_ENCODING_SOURCE = (
    "python/packages/core/agent_framework/_workflows/_checkpoint_encoding.py"
)

Witness = Mapping[str, Any]


def workflow_checkpoint_state(
    witnesses: Sequence[Witness],
    *,
    checkpoint_id: str = "cgqa-checkpoint",
    previous_checkpoint_id: str | None = None,
    timestamp: str = "2026-08-22T00:00:00+00:00",
) -> dict[str, Any]:
    """Build the minimal source-pinned WorkflowCheckpoint shape for this benchmark.

    At the pinned upstream source, ``WorkflowCheckpoint.state`` contains committed
    workflow/user state and checkpoint objects carry lineage separately via
    ``previous_checkpoint_id``. The witness log is therefore stored as ordinary
    committed user state, while checkpoint metadata remains outside the projection.
    """

    return {
        "workflow_name": "witness-projection-conformance-v0.1",
        "graph_signature_hash": "cgqa-source-pinned-adapter",
        "checkpoint_id": checkpoint_id,
        "previous_checkpoint_id": previous_checkpoint_id,
        "timestamp": timestamp,
        "messages": {},
        "state": {
            "witnesses": [copy.deepcopy(dict(item)) for item in witnesses]
        },
        "pending_request_info_events": {},
        "iteration_count": len(witnesses),
        "metadata": {"adapter": "contractgraph-qa"},
        "version": "1.0",
    }


def checkpoint_json_round_trip(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    """Exercise the JSON-safe subset used by the canonical witness fixtures.

    Agent Framework's file checkpoint storage encodes values before JSON storage
    and decodes them on load. The conformance fixtures use only JSON-safe
    primitives, so an ordinary JSON round trip is a deliberately stricter,
    dependency-free representability check for this boundary.
    """

    return json.loads(json.dumps(copy.deepcopy(dict(checkpoint))))


def restore_witnesses_from_workflow_checkpoint(
    checkpoint: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Restore the canonical witness sequence from committed workflow state."""

    state = checkpoint.get("state")
    if not isinstance(state, Mapping):
        raise ValueError("workflow checkpoint must contain committed state")

    witnesses = state.get("witnesses")
    if not isinstance(witnesses, list):
        raise ValueError("workflow checkpoint state must contain witnesses list")

    return [copy.deepcopy(dict(item)) for item in witnesses]


def project_ms_agent_framework_checkpoint_boundary(
    witnesses: Sequence[Witness], now: int | float | None = None
) -> str:
    """Replay v0.1 through the pinned Agent Framework checkpoint state boundary.

    This is a hosted-domain benchmark over a framework-native checkpoint
    primitive. Microsoft Agent Framework does not natively define the
    ``sent``/``absence``/``response`` semantics. It does, however, expose a
    workflow checkpoint whose committed ``state`` can preserve the exact
    witness sequence across storage and restore.

    The checkpoint timestamp and lineage metadata are deliberately not used by
    the projection. Decision-affecting time remains inside explicit witnesses.
    """

    checkpoint = workflow_checkpoint_state(witnesses)
    restored_checkpoint = checkpoint_json_round_trip(checkpoint)
    restored_witnesses = restore_witnesses_from_workflow_checkpoint(restored_checkpoint)
    return project_witnesses(restored_witnesses, now=now)
