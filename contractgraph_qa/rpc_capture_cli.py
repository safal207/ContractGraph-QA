"""CLI for immutable JSON-RPC transaction capture."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.rpc_capture import capture_transaction, write_capture_result

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _rpc_url(cli_value: str | None) -> str:
    value = cli_value or os.environ.get("CGQA_RPC_URL")
    if value is None or not value.strip():
        raise ValueError("RPC URL is required via --rpc-url or CGQA_RPC_URL")
    return value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-rpc-capture",
        description=(
            "Capture eth_chainId, eth_getTransactionReceipt, the containing block witness, "
            "and observed head without persisting the RPC endpoint or credentials."
        ),
    )
    parser.add_argument("--tx-hash", required=True, help="32-byte transaction hash")
    parser.add_argument(
        "--rpc-url",
        help="JSON-RPC endpoint; prefer CGQA_RPC_URL to avoid shell-history exposure",
    )
    parser.add_argument("--output", type=Path, help="Optional path for canonical capture result JSON")
    args = parser.parse_args(argv)

    try:
        result = capture_transaction(_rpc_url(args.rpc_url), args.tx_hash)
        if args.output is not None:
            write_capture_result(args.output.resolve(), result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"cgqa-rpc-capture: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-rpc-capture: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-rpc-capture: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
