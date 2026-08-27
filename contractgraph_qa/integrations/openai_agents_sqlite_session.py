from __future__ import annotations

import copy
import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import Any

from contractgraph_qa.witness_projection import project_witnesses

OPENAI_AGENTS_SOURCE_REPOSITORY = "openai/openai-agents-python"
OPENAI_AGENTS_SOURCE_COMMIT = "7f7a44f8dc0650296bd5ab6c745c9bcbaa6ac3b7"
OPENAI_AGENTS_SESSION_SOURCE = "src/agents/memory/session.py"
OPENAI_AGENTS_SQLITE_SESSION_SOURCE = "src/agents/memory/sqlite_session.py"
OPENAI_AGENTS_NATIVE_MUTATORS = ("pop_item", "clear_session")

Witness = Mapping[str, Any]
_WITNESS_PREFIX = "cgqa:witness-projection-conformance:v0.1:"


def encode_witness_as_session_item(witness: Witness) -> dict[str, Any]:
    """Encode one witness as a normal Responses-style user message item.

    The pinned Agents SDK ``Session`` boundary stores ``TResponseInputItem``
    conversation items. A thin hosted adapter therefore needs an explicit
    domain envelope rather than pretending the session is a general state
    checkpoint. The witness JSON is canonicalized only for stable transport;
    projection semantics remain entirely in the decoded witness fields.
    """

    payload = json.dumps(
        copy.deepcopy(dict(witness)),
        sort_keys=True,
        separators=(",", ":"),
    )
    return {"role": "user", "content": f"{_WITNESS_PREFIX}{payload}"}


def decode_witness_session_item(item: Mapping[str, Any]) -> dict[str, Any]:
    """Decode a witness from the hosted session envelope."""

    if item.get("role") != "user":
        raise ValueError("witness session item must use role='user'")
    content = item.get("content")
    if not isinstance(content, str) or not content.startswith(_WITNESS_PREFIX):
        raise ValueError("session item is not a ContractGraph-QA witness envelope")
    decoded = json.loads(content[len(_WITNESS_PREFIX) :])
    if not isinstance(decoded, dict):
        raise ValueError("decoded witness must be an object")
    return decoded


def sqlite_session_round_trip(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Exercise the pinned SQLiteSession JSON/order persistence shape.

    The pinned implementation writes each item with ``json.dumps(item)`` into
    an autoincrement ``id`` row and retrieves items with ``ORDER BY id ASC``.
    This dependency-free probe reproduces that storage contract directly with
    Python's standard-library sqlite3 rather than importing the Agents SDK.
    """

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """
            CREATE TABLE agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_data TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO agent_messages (session_id, message_data) VALUES (?, ?)",
            [("cgqa", json.dumps(copy.deepcopy(dict(item)))) for item in items],
        )
        rows = conn.execute(
            "SELECT message_data FROM agent_messages WHERE session_id = ? ORDER BY id ASC",
            ("cgqa",),
        ).fetchall()
        return [json.loads(message_data) for (message_data,) in rows]
    finally:
        conn.close()


def restore_witnesses_from_session_items(
    items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Restore the ordered witness sequence from hosted session items."""

    return [decode_witness_session_item(item) for item in items]


def project_openai_agents_session_boundary(
    witnesses: Sequence[Witness], now: int | float | None = None
) -> str:
    """Replay v0.1 through the OpenAI Agents SDK session persistence shape.

    This is a hosted adapter benchmark, not a claim that ``Session`` is a
    native evidence log. ``Session`` is conversational memory and explicitly
    exposes destructive ``pop_item`` and ``clear_session`` operations. The
    conformant boundary is therefore the restricted adapter path:

    witnesses -> Responses-style envelope -> JSON/SQLite persistence ->
    ordered restore -> frozen witness projection.
    """

    items = [encode_witness_as_session_item(witness) for witness in witnesses]
    restored_items = sqlite_session_round_trip(items)
    restored_witnesses = restore_witnesses_from_session_items(restored_items)
    return project_witnesses(restored_witnesses, now=now)
