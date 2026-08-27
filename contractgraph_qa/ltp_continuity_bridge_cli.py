"""CLI for deterministic ContractGraph-QA -> LTP continuity export."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from contractgraph_qa import legacy_cli
from contractgraph_qa.ltp_continuity_bridge import (
    ContinuityBridgeError,
    build_ltp_continuity_export,
    canonical_json_bytes,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


class DuplicateJsonKeyError(ValueError):
    pass


class NonFiniteJsonNumberError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_finite_number(value: str) -> None:
    raise NonFiniteJsonNumberError(
        f"non-finite JSON number is not allowed: {value}"
    )


def _reject_parent_traversal(path: Path, label: str) -> None:
    if ".." in path.parts:
        raise ContinuityBridgeError(
            f"{label} must not contain parent-directory traversal"
        )


def _input_path(path: Path, label: str) -> Path:
    _reject_parent_traversal(path, label)
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ContinuityBridgeError(f"{label} must not be a symbolic link")
    resolved = expanded.resolve(strict=True)
    if not resolved.is_file():
        raise ContinuityBridgeError(f"{label} must be a regular file: {resolved}")
    return resolved


def _load_json(path: Path, label: str) -> object:
    resolved = _input_path(path, label)
    try:
        return json.loads(
            resolved.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_number,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
        NonFiniteJsonNumberError,
    ) as exc:
        raise ContinuityBridgeError(f"{label} is not valid unambiguous JSON: {exc}") from exc


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = _load_json(path, label)
    if not isinstance(value, dict):
        raise ContinuityBridgeError(f"{label} must contain one JSON object")
    return value


def _load_observations(path: Path) -> list[dict[str, Any]]:
    value = _load_json(path, "observations")
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict) and value.get("schemaVersion") == "cgqa-external-observations-v0.1":
        extras = sorted(set(value) - {"schemaVersion", "observations"})
        if extras:
            raise ContinuityBridgeError(
                "observations wrapper contains unexpected fields: " + ", ".join(extras)
            )
        rows = value.get("observations")
        if not isinstance(rows, list):
            raise ContinuityBridgeError("observations wrapper.observations must be an array")
    elif isinstance(value, dict):
        rows = [value]
    else:
        raise ContinuityBridgeError("observations must be one object, an array, or the v0.1 wrapper")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContinuityBridgeError(f"observations[{index}] must be an object")
    return rows


def _same_existing_file(left: Path, right: Path) -> bool:
    if left.resolve(strict=False) == right.resolve(strict=False):
        return True
    if not left.exists() or not right.exists():
        return False
    try:
        return os.path.samefile(left, right)
    except OSError as exc:
        raise ContinuityBridgeError(f"could not compare path identity safely: {exc}") from exc


def _validate_output_targets(
    *,
    inputs: list[Path],
    outputs: list[Path],
    force: bool,
) -> list[Path]:
    resolved_outputs = [path.expanduser().resolve(strict=False) for path in outputs]
    for index, output in enumerate(outputs):
        _reject_parent_traversal(output, "output")
        if output.expanduser().is_symlink():
            raise ContinuityBridgeError(f"output must not be a symbolic link: {output}")
        resolved = resolved_outputs[index]
        for source in inputs:
            if _same_existing_file(source, resolved):
                raise ContinuityBridgeError("output path must be distinct from every input file")
        for prior_index in range(index):
            if _same_existing_file(resolved_outputs[prior_index], resolved):
                raise ContinuityBridgeError("continuity output and bridge report output must be distinct")
        if resolved.exists():
            if not resolved.is_file():
                raise ContinuityBridgeError(f"output target must be a regular file: {resolved}")
            if not force:
                raise ContinuityBridgeError(
                    f"output already exists: {resolved}; use --force to replace it"
                )
    return resolved_outputs


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
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cgqa continuity-export",
        description=(
            "Project reviewed smart-contract evidence into the pinned LTP v0.1 "
            "request/outcome input contract without computing a continuity verdict."
        ),
    )
    parser.add_argument(
        "--intent",
        type=Path,
        action="append",
        required=True,
        help="Smart Contract Intent v0.1 JSON; repeat for retry attempts",
    )
    parser.add_argument(
        "--capture",
        type=Path,
        action="append",
        default=[],
        help="RPC capture result v0.1 JSON; repeat for distinct transaction attempts",
    )
    parser.add_argument(
        "--receipt-trace",
        type=Path,
        action="append",
        default=[],
        help="EVM receipt adapter result v0.1 JSON; repeat for distinct transactions",
    )
    parser.add_argument(
        "--observations",
        type=Path,
        action="append",
        default=[],
        help="External Observation v0.1 JSON, array, or wrapper; repeat as needed",
    )
    parser.add_argument("--as-of", required=True, help="Bounded snapshot time with explicit UTC offset")
    parser.add_argument("--out", type=Path, required=True, help="Destination LTP input JSON")
    parser.add_argument(
        "--bridge-report-out",
        type=Path,
        help="Optional destination for the non-verdict bridge provenance report",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing regular output files after identity checks",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    try:
        all_input_args = [
            *args.intent,
            *args.capture,
            *args.receipt_trace,
            *args.observations,
        ]
        input_paths = [
            _input_path(path, f"input[{index}]")
            for index, path in enumerate(all_input_args)
        ]
        output_args = [args.out]
        if args.bridge_report_out is not None:
            output_args.append(args.bridge_report_out)
        output_paths = _validate_output_targets(
            inputs=input_paths,
            outputs=output_args,
            force=args.force,
        )

        intents = [_load_object(path, "intent") for path in args.intent]
        captures = [_load_object(path, "capture") for path in args.capture]
        traces = [_load_object(path, "receipt trace") for path in args.receipt_trace]
        observations = [
            row
            for path in args.observations
            for row in _load_observations(path)
        ]
        ltp_input, bridge_report = build_ltp_continuity_export(
            intents=intents,
            captures=captures,
            receipt_traces=traces,
            observations=observations,
            as_of=args.as_of,
        )

        _atomic_write(output_paths[0], canonical_json_bytes(ltp_input))
        if args.bridge_report_out is not None:
            _atomic_write(output_paths[1], canonical_json_bytes(bridge_report))
        print(canonical_json_bytes(bridge_report).decode("utf-8"), end="")
        return EXIT_OK
    except (ContinuityBridgeError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"cgqa continuity-export: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa continuity-export: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"cgqa continuity-export: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
