"""CLI entry points for the file-first LiminalQA interchange profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

from contractgraph_qa import legacy_cli
from contractgraph_qa.interop_conformance import run_interop_conformance_suite
from contractgraph_qa.liminalqa_interop import (
    LiminalQaInteropError,
    build_liminalqa_evidence_export,
    canonical_json_bytes,
    import_liminalqa_candidates,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _input_file(path: Path, label: str) -> Path:
    if ".." in path.parts:
        raise LiminalQaInteropError(f"{label} must not contain parent-directory traversal")
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise LiminalQaInteropError(f"{label} must not be a symbolic link")
    resolved = expanded.resolve(strict=True)
    if not resolved.is_file():
        raise LiminalQaInteropError(f"{label} must be a regular file")
    return resolved


def _load_object(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    resolved = _input_file(path, label)
    raw = resolved.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise LiminalQaInteropError(f"{label} is not valid unambiguous JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LiminalQaInteropError(f"{label} must contain one JSON object")
    return value, raw


def _prepare_output(path: Path, inputs: list[Path], force: bool) -> Path:
    if ".." in path.parts:
        raise LiminalQaInteropError("output must not contain parent-directory traversal")
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise LiminalQaInteropError("output must not be a symbolic link")
    resolved = expanded.resolve(strict=False)
    for source in inputs:
        if resolved == source or (resolved.exists() and os.path.samefile(resolved, source)):
            raise LiminalQaInteropError("output must be distinct from every input file")
    if resolved.exists():
        if not resolved.is_file():
            raise LiminalQaInteropError("output must be a regular file")
        if not force:
            raise LiminalQaInteropError(f"output already exists: {resolved}; use --force to replace it")
    return resolved


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(payload)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _run(action: Callable[[], tuple[dict[str, Any], Path]]) -> int:
    try:
        payload, output = action()
        encoded = canonical_json_bytes(payload)
        _atomic_write(output, encoded)
        print(
            json.dumps(
                {
                    "ok": True,
                    "output": str(output),
                    "sha256": hashlib.sha256(encoded + b"\n").hexdigest(),
                },
                sort_keys=True,
            )
        )
        return EXIT_OK
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


def export_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa export-liminalqa",
        description="Export exact-subject bounded CGQA evidence without computing continuity or authorization.",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--repository", required=True, help="Repository URL or stable repository identifier")
    parser.add_argument("--commit-sha", required=True, help="Full lowercase 40-character commit SHA")
    parser.add_argument("--adapter-version", required=True)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--valid-at", required=True, help="RFC 3339 timestamp with explicit offset")
    parser.add_argument("--observed-at", required=True, help="RFC 3339 timestamp with explicit offset")
    parser.add_argument("--recorded-at", required=True, help="RFC 3339 timestamp with explicit offset")
    parser.add_argument("--causal-parent", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    def action() -> tuple[dict[str, Any], Path]:
        manifest_path = _input_file(args.manifest, "manifest")
        result_path = _input_file(args.result, "result")
        manifest, _ = _load_object(manifest_path, "manifest")
        result, _ = _load_object(result_path, "result")
        output = _prepare_output(args.out, [manifest_path, result_path], args.force)
        profile = build_liminalqa_evidence_export(
            manifest,
            result,
            repository=args.repository,
            commit_sha=args.commit_sha,
            adapter_version=args.adapter_version,
            trace_id=args.trace_id,
            operation_id=args.operation_id,
            attempt_id=args.attempt_id,
            valid_at=args.valid_at,
            observed_at=args.observed_at,
            recorded_at=args.recorded_at,
            causal_parents=args.causal_parent,
        )
        return profile, output

    return _run(action)


def import_candidates_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa import-liminalqa-candidates",
        description="Validate LiminalQA candidate seeds without treating them as verified findings.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    def action() -> tuple[dict[str, Any], Path]:
        input_path = _input_file(args.input, "candidate export")
        candidate_export, raw = _load_object(input_path, "candidate export")
        output = _prepare_output(args.out, [input_path], args.force)
        return import_liminalqa_candidates(candidate_export, source_bytes=raw), output

    return _run(action)


def conformance_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa liminalqa-conformance",
        description=(
            "Run the pinned CGQA/LiminalQA golden and fail-closed vectors without "
            "executing candidates or authorizing actions."
        ),
    )
    parser.add_argument(
        "--suite",
        type=Path,
        help="Optional path to an exact byte-for-byte copy of the pinned v0.1 suite",
    )
    args = parser.parse_args(argv)
    try:
        report = run_interop_conformance_suite(args.suite)
        print(canonical_json_bytes(report).decode("utf-8"))
        return EXIT_OK if report["status"] == "PASS" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL
