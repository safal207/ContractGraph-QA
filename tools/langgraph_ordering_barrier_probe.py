#!/usr/bin/env python3
"""Bounded, no-sleep LangGraph #8039 ordering / write-failure probe.

Ordering GREEN means an ordinary write completed before actual saver put/aput
entry. Registration and barrier names are diagnostics, never verdict inputs.
Failed-write propagation is a SEPARATE axis. Neither axis proves exactly-once
external effects, storage durability, or crash/recovery safety.
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures as cf
import importlib.metadata as metadata
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCHEMA = "cgqa.langgraph.ordering-barrier-red-first/v0.2"
TIMEOUT = 5  # Watchdog only: expiry is a harness error, never expected RED.
INVARIANT = "ordinary write drained before actual superseding saver put/aput entry"
CLAIM_BOUNDARY = (
    "Bounded loop/saver-entry ordering and separate failed-write propagation only. "
    "GREEN does not establish storage durability, full graph recovery, exactly-once "
    "external effects, or close the effect-before-local-receipt crash window."
)


class HarnessError(RuntimeError):
    pass


class WriteFailure(RuntimeError):
    pass


class _Recorder:
    def __init__(self, fail: bool) -> None:
        self.fail = fail
        self.error = WriteFailure("ordinary-put-writes-sentinel")
        self.events: list[str] = []
        self.futures: list[Any] = []
        self.entries: list[dict[str, Any]] = []
        self.write_completed = False
        self.write_failed = False
        self.write_attempts = 0
        self.driver_thread = threading.get_ident()
        self.driver_task: Any = None
        self.release = threading.Event()
        self.started = threading.Event()
        self.arelease = asyncio.Event()
        self.astarted = asyncio.Event()

    def _complete_write(self) -> None:
        if self.fail:
            self.write_failed = True
            self.events.append("write_failed")
            raise self.error
        self.write_completed = True
        self.events.append("write_completed")

    def put_writes(self, *args: Any, **kwargs: Any) -> None:
        self.write_attempts += 1
        self.events.append("write_started")
        self.started.set()
        # An inline synchronous write is a valid alternative to registration.
        if not self.fail and threading.get_ident() != self.driver_thread:
            if not self.release.wait(TIMEOUT):
                raise HarnessError("sync write release watchdog expired")
        self._complete_write()

    async def aput_writes(self, *args: Any, **kwargs: Any) -> None:
        self.write_attempts += 1
        self.events.append("write_started")
        self.astarted.set()
        if not self.fail and asyncio.current_task() is not self.driver_task:
            await asyncio.wait_for(self.arelease.wait(), TIMEOUT)
        self._complete_write()

    def _entry(self, name: str, config: Any) -> Any:
        # Observe BEFORE cleanup releases a write on an unbarriered subject.
        self.entries.append({
            "event": name,
            "ordinary_write_drained": self.write_completed,
            "all_submitted_futures_done": all(f.done() for f in self.futures),
        })
        self.events.append(name)
        return config

    def put(self, config: Any, *args: Any, **kwargs: Any) -> Any:
        return self._entry("put", config)

    async def aput(self, config: Any, *args: Any, **kwargs: Any) -> Any:
        return self._entry("aput", config)


def _new_loop(cls: type[Any], recorder: _Recorder, submit: Any, *, asynchronous: bool) -> Any:
    loop = object.__new__(cls)
    loop.checkpoint_pending_writes = []
    loop.specs = {}
    loop.channels = {}  # ordinary-channel is deliberately not a DeltaChannel.
    loop.durability = "sync"  # Also on the async API control.
    loop.cache = None
    loop.checkpointer = recorder
    loop.checkpointer_put_writes = recorder.aput_writes if asynchronous else recorder.put_writes
    loop.checkpointer_put_writes_accepts_task_path = False
    loop.config = loop.checkpoint_config = {"configurable": {}}
    loop.checkpoint = {"id": "cp-parent"}
    # Pinned-interface setup only. Never inject a future into either list.
    loop._delta_write_futs = []
    loop._pending_write_futs = []
    loop._error_handler_write_futs = []
    loop.submit = submit
    return loop


def _registration(loop: Any, futures: list[Any]) -> dict[str, Any]:
    lists = {k: v for k, v in vars(loop).items()
             if k.endswith("_write_futs") and isinstance(v, list)}
    return {
        "registered_barriers": sorted(k for k, v in lists.items()
                                      if any(f is item for f in futures for item in v)),
        "known_write_barrier_sizes": {k: len(v) for k, v in sorted(lists.items())},
    }


def _report(r: _Recorder, caught: BaseException | None, diagnostic: dict[str, Any]) -> dict[str, Any]:
    if caught is not None and caught is not r.error:
        raise HarnessError(f"unexpected probe exception: {caught!r}") from caught
    if r.write_attempts != 1:
        raise HarnessError(f"expected one real saver write, observed {r.write_attempts}")
    for f in r.futures:
        if not f.done() or f.cancelled():
            raise HarnessError("write future did not terminate normally")
        error = f.exception()
        if error is not None and error is not r.error:
            raise HarnessError(f"write fixture failed: {error!r}") from error
    if r.fail:
        passed = r.write_failed and caught is r.error and not r.entries
    else:
        passed = (caught is None and len(r.entries) == 1
                  and r.entries[0]["ordinary_write_drained"]
                  and r.entries[0]["all_submitted_futures_done"])
    return {
        "passed": bool(passed),
        "events": r.events,
        "saver_entries": r.entries,
        "original_write_error_propagated": caught is r.error,
        "write_failed": r.write_failed,
        "submitted_future_count": len(r.futures),
        "diagnostics": diagnostic,
    }


def _sync_case(cls: type[Any], *, fail: bool = False) -> dict[str, Any]:
    r = _Recorder(fail)
    real_wait = cf.wait
    caught: BaseException | None = None
    diagnostic: dict[str, Any] = {}
    with cf.ThreadPoolExecutor(max_workers=1) as executor:
        def submit(fn: Any, *args: Any, **kwargs: Any) -> Any:
            kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}
            f = executor.submit(fn, *args, **kwargs)
            r.futures.append(f)
            original_result = f.result

            def observed_result(timeout: float | None = None) -> Any:
                r.events.append("result")
                r.release.set()
                return original_result(TIMEOUT if timeout is None else timeout)

            f.result = observed_result
            return f

        def observed_wait(fs: Any, timeout: Any = None, return_when: Any = cf.ALL_COMPLETED) -> Any:
            fs = list(fs)
            if any(f is item for f in r.futures for item in fs):
                r.events.append("wait")
                r.release.set()
            result = real_wait(fs, TIMEOUT if timeout is None else timeout, return_when)
            if result.not_done:
                raise HarnessError("sync wait watchdog expired")
            return result

        loop = _new_loop(cls, r, submit, asynchronous=False)
        try:
            with patch.object(cf, "wait", new=observed_wait):
                loop.put_writes("task-ordinary", [("ordinary-channel", 1)])
                diagnostic = _registration(loop, r.futures)
                if not r.started.wait(TIMEOUT):
                    raise HarnessError("sync saver write was not invoked")
                # Failure case starts with an already-failed REAL executor future.
                # wait() is not result(): do not retrieve/propagate it for the subject.
                if fail and r.futures:
                    if real_wait(r.futures, TIMEOUT).not_done:
                        raise HarnessError("failed sync future did not settle")
                cls._checkpointer_put_after_previous(loop, None, loop.config, {}, {}, {})
        except Exception as error:
            caught = error
        finally:
            r.release.set()  # Cleanup never changes the saved entry observations.
    return _report(r, caught, diagnostic)


async def _async_case(cls: type[Any], *, fail: bool = False) -> dict[str, Any]:
    r = _Recorder(fail)
    r.driver_task = asyncio.current_task()
    real_gather = asyncio.gather
    real_wait = asyncio.wait
    caught: BaseException | None = None
    diagnostic: dict[str, Any] = {}

    class WriteTask(asyncio.Task):
        def __await__(self) -> Any:
            r.events.append("await_write")
            r.arelease.set()
            return super().__await__()

    def submit(fn: Any, *args: Any, **kwargs: Any) -> Any:
        kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}
        task = WriteTask(fn(*args, **kwargs))
        r.futures.append(task)
        return task

    def observed_gather(*fs: Any, **kwargs: Any) -> Any:
        if any(f is item for f in r.futures for item in fs):
            r.events.append("gather")
            r.arelease.set()
        return real_gather(*fs, **kwargs)

    async def observed_wait(fs: Any, **kwargs: Any) -> Any:
        fs = list(fs)
        if any(f is item for f in r.futures for item in fs):
            r.events.append("async_wait")
            r.arelease.set()
        return await real_wait(fs, **kwargs)

    loop = _new_loop(cls, r, submit, asynchronous=True)
    try:
        with patch.object(asyncio, "gather", new=observed_gather), patch.object(asyncio, "wait", new=observed_wait):
            loop.put_writes("task-ordinary", [("ordinary-channel", 1)])
            diagnostic = _registration(loop, r.futures)
            await asyncio.wait_for(r.astarted.wait(), TIMEOUT)
            if fail and r.futures:
                _, pending = await real_wait(r.futures, timeout=TIMEOUT)
                if pending:
                    raise HarnessError("failed async future did not settle")
            await asyncio.wait_for(
                cls._checkpointer_put_after_previous(loop, None, loop.config, {}, {}, {}),
                TIMEOUT,
            )
    except Exception as error:
        caught = error
    finally:
        r.arelease.set()
        if r.futures:
            await asyncio.wait_for(real_gather(*r.futures, return_exceptions=True), TIMEOUT)
    return _report(r, caught, diagnostic)


def _results(sync_cls: type[Any], async_cls: type[Any]) -> dict[str, Any]:
    sync = _sync_case(sync_cls)
    asynchronous = asyncio.run(_async_case(async_cls))
    failed_sync = _sync_case(sync_cls, fail=True)
    failed_async = asyncio.run(_async_case(async_cls, fail=True))
    checks = {
        "sync_ordinary_write_drained_before_actual_put": sync["passed"],
        "async_ordinary_write_drained_before_actual_aput": asynchronous["passed"],
    }
    failure_checks = {
        "sync_failed_write_propagated_before_put": failed_sync["passed"],
        "async_failed_write_propagated_before_aput": failed_async["passed"],
    }
    sync_names = sync["diagnostics"].get("registered_barriers", [])
    async_names = asynchronous["diagnostics"].get("registered_barriers", [])
    return {
        "schema": SCHEMA,
        "issue": "langchain-ai/langgraph#8039",
        "invariant": INVARIANT,
        "checks": checks,
        "verdict": "GREEN" if all(checks.values()) else "RED",
        "diagnostics": {
            "ordinary_future_registered": bool(sync_names),
            "registered_in_same_sync_and_async_barrier": bool(set(sync_names) & set(async_names)),
            "sync_registered_barriers": sync_names,
            "async_registered_barriers": async_names,
        },
        "evidence": {"sync": sync, "async": asynchronous},
        "failure_propagation": {
            "invariant": "failed ordinary write must propagate its original exception before saver entry",
            "checks": failure_checks,
            "verdict": "GREEN" if all(failure_checks.values()) else "RED",
            "evidence": {"sync": failed_sync, "async": failed_async},
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def run_probe() -> dict[str, Any]:
    from langgraph.pregel import _loop as loop_module
    result = _results(loop_module.SyncPregelLoop, loop_module.AsyncPregelLoop)
    result["subject"] = {
        "repository": os.environ.get("CGQA_SUBJECT_REPOSITORY"),
        "ref": os.environ.get("CGQA_SUBJECT_REF"),
        "langgraph_version": metadata.version("langgraph"),
        "loop_module": str(Path(loop_module.__file__).resolve()),
        "loop_source_sha256": hashlib.sha256(Path(loop_module.__file__).read_bytes()).hexdigest(),
        "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect", choices=("red", "green"), help="ordering verdict, for each API path")
    parser.add_argument("--expect-sync-failure-propagation", choices=("red", "green"))
    parser.add_argument("--expect-async-failure-propagation", choices=("red", "green"))
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    exit_code = 0
    try:
        result = run_probe()
        mismatches = []
        if args.expect:
            for name, ok in result["checks"].items():
                if ok != (args.expect == "green"):
                    mismatches.append(name)
        for path in ("sync", "async"):
            expected = getattr(args, f"expect_{path}_failure_propagation")
            observed = result["failure_propagation"]["evidence"][path]["passed"]
            if expected and observed != (expected == "green"):
                mismatches.append(f"{path}_failure_propagation")
        result["expectation_mismatches"] = mismatches
        exit_code = int(bool(mismatches))
    except Exception as error:
        result = {"schema": SCHEMA, "verdict": "ERROR", "harness_error": repr(error),
                  "claim_boundary": CLAIM_BOUNDARY}
        exit_code = 2
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
