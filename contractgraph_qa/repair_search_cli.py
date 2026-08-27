"""CLI for deterministic minimal verified repair selection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.repair_search import load_repair_search_model, run_repair_search_model

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-repair-search",
        description=(
            "Select the minimum repair-count candidate set that repairs all declared "
            "targets without regressing supplied comparable evidence."
        ),
    )
    parser.add_argument("--model", type=Path, required=True, help="Repair search v0.1 model JSON")
    args = parser.parse_args(argv)

    try:
        result = run_repair_search_model(load_repair_search_model(args.model.resolve()))
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-repair-search: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-repair-search: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"cgqa-repair-search: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
