"""CLI for deterministic reviewed repair comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.causal_repair import load_causal_repair_model, run_causal_repair_model

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-causal-repair",
        description=(
            "Compare reviewed baseline/candidate invariant evidence and verify that "
            "declared target failures are repaired without regressing declared guards."
        ),
    )
    parser.add_argument("--model", type=Path, required=True, help="Causal repair v0.1 model JSON")
    args = parser.parse_args(argv)

    try:
        result = run_causal_repair_model(load_causal_repair_model(args.model.resolve()))
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-causal-repair: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-causal-repair: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-causal-repair: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
