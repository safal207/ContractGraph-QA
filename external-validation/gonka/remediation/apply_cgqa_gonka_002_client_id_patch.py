#!/usr/bin/env python3
"""Apply the CGQA-GONKA-002 proof-of-fix patch to a pinned Gonka checkout.

This is a local verification patch only. It binds a caller-supplied
X-Request-Id at devshardctl HTTP entrypoints using Gonka's existing
logging.WithRequestID primitive. Existing generated-ID fallback behavior and
background execution / post-disconnect drain semantics remain unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path

LOGGING_OLD = '''func ensureRequestLogContext(ctx context.Context) (context.Context, string) {
\treturn logging.WithRequestID(ctx)
}
'''
LOGGING_NEW = '''func ensureRequestLogContext(ctx context.Context, ids ...string) (context.Context, string) {
\treturn logging.WithRequestID(ctx, ids...)
}
'''

HTTP_OLD = 'ctx, _ := ensureRequestLogContext(r.Context())'
HTTP_NEW = 'ctx, _ := ensureRequestLogContext(r.Context(), strings.TrimSpace(r.Header.Get("X-Request-Id")))'


def replace_exact(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrences, found {count}")
    if new in text:
        raise SystemExit(f"{path}: proof patch appears already applied")
    patched = text.replace(old, new)
    if patched.count(old) != 0 or patched.count(new) != expected:
        raise SystemExit(f"{path}: replacement count was not exact")
    path.write_text(patched, encoding="utf-8")


def apply(root: Path) -> None:
    logging_go = root / "devshard/cmd/devshardctl/logging.go"
    gateway_go = root / "devshard/cmd/devshardctl/gateway.go"
    proxy_go = root / "devshard/cmd/devshardctl/proxy.go"

    replace_exact(logging_go, LOGGING_OLD, LOGGING_NEW, 1)
    # Pooled chat and explicit /devshard/{id}/ chat entrypoints.
    replace_exact(gateway_go, HTTP_OLD, HTTP_NEW, 2)
    # Direct proxy entrypoint. If the gateway already attached an ID,
    # logging.WithRequestID preserves it; direct callers get the same header binding.
    replace_exact(proxy_go, HTTP_OLD, HTTP_NEW, 1)

    print(
        "CGQA-GONKA-002 proof patch applied: inbound X-Request-Id is bound at "
        "3 chat HTTP entrypoints; generated-ID fallback remains intact"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gonka_root", type=Path)
    args = parser.parse_args()
    apply(args.gonka_root)


if __name__ == "__main__":
    main()
