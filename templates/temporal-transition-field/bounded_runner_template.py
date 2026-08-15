#!/usr/bin/env python3
"""Generic bounded runner template for Temporal Transition Field QA.

Safe defaults:
- dry-run unless --execute is supplied;
- credentials from environment variables only;
- explicit same-origin URL/path allow-list;
- bounded response reads and bounded concurrency;
- intended only for authorized sandbox/local-fork/test environments.
"""

import argparse
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib import error, parse, request

BASE_URL = os.getenv("CGQA_TEST_BASE_URL", "https://example.invalid/api")
API_KEY_ENV = "CGQA_TEST_API_KEY"
MAX_CONCURRENCY = 2
MAX_RESPONSE_BYTES = 1_048_576

ALLOWED_PATH_ROOTS = (
    ("sandbox",),
    ("policy",),
    ("action",),
    ("audit",),
    ("transactions",),
)


def _segments(path: str) -> tuple[str, ...]:
    decoded = parse.unquote(path)
    parts: list[str] = []
    for part in decoded.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise RuntimeError("Blocked path traversal outside declared test scope")
            parts.pop()
            continue
        parts.append(part)
    return tuple(parts)


def _base_parts():
    parts = parse.urlsplit(BASE_URL)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise RuntimeError("CGQA_TEST_BASE_URL must be an http(s) URL with a host")
    if parts.username or parts.password:
        raise RuntimeError("Credentials are not allowed in CGQA_TEST_BASE_URL")
    return parts


def _same_origin(left, right) -> bool:
    return (
        left.scheme.lower(),
        left.hostname.lower() if left.hostname else None,
        left.port,
    ) == (
        right.scheme.lower(),
        right.hostname.lower() if right.hostname else None,
        right.port,
    )


def _relative_scoped_segments(url_parts) -> tuple[str, ...]:
    base = _base_parts()
    if not _same_origin(base, url_parts):
        raise RuntimeError("Blocked request outside declared test origin")

    base_segments = _segments(base.path)
    target_segments = _segments(url_parts.path)
    if target_segments[: len(base_segments)] != base_segments:
        raise RuntimeError("Blocked request outside declared base path")
    relative = target_segments[len(base_segments) :]
    if not any(relative[: len(root)] == root for root in ALLOWED_PATH_ROOTS):
        raise RuntimeError("Blocked path outside declared test scope")
    return relative


def guard(path: str):
    if not isinstance(path, str) or not path.startswith("/"):
        raise RuntimeError("Request path must be absolute within the declared test base")
    relative = _segments(path)
    if not any(relative[: len(root)] == root for root in ALLOWED_PATH_ROOTS):
        raise RuntimeError(f"Blocked path outside declared test scope: {path}")


def scoped_url(path: str) -> str:
    guard(path)
    base = _base_parts()
    full_url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    parts = parse.urlsplit(full_url)
    if parts.scheme not in {"http", "https"}:
        raise RuntimeError("Blocked non-http(s) request scheme")
    _relative_scoped_segments(parts)
    return full_url


