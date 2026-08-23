"""CLI for source-bound Solidity mutation acquisition through Foundry."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.mutation_acquisition import load_mutation_plan, run_mutation_acquisition

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-mutation-run",
        description=(
            "Apply source-bound reviewed Solidity mutations in isolated project copies, run exact Foundry "
            "test selectors, and feed the outcomes into CGQ-SPEC-001."
        ),
    )
    parser.add_argument("--plan", type=Path, required=True, help="Solidity mutation plan v0.1 JSON")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Foundry project root")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for mutants and evidence JSON")
    args = parser.parse_args(argv)

    if shutil.which("forge") is None:
        print("cgqa-mutation-run: forge executable not found", file=sys.stderr)
        return EXIT_VALIDATION

    try:
        result = run_mutation_acquisition(
            load_mutation_plan(args.plan.resolve()),
            args.project_root.resolve(),
            output_dir=args.output_dir.resolve(),
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        spec = result.get("specAssurance")
        spec_status = spec.get("status") if isinstance(spec, dict) else None
        return EXIT_OK if result.get("status") == "pass" and spec_status == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-mutation-run: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-mutation-run: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-mutation-run: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
