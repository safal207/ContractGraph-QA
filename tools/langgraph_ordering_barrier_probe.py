#!/usr/bin/env python3
"""Deterministic RED→GREEN mechanism probe for langchain-ai/langgraph#8039.

This probe intentionally does not use sleeps, scheduler luck, SIGKILL, or external
side-effect counts. It exercises the actual `PregelLoop.put_writes` method with
an ordinary (non-DeltaChannel) write and records whether the returned future is
registered in the same barrier later drained before the superseding saver `put`.

Claim boundary: this only checks the persistence-ordering mechanism. It does not
claim exactly-once external side effects; a process can still crash after a real
external effect but before its local durable receipt is written.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import importlib.metadata as metadata
import inspect
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCHEMA = "cgqa.langgraph.ordering-barrier-red-first/v0.1"
INVARIANT = (
    "ordinary pending writes must be registered in the checkpoint barrier, and "
    "that same barrier must be drained before the actual superseding saver put begins"
)


def _new_loop(loop_cls: type[Any], sentinel: object) -> Any:
    loop = object.__new__(loop_cls)
    loop.checkpoint_pending_writes = []
    loop.specs = {}
    loop.channels = {}
    loop.durability = "sync"
    loop.cache = None
    loop.checkpointer_put_writes = lambda *args, **kwargs: None
    loop.checkpointer_put_writes_accepts_task_path = False
    loop.checkpoint_config = {"configurable": {}}
    loop.config = {"configurable": {}}
    loop.checkpoint = {"id": "cp-parent"}
    # Seed both historical and proposed names so the probe can execute against
    # current main and PR #8055 without version-specific setup branches.
    loop._delta_write_futs = []
    loop._pending_write_futs = []
    loop._error_handler_write_futs = []
    loop.submit = lambda fn, *args, **kwargs: sentinel
    return loop


def _registered_barriers(sync_loop_cls: type[Any]) -> tuple[list[str], dict[str, list[Any]]]:
    sentinel = object()
    loop = _new_loop(sync_loop_cls, sentinel)
    loop.put_writes("task-ordinary", [("ordinary-channel", {"value": 1})])

    barriers: dict[str, list[Any]] = {}
    registered: list[str] = []
    for name, value in vars(loop).items():
        if not name.endswith("_write_futs") or not isinstance(value, list):
            continue
        barriers[name] = value
        if sentinel in value:
            registered.append(name)
    return sorted(registered), barriers


class _SyncSaver:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def put(
        self,
        config: dict[str, Any],
        checkpoint: dict[str, Any],
        metadata_value: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        self.events.append("put")
        return config


class _AsyncSaver:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: dict[str, Any],
        metadata_value: dict[str, Any],
        new_versions: dict[str, Any],
    ) -> dict[str, Any]:
        self.events.append("aput")
        return config


def _sync_drain_order(
    loop_module: Any,
    sync_loop_cls: type[Any],
    barrier_name: str,
) -> tuple[bool, list[str]]:
    events: list[str] = []
    loop = object.__new__(sync_loop_cls)
    loop._delta_write_futs = []
    loop._pending_write_futs = []
    future: concurrent.futures.Future[None] = concurrent.futures.Future()
    setattr(loop, barrier_name, [future])
    loop.checkpointer = _SyncSaver(events)

    def fake_wait(futures: Any, *args: Any, **kwargs: Any) -> tuple[set[Any], set[Any]]:
        events.append("wait")
        return set(futures), set()

    with patch.object(loop_module.concurrent.futures, "wait", new=fake_wait):
        sync_loop_cls._checkpointer_put_after_previous(
            loop,
            None,
            {"configurable": {}},
            {},
            {},
            {},
        )
    return events[:2] == ["wait", "put"], events


async def _async_drain_order_inner(
    loop_module: Any,
    async_loop_cls: type[Any],
    barrier_name: str,
) -> tuple[bool, list[str]]:
    events: list[str] = []
    loop = object.__new__(async_loop_cls)
    loop._delta_write_futs = []
    loop._pending_write_futs = []
    setattr(loop, barrier_name, [object()])
    loop.checkpointer = _AsyncSaver(events)

    async def fake_gather(*futures: Any, **kwargs: Any) -> list[None]:
        events.append("gather")
        return [None for _ in futures]

    with patch.object(loop_module.asyncio, "gather", new=fake_gather):
        await async_loop_cls._checkpointer_put_after_previous(
            loop,
            None,
            {"configurable": {}},
            {},
            {},
            {},
        )
    return events[:2] == ["gather", "aput"], events


def _async_drain_order(
    loop_module: Any,
    async_loop_cls: type[Any],
    barrier_name: str,
) -> tuple[bool, list[str]]:
    return asyncio.run(_async_drain_order_inner(loop_module, async_loop_cls, barrier_name))


def run_probe() -> dict[str, Any]:
    from langgraph.pregel import _loop as loop_module
    from langgraph.pregel._loop import AsyncPregelLoop, SyncPregelLoop

    registered, barriers = _registered_barriers(SyncPregelLoop)
    sync_source = inspect.getsource(SyncPregelLoop._checkpointer_put_after_previous)
    async_source = inspect.getsource(AsyncPregelLoop._checkpointer_put_after_previous)

    linked = [
        name
        for name in registered
        if f"self.{name}" in sync_source and f"self.{name}" in async_source
    ]
    selected = linked[0] if len(linked) == 1 else None

    sync_ok = False
    sync_events: list[str] = []
    async_ok = False
    async_events: list[str] = []
    if selected is not None:
        sync_ok, sync_events = _sync_drain_order(loop_module, SyncPregelLoop, selected)
        async_ok, async_events = _async_drain_order(loop_module, AsyncPregelLoop, selected)

    checks = {
        "ordinary_future_registered": bool(registered),
        "registered_in_same_sync_and_async_barrier": selected is not None,
        "sync_barrier_drained_before_actual_put": sync_ok,
        "async_barrier_drained_before_actual_put": async_ok,
    }
    verdict = "GREEN" if all(checks.values()) else "RED"

    return {
        "schema": SCHEMA,
        "subject": {
            "repository": os.environ.get("CGQA_SUBJECT_REPOSITORY"),
            "ref": os.environ.get("CGQA_SUBJECT_REF"),
            "langgraph_version": metadata.version("langgraph"),
            "loop_module": str(Path(loop_module.__file__).resolve()),
        },
        "issue": "langchain-ai/langgraph#8039",
        "candidate_fix": "langchain-ai/langgraph#8055",
        "invariant": INVARIANT,
        "checks": checks,
        "evidence": {
            "registered_barriers": registered,
            "known_write_barrier_sizes_after_ordinary_put_writes": {
                name: len(value) for name, value in sorted(barriers.items())
            },
            "selected_barrier": selected,
            "sync_events": sync_events,
            "async_events": async_events,
        },
        "verdict": verdict,
        "claim_boundary": (
            "Mechanism-level persistence ordering only. GREEN does not establish exactly-once "
            "external effects or close the effect-before-local-receipt crash window."
        ),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=("red", "green"))
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_probe()
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    if args.expect is not None and result["verdict"].lower() != args.expect:
        print(
            f"expected {args.expect.upper()} but observed {result['verdict']}",
            file=os.sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
