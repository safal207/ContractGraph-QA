#!/usr/bin/env python3
"""Verify packet membership and bytes; this does not authenticate observations."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text())
expected = set()
for item in manifest["artifacts"]:
    path = Path(item["path"])
    if path.is_absolute() or ".." in path.parts or path.as_posix() in expected:
        raise SystemExit("Invalid or duplicate artifact path")
    expected.add(path.as_posix())
    target = root / path
    if (not target.resolve().is_relative_to(root) or
            any(parent.is_symlink() for parent in [target, *target.parents] if parent != root) or
            not target.is_file()):
        raise SystemExit(f"Missing or symbolic artifact: {path}")
    data = target.read_bytes()
    if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit(f"Artifact mismatch: {path}")
members = list(root.rglob("*"))
if any(p.is_symlink() for p in members):
    raise SystemExit("Symbolic packet member")
observed = {p.relative_to(root).as_posix() for p in members if p.is_file()}
if observed != expected | {"manifest.json"}:
    raise SystemExit("Closed packet membership mismatch")
for item in manifest["repository_sources"]:
    path = Path(item["path"])
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit("Invalid repository source path")
    target = root.parents[1] / path
    if (not target.resolve().is_relative_to(root.parents[1]) or
            any(parent.is_symlink() for parent in [target, *target.parents])):
        raise SystemExit("Symbolic repository source")
    data = target.read_bytes()
    if target.is_symlink() or len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit(f"Repository source mismatch: {path}")
print(f"VERIFIED: {len(expected)} artifacts and {len(manifest['repository_sources'])} repository sources")
