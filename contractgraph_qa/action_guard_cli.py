"""CLI for deterministic agent-action authorization and control checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from contractgraph_qa.action_guard import evaluate_action_guard, load_action_guard


EXIT_PASS = 0
EXIT_HOLD = 1
EXIT_FAIL = 2
EXIT_VALIDATION = 3
EXIT_INTERNAL = 70


def _parser(prog: str = "cgqa-action-guard") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Compare declared agent actions with an exact-subject authorization "
            "envelope, independent monitor decisions, canaries, and evidence."
        ),
    )
    parser.add_argument("--input", type=Path, required=True, help="Action Guard v0.1 JSON")
    parser.add_argument("--output", type=Path, help="Optional result JSON destination")
    parser.add_argument("--force", action="store_true", help="Replace an existing output")
    return parser


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _same_path(left: Path, right: Path) -> bool:
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and left.samefile(right)
    except OSError:
        return False


def _write_atomic(path: Path, rendered: str) -> None:
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
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: list[str] | None = None, *, prog: str = "cgqa-action-guard") -> int:
    try:
        args = _parser(prog).parse_args(argv)
    except SystemExit as exc:
        return EXIT_PASS if int(exc.code or 0) == 0 else EXIT_VALIDATION

    try:
        input_path = args.input.resolve()
        output_path = None if args.output is None else args.output.resolve()
        if output_path is not None:
            if _same_path(input_path, output_path):
                raise ValueError("--output must not overwrite the input")
            if output_path.exists() and not args.force:
                raise ValueError("--output already exists; pass --force to replace it")

        result = evaluate_action_guard(load_action_guard(input_path))
        rendered = _stable_json(result)
        if output_path is not None:
            _write_atomic(output_path, rendered)
        print(rendered, end="")

        status = result.get("status")
        if status == "pass":
            return EXIT_PASS
        if status == "hold":
            return EXIT_HOLD
        return EXIT_FAIL
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print(f"{prog}: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"{prog}: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
