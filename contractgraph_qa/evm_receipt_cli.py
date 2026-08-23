"""CLI for reviewed raw EVM receipt -> ExecutionTrace normalization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.evm_receipt_adapter import adapt_receipt_files

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-evm-receipt",
        description=(
            "Normalize one raw JSON-RPC EVM transaction receipt into ExecutionTrace "
            "using an exact reviewed topic/address/word mapping profile."
        ),
    )
    parser.add_argument("--receipt", type=Path, required=True, help="Raw JSON-RPC receipt JSON")
    parser.add_argument("--profile", type=Path, required=True, help="Reviewed EVM receipt profile JSON")
    parser.add_argument(
        "--trace-out",
        type=Path,
        help="Optional destination for the normalized ExecutionTrace JSON only",
    )
    args = parser.parse_args(argv)

    try:
        result = adapt_receipt_files(args.receipt.resolve(), args.profile.resolve())
        if args.trace_out is not None:
            _write_json(args.trace_out.resolve(), result["executionTrace"])
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"cgqa: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
