"""One-command Solidity + runtime hydrated lattice verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.execution_trace import load_execution_trace
from contractgraph_qa.hydrated_lattice import load_hydration_bindings, run_hydrated_lattice
from contractgraph_qa.solidity_lattice import check_target, load_profile

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-hydrated",
        description=(
            "Compile Solidity to a static Contract Lattice template, hydrate it with a "
            "normalized execution trace and reviewed authority/time bindings, then run "
            "lifecycle, replay, successor and static/runtime conformance checks."
        ),
    )
    parser.add_argument("--target", required=True, help="Foundry target <source.sol>:<Contract>")
    parser.add_argument("--profile", type=Path, required=True, help="Reviewed Solidity lattice profile JSON")
    parser.add_argument("--trace", type=Path, required=True, help="Normalized execution trace v0.1 JSON")
    parser.add_argument("--bindings", type=Path, required=True, help="Hydration bindings v0.1 JSON")
    parser.add_argument("--root", type=Path, help="Optional Foundry project root")
    args = parser.parse_args(argv)

    try:
        root = None if args.root is None else args.root.resolve()
        static_result = check_target(args.target, load_profile(args.profile.resolve()), root)
        result = run_hydrated_lattice(
            static_result,
            load_execution_trace(args.trace.resolve()),
            load_hydration_bindings(args.bindings.resolve()),
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-hydrated: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-hydrated: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-hydrated: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
