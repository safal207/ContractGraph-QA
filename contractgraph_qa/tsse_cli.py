"""CLI for deterministic Time-Space-State-Environment trace verification."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from contractgraph_qa.tsse import load_tsse_model, run_tsse_model

EXIT_OK = 0
EXIT_HOLD = 1
EXIT_VALIDATION = 2
EXIT_INTERNAL = 70


def _parser(prog: str = "cgqa-tsse") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Verify a saved Time-Space-State-Environment state-machine trace "
            "deterministically. This command does not scan or execute a target."
        ),
    )
    parser.add_argument(
        "--model",
        type=Path,
        required=True,
        help="TSSE model JSON to verify",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional UTF-8 JSON result path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output file (never the input model)",
    )
    return parser


def _stable_json(data: dict[str, object]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _write_atomic(output: Path, rendered: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def main(argv: list[str] | None = None, *, prog: str = "cgqa-tsse") -> int:
    try:
        args = _parser(prog).parse_args(argv)
    except SystemExit as exc:
        return EXIT_OK if int(exc.code or 0) == 0 else EXIT_VALIDATION

    try:
        model_path = args.model.resolve()
        result = run_tsse_model(load_tsse_model(model_path))
        rendered = _stable_json(result)

        if args.output is not None:
            output = args.output.resolve()
            aliases_input = output == model_path or (
                output.exists() and output.samefile(model_path)
            )
            if aliases_input:
                raise ValueError("--output must not overwrite the input model")
            if output.exists() and not args.force:
                raise ValueError("--output already exists; pass --force to replace it")
            _write_atomic(output, rendered)

        print(rendered, end="")
        return EXIT_OK if result.get("status") == "pass" else EXIT_HOLD
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-tsse: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-tsse: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-tsse: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
