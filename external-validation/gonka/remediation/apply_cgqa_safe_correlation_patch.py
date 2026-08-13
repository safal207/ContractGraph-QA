#!/usr/bin/env python3
"""Apply the CGQA non-collapsing correlation proof patch to pinned Gonka.

Proof-only transformation:
- keep gateway-generated internal request IDs canonical;
- bind caller X-Request-Id as a separate client correlation value;
- propagate both identities through detached background inference;
- persist one-to-many client -> internal request mappings;
- expose an explicit correlation lookup endpoint.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ENTRY_OLD = 'ctx, _ := ensureRequestLogContext(r.Context())\n\tr = r.WithContext(ctx)'
ENTRY_NEW = 'ctx, _ := ensureRequestLogContext(r.Context())\n\tctx = withCGQAClientCorrelationID(ctx, r.Header.Get("X-Request-Id"))\n\tr = r.WithContext(ctx)'
RUN_OLD = 'RunInference(context.Background(), params,'
RUN_NEW = 'RunInference(propagateCGQARequestContext(context.Background(), r.Context()), params,'
START_OLD = 'e.perf.RecordAccountingRequestStart(requestID, e.devshardID, params.Model, time.Now())'
START_NEW = '''e.perf.RecordAccountingRequestStart(requestID, e.devshardID, params.Model, time.Now())
\tif clientID := cgqaClientCorrelationIDFromContext(ctx); clientID != "" {
\t\te.perf.recordCGQARequestCorrelation(clientID, requestID, e.devshardID, time.Now())
\t}'''
ROUTE_OLD = 'mux.HandleFunc("GET /v1/requests/{request_id}", p.handleRequestAccounting)'
ROUTE_NEW = ROUTE_OLD + '\n\tmux.HandleFunc("GET /v1/request-correlations/{client_request_id}", p.handleCGQARequestCorrelation)'


def replace_exact(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrences of patch anchor, found {count}")
    if new in text:
        raise SystemExit(f"{path}: proof patch appears already applied")
    patched = text.replace(old, new)
    if patched.count(old) != 0 or patched.count(new) != expected:
        raise SystemExit(f"{path}: replacement did not complete exactly")
    path.write_text(patched, encoding="utf-8")


def apply(root: Path) -> None:
    gateway = root / "devshard/cmd/devshardctl/gateway.go"
    proxy = root / "devshard/cmd/devshardctl/proxy.go"
    redundancy = root / "devshard/cmd/devshardctl/redundancy.go"

    # Two gateway chat entrypoints (pooled + explicit devshard route).
    replace_exact(gateway, ENTRY_OLD, ENTRY_NEW, 2)
    # Direct proxy chat entrypoint.
    replace_exact(proxy, ENTRY_OLD, ENTRY_NEW, 1)
    # Streaming + non-streaming detached execution keep background cancellation
    # semantics but carry internal request ID and client correlation separately.
    replace_exact(proxy, RUN_OLD, RUN_NEW, 2)
    # Persist the relation only after canonical request accounting starts.
    replace_exact(redundancy, START_OLD, START_NEW, 1)
    # Explicit namespace avoids conflating internal request IDs with caller IDs.
    replace_exact(gateway, ROUTE_OLD, ROUTE_NEW, 1)

    print(
        "CGQA safe correlation proof patch applied: internal request IDs remain canonical; "
        "caller correlation is one-to-many and separately queryable"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gonka_root", type=Path)
    args = parser.parse_args()
    apply(args.gonka_root)


if __name__ == "__main__":
    main()
