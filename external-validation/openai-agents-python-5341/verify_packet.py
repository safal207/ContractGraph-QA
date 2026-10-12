#!/usr/bin/env python3
"""Check packet bytes against its manifest; not an authenticity verifier."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def verify(root: Path) -> list[str]:
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if data.get("schema") != "sdk-5341-packet-manifest/1":
        raise ValueError("unsupported manifest")
    errors = []
    seen = set()
    for entry in data["files"]:
        relative = entry["path"]
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError("invalid or duplicate manifest path")
        seen.add(relative)
        target = root / relative
        if not target.is_file() or target.is_symlink():
            errors.append(f"missing/nonregular: {relative}")
            continue
        content = target.read_bytes()
        if len(content) != entry["size_bytes"]:
            errors.append(f"size mismatch: {relative}")
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            errors.append(f"sha256 mismatch: {relative}")
    return errors


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    errors = verify(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        raise SystemExit(1)
    print("Packet files match the manifest. This does not prove authenticity.")
