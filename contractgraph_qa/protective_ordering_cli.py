"""CLI for CGQ-RACE-001 protective ordering verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.protective_ordering import (
    load_protective_ordering_model,
    run_protective_ordering_model,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-race",
        description=(
            "Verify CGQ-RACE-001: a declared protective action must not lose its "
            "business effect solely because a competing legal transition is ordered first."
        ),
    )
    parser.add_argument("--model", type=Path, required=True, help="Protective ordering model v0.1 JSON")
    args = parser.parse_args(argv)

    try:
        result = run_protective_ordering_model(load_protective_ordering_model(args.model.resolve()))
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"cgqa-race: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-race: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-race: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
