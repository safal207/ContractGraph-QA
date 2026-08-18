#!/usr/bin/env python3
"""Apply the CGQA-GONKA-001 proof-of-fix patch to a pinned Gonka proxy.go.

This is a local verification patch only. It deliberately preserves the existing
background execution / post-disconnect drain semantics while propagating the
HTTP request identity into the detached RunInference context.
"""

from __future__ import annotations

import argparse
from pathlib import Path

IMPORT_ANCHOR = '\t"devshard/state"\n'
IMPORT_REPLACEMENT = '\t"devshard/logging"\n\t"devshard/state"\n'
CALL_ANCHOR = "RunInference(context.Background(), params,"
CALL_REPLACEMENT = "RunInference(logging.PropagateRequestID(context.Background(), r.Context()), params,"
EXPECTED_CALL_REPLACEMENTS = 2  # streaming + non-streaming


def apply(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    if '"devshard/logging"' in text or CALL_REPLACEMENT in text:
        raise SystemExit("proof patch appears to be already applied; refusing ambiguous state")

    import_count = text.count(IMPORT_ANCHOR)
    call_count = text.count(CALL_ANCHOR)
    if import_count != 1:
        raise SystemExit(f"expected exactly one import anchor, found {import_count}")
    if call_count != EXPECTED_CALL_REPLACEMENTS:
        raise SystemExit(
            f"expected {EXPECTED_CALL_REPLACEMENTS} detached RunInference call sites, found {call_count}"
        )

    patched = text.replace(IMPORT_ANCHOR, IMPORT_REPLACEMENT, 1)
    patched = patched.replace(CALL_ANCHOR, CALL_REPLACEMENT)

    if patched.count(CALL_ANCHOR) != 0:
        raise SystemExit("unpatched detached RunInference call remains")
    if patched.count(CALL_REPLACEMENT) != EXPECTED_CALL_REPLACEMENTS:
        raise SystemExit("patched RunInference call count is not exact")

    path.write_text(patched, encoding="utf-8")
    print(
        "CGQA-GONKA-001 proof patch applied: detached background execution preserved; "
        "request identity propagated at 2 RunInference call sites"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("proxy_go", type=Path)
    args = parser.parse_args()
    apply(args.proxy_go)


if __name__ == "__main__":
    main()
