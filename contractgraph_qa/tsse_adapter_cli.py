"""CLI for fail-closed scanner evidence import into TSSE."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from contractgraph_qa.tsse_adapters import (
    adapt_tool_capture,
    load_tool_capture,
    load_tool_profile,
)


EXIT_OK = 0
EXIT_HOLD = 1
EXIT_VALIDATION = 2
EXIT_INTERNAL = 70


def _parser(prog: str = "cgqa-tsse-adapt") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Verify a reviewed Cargo/Soroban, Foundry, Echidna, Medusa, or Slither evidence capture "
            "and project eligible dynamic traces into TSSE."
        ),
    )
    parser.add_argument(
        "--capture",
        type=Path,
        required=True,
        help="Reviewed TSSE tool capture JSON",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        required=True,
        help="Separately reviewed TSSE tool policy/subject profile JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional UTF-8 JSON adapter-result path",
    )
    parser.add_argument(
        "--model-out",
        type=Path,
        help="Optional TSSE model destination; requires --output (dynamic traces only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing output files without replacing capture/evidence inputs",
    )
    return parser


def _stable_json(data: object) -> str:
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


def _same_path(left: Path, right: Path) -> bool:
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and left.samefile(right)
    except OSError:
        return False


def _protected_paths(capture_path: Path, capture: dict[str, Any]) -> list[Path]:
    protected = [capture_path]
    subject = capture.get("subject")
    if isinstance(subject, dict):
        artifacts = subject.get("artifacts")
        if isinstance(artifacts, list):
            for item in artifacts:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    protected.append((capture_path.parent / item["path"]).resolve())
    artifacts = capture.get("toolArtifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                protected.append((capture_path.parent / item["path"]).resolve())
    return protected


def _preflight_output(
    output: Path,
    *,
    protected: list[Path],
    other_outputs: list[Path],
    force: bool,
    option: str,
) -> None:
    if any(_same_path(output, item) for item in protected):
        raise ValueError(f"{option} must not overwrite the capture or a bound artifact")
    if any(_same_path(output, item) for item in other_outputs):
        raise ValueError("--output and --model-out must identify different files")
    if output.exists() and not force:
        raise ValueError(f"{option} already exists; pass --force to replace it")


def main(argv: list[str] | None = None, *, prog: str = "cgqa-tsse-adapt") -> int:
    try:
        args = _parser(prog).parse_args(argv)
    except SystemExit as exc:
        return EXIT_OK if int(exc.code or 0) == 0 else EXIT_VALIDATION

    try:
        capture_path = args.capture.resolve()
        profile_path = args.profile.resolve()
        capture = load_tool_capture(capture_path)
        profile = load_tool_profile(profile_path)
        protected = [
            *_protected_paths(capture_path, capture),
            *_protected_paths(profile_path, profile),
        ]

        result_output = None if args.output is None else args.output.resolve()
        model_output = None if args.model_out is None else args.model_out.resolve()
        if model_output is not None and result_output is None:
            raise ValueError("--model-out requires a companion --output adapter receipt")
        if result_output is not None:
            _preflight_output(
                result_output,
                protected=protected,
                other_outputs=[] if model_output is None else [model_output],
                force=args.force,
                option="--output",
            )
        if model_output is not None:
            _preflight_output(
                model_output,
                protected=protected,
                other_outputs=[] if result_output is None else [result_output],
                force=args.force,
                option="--model-out",
            )

        result = adapt_tool_capture(
            capture,
            capture_path.parent,
            profile,
            profile_path.parent,
            capture_path=capture_path,
            profile_path=profile_path,
        )
        model = result.get("tsseModel")
        if model_output is not None and not isinstance(model, dict):
            raise ValueError("--model-out requires a dynamic Cargo/Soroban/Foundry/Echidna/Medusa trace")

        rendered = _stable_json(result)
        if result_output is not None:
            _write_atomic(result_output, rendered)
        if model_output is not None:
            _write_atomic(model_output, _stable_json(model))

        print(rendered, end="")
        return EXIT_OK if result.get("status") == "ready" else EXIT_HOLD
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