class ScopedRedirectHandler(request.HTTPRedirectHandler):
    """Reject redirects that leave the approved origin or path roots."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = parse.urljoin(req.full_url, newurl)
        parts = parse.urlsplit(target)
        if parts.scheme not in {"http", "https"}:
            raise RuntimeError("Blocked redirect to non-http(s) scheme")
        _relative_scoped_segments(parts)
        return super().redirect_request(req, fp, code, msg, headers, target)


OPENER = request.build_opener(ScopedRedirectHandler())


def idem():
    return f"cgqa-{uuid.uuid4()}"


def _bounded_read(stream) -> bytes:
    raw = stream.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError(f"response_exceeds_{MAX_RESPONSE_BYTES}_bytes")
    return raw


def _decode_json(raw: bytes):
    text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        return None, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, {
            "kind": "invalid_json",
            "message": str(exc),
            "body_bytes": len(raw),
        }


def _timed_result(started_ns: int, result: dict) -> dict:
    ended_ns = time.monotonic_ns()
    return {
        **result,
        "timing": {
            "started_monotonic_ns": started_ns,
            "ended_monotonic_ns": ended_ns,
            "duration_ms": round((ended_ns - started_ns) / 1_000_000, 3),
        },
    }


def call(method: str, path: str, payload=None, execute=False, start_barrier=None):
    guard(path)
    if not execute:
        return {"dry_run": True, "method": method, "path": path, "payload": payload}

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"{API_KEY_ENV} is required for --execute")

    try:
        full_url = scoped_url(path)
    except RuntimeError as exc:
        return {"complete": False, "policy_error": str(exc), "method": method, "path": path}

    if start_barrier is not None:
        try:
            start_barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            return {
                "complete": False,
                "synchronization_error": "race_start_barrier_broken",
                "method": method,
                "path": path,
            }

    started_ns = time.monotonic_ns()
    body = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = request.Request(full_url, data=body, headers=headers, method=method)

    try:
        with OPENER.open(req, timeout=15) as response:
            raw = _bounded_read(response)
            data, parse_error = _decode_json(raw)
            if parse_error is not None:
                return _timed_result(
                    started_ns,
                    {
                        "complete": False,
                        "status": response.status,
                        "response_error": parse_error,
                    },
                )
            return _timed_result(
                started_ns,
                {"complete": True, "status": response.status, "data": data},
            )
    except error.HTTPError as exc:
        try:
            raw = _bounded_read(exc)
        except ValueError as read_exc:
            return _timed_result(
                started_ns,
                {
                    "complete": False,
                    "status": exc.code,
                    "response_error": {"kind": str(read_exc)},
                },
            )
        data, parse_error = _decode_json(raw)
        return _timed_result(
            started_ns,
            {
                "complete": True,
                "status": exc.code,
                "http_error": True,
                "data": data,
                "response_error": parse_error,
            },
        )
    except ValueError as exc:
        return _timed_result(
            started_ns,
            {"complete": False, "response_error": {"kind": str(exc)}},
        )
    except (error.URLError, TimeoutError, OSError) as exc:
        return _timed_result(
            started_ns,
            {
                "complete": False,
                "transport_error": type(exc).__name__,
                "message": str(exc),
            },
        )
    except RuntimeError as exc:
        return _timed_result(
            started_ns,
            {"complete": False, "policy_error": str(exc)},
        )


def _readable_success(result: dict) -> bool:
    return (
        result.get("complete") is True
        and isinstance(result.get("status"), int)
        and 200 <= result["status"] < 300
        and isinstance(result.get("data"), (dict, list))
    )


def _collect_tail(evidence: dict, execute: bool) -> dict:
    evidence["after"] = call("GET", "/audit", None, execute)
    evidence["transactions"] = call("GET", "/transactions", None, execute)
    if execute and not all(
        item.get("complete") is True
        for item in (evidence["after"], evidence["transactions"])
    ):
        evidence["complete"] = False
    return evidence


def run_boundary_race(
    execute=False,
    *,
    boundary_limit=None,
    remaining_budget=None,
    action_amount=30,
):
    """Run two individually valid actions whose aggregate should cross a known boundary."""
    before = call("GET", "/audit", None, execute)
    evidence = {"before": before, "complete": True}

    payloads = [
        {"amount": action_amount, "idempotencyKey": idem()},
        {"amount": action_amount, "idempotencyKey": idem()},
    ]

    if execute:
        if not _readable_success(before):
            evidence.update(
                {
                    "complete": False,
                    "race": [],
                    "precondition": {
                        "status": "blocked",
                        "reason": "unreadable_or_failed_audit_preflight",
                    },
                }
            )
            return _collect_tail(evidence, execute)

        if not all(isinstance(value, (int, float)) for value in (boundary_limit, remaining_budget)):
            evidence.update(
                {
                    "complete": False,
                    "race": [],
                    "precondition": {
                        "status": "blocked",
                        "reason": "boundary_limit_and_remaining_budget_required",
                    },
                }
            )
            return _collect_tail(evidence, execute)

        combined = action_amount * len(payloads)
        boundary_proven = (
            boundary_limit >= 0
            and 0 <= remaining_budget <= boundary_limit
            and action_amount > 0
            and action_amount <= remaining_budget
            and combined > remaining_budget
        )
        evidence["precondition"] = {
            "status": "proven" if boundary_proven else "blocked",
            "boundary_limit": boundary_limit,
            "remaining_budget": remaining_budget,
            "individual_amount": action_amount,
            "combined_amount": combined,
            "expected_relation": "individual <= remaining < combined",
        }
        if not boundary_proven:
            evidence["complete"] = False
            evidence["race"] = []
            return _collect_tail(evidence, execute)

        barrier = threading.Barrier(len(payloads))
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            futures = [
                pool.submit(call, "POST", "/action", payload, True, barrier)
                for payload in payloads
            ]
            evidence["race"] = [future.result() for future in futures]
        if not all(item.get("complete") is True for item in evidence["race"]):
            evidence["complete"] = False
    else:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
            futures = [pool.submit(call, "POST", "/action", payload, False) for payload in payloads]
            evidence["race"] = [future.result() for future in futures]
        evidence["precondition"] = {"status": "not_evaluated_dry_run"}

    return _collect_tail(evidence, execute)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--scenario", choices=["boundary-race"], default="boundary-race")
    parser.add_argument("--boundary-limit", type=float)
    parser.add_argument("--remaining-budget", type=float)
    parser.add_argument("--action-amount", type=float, default=30)
    args = parser.parse_args()

    if not args.execute:
        print("DRY RUN: no network calls will be made.")

    result = run_boundary_race(
        execute=args.execute,
        boundary_limit=args.boundary_limit,
        remaining_budget=args.remaining_budget,
        action_amount=args.action_amount,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
