#!/usr/bin/env python3
"""Generic bounded runner template for Temporal Transition Field QA.

Safe defaults:
- dry-run unless --execute is supplied;
- credentials from environment variables only;
- explicit allow-list for paths;
- bounded concurrency;
- intended only for authorized sandbox/local-fork/test environments.
"""

import argparse
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib import request, error

BASE_URL = os.getenv("CGQA_TEST_BASE_URL", "https://example.invalid/api")
API_KEY_ENV = "CGQA_TEST_API_KEY"
MAX_CONCURRENCY = 2

ALLOWED_PATH_PREFIXES = (
    "/sandbox/",
    "/policy",
    "/action",
    "/audit",
    "/transactions",
)


def guard(path: str):
    if not any(path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
        raise RuntimeError(f"Blocked path outside declared test scope: {path}")


def idem():
    return f"cgqa-{uuid.uuid4()}"


def call(method: str, path: str, payload=None, execute=False):
    guard(path)
    if not execute:
        return {"dry_run": True, "method": method, "path": path, "payload": payload}

    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"{API_KEY_ENV} is required for --execute")

    body = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    req = request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw)
            except Exception:
                data = raw
            return {"status": response.status, "data": data}
    except error.HTTPError as exc:
        return {
            "status": exc.code,
            "data": exc.read().decode("utf-8", errors="replace"),
        }


def run_boundary_race(execute=False):
    """Template race: each action is independently valid, aggregate is not."""
    evidence = {
        "before": call("GET", "/audit", None, execute),
    }

    payloads = [
        {"amount": 30, "idempotencyKey": idem()},
        {"amount": 30, "idempotencyKey": idem()},
    ]

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = [pool.submit(call, "POST", "/action", p, execute) for p in payloads]
        evidence["race"] = [future.result() for future in futures]

    evidence["after"] = call("GET", "/audit", None, execute)
    evidence["transactions"] = call("GET", "/transactions", None, execute)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--scenario", choices=["boundary-race"], default="boundary-race")
    args = parser.parse_args()

    if not args.execute:
        print("DRY RUN: no network calls will be made.")

    result = run_boundary_race(execute=args.execute)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
