#!/usr/bin/env python3
"""Apply the CGQA non-collapsing correlation proof patch to pinned Gonka.

Proof-only transformation:
- keep gateway-generated internal request IDs canonical;
- bind caller X-Request-Id as a separate client correlation value;
- propagate both identities through detached background inference;
- persist one-to-many client -> internal request mappings;
- expose an explicit correlation lookup endpoint;
- initialize proof-only correlation storage when PerfStore opens, never on the
  inference hot path.
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
ROUTE_OLD = 'mux.HandleFunc("GET /v1/requests/{request_id}", proxy.handleRequestAccounting)'
ROUTE_NEW = ROUTE_OLD + '\n\tmux.HandleFunc("GET /v1/request-correlations/{client_request_id}", proxy.handleCGQARequestCorrelation)'
STORE_RETURN_OLD = 'return &PerfStore{db: db, path: dbPath}, nil'
STORE_RETURN_NEW = '''store := &PerfStore{db: db, path: dbPath}
\tif err := store.ensureCGQARequestCorrelationSchema(); err != nil {
\t\tdb.Close()
\t\treturn nil, fmt.Errorf("create CGQA correlation schema: %w", err)
\t}
\treturn store, nil'''


def replace_exact(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrences of patch anchor, found {count}")
    if new in text:
        raise SystemExit(f"{path}: proof patch appears already applied")

    patched = text.replace(old, new)

    # Some proof transformations deliberately retain the original statement
    # and append a second statement after it (for example canonical accounting
    # start + correlation insert, or existing route + correlation route). In
    # those cases `old` is a substring of `new`, so counting `old` after the
    # replacement cannot distinguish a successful insertion from a leftover.
    # We still fail closed on the exact pre-patch count and require the exact
    # post-patch replacement count.
    if old not in new and patched.count(old) != 0:
        raise SystemExit(f"{path}: original patch anchor remains after replacement")
    if patched.count(new) != expected:
        raise SystemExit(f"{path}: replacement count is not exact")

    path.write_text(patched, encoding="utf-8")


def apply(root: Path) -> None:
    gateway = root / "devshard/cmd/devshardctl/gateway.go"
    proxy = root / "devshard/cmd/devshardctl/proxy.go"
    redundancy = root / "devshard/cmd/devshardctl/redundancy.go"
    perfstore = root / "devshard/cmd/devshardctl/perfstore.go"

    # Correlation storage is created with the store, before request traffic.
    replace_exact(perfstore, STORE_RETURN_OLD, STORE_RETURN_NEW, 1)
    # Two gateway chat entrypoints (pooled + explicit devshard route).
    replace_exact(gateway, ENTRY_OLD, ENTRY_NEW, 2)
    # Direct proxy chat entrypoint.
    replace_exact(proxy, ENTRY_OLD, ENTRY_NEW, 1)
    # Streaming + non-streaming detached execution keep background cancellation
    # semantics but carry internal request ID and client correlation separately.
    replace_exact(proxy, RUN_OLD, RUN_NEW, 2)
    # Persist the relation only after canonical request accounting starts.
    replace_exact(redundancy, START_OLD, START_NEW, 1)
    # RuntimeMux owns /v1/requests and the proof correlation lookup route.
    replace_exact(gateway, ROUTE_OLD, ROUTE_NEW, 1)

    print(
        "CGQA safe correlation proof patch applied: internal request IDs remain canonical; "
        "caller correlation is one-to-many, separately queryable, and schema DDL stays off the inference hot path"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gonka_root", type=Path)
    args = parser.parse_args()
    apply(args.gonka_root)


if __name__ == "__main__":
    main()
