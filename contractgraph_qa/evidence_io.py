"""Publish complete evidence files, preserving existing files unless requested."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, rendered: str, *, force: bool = False) -> None:
    """Write UTF-8 JSON without exposing partial output or silently replacing it.

    No-force publication uses a hard link in the same directory: creation either
    succeeds or reports an existing destination atomically. Filesystems without
    hard-link support fail rather than falling back to a replacing write.
    Callers must separately reject output paths that alias their input files.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        if force:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise FileExistsError(
                    f"output already exists: {path}; pass --force to replace it"
                ) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
