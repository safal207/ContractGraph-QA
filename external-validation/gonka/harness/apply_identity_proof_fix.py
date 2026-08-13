#!/usr/bin/env python3
"""Apply the CGQA-GONKA-001 proof-of-fix to a pinned Gonka checkout.

This is intentionally not an upstream patch. It changes only request-ID
propagation into the detached background inference context while preserving
HTTP cancellation detachment/post-disconnect protocol completion.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply_identity_proof_fix.py <proxy.go>")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

import_anchor = '\t"devshard/state"\n'
import_replacement = '\t"devshard/logging"\n\t"devshard/state"\n'
if '"devshard/logging"' not in text:
    if text.count(import_anchor) != 1:
        raise SystemExit("expected exactly one devshard/state import anchor")
    text = text.replace(import_anchor, import_replacement, 1)

replacements = {
    '\terr := p.redundancy.RunInference(context.Background(), params, dw, flag)\n':
        '\trunCtx := logging.PropagateRequestID(context.Background(), r.Context())\n'
        '\terr := p.redundancy.RunInference(runCtx, params, dw, flag)\n',
    '\terr := p.redundancy.RunInference(context.Background(), params, &buf, flag)\n':
        '\trunCtx := logging.PropagateRequestID(context.Background(), r.Context())\n'
        '\terr := p.redundancy.RunInference(runCtx, params, &buf, flag)\n',
}

for old, new in replacements.items():
    if old not in text:
        if new in text:
            continue
        raise SystemExit(f"expected proof-fix source anchor not found: {old.strip()}")
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one proof-fix source anchor: {old.strip()}")
    text = text.replace(old, new, 1)

if text.count('logging.PropagateRequestID(context.Background(), r.Context())') != 2:
    raise SystemExit("proof-fix must propagate request identity at exactly two inference entry points")
if 'RunInference(context.Background(), params' in text:
    raise SystemExit("unpatched detached RunInference call remains")

path.write_text(text, encoding="utf-8")
print(f"applied CGQA-GONKA-001 proof-of-fix to {path}")
