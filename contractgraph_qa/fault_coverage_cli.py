"""CLI for evidence-bound fault coverage matrices."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.fault_coverage import (
    build_fault_coverage_matrix,
    load_json_object,
    render_fault_coverage_markdown,
)

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-fault-coverage",
        description="Bind mutation generation to execution evidence and render per-fault-class coverage.",
    )
    parser.add_argument("--generation", type=Path, required=True, help="fault-generation-result.json")
    parser.add_argument("--execution", type=Path, required=True, help="mutation-execution-result.json")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument("--markdown", type=Path, help="Optional Markdown report path")
    args = parser.parse_args(argv)

    try:
        generation = load_json_object(args.generation.resolve())
        execution = load_json_object(args.execution.resolve())
        result = build_fault_coverage_matrix(generation, execution)

        if args.output is not None:
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        if args.markdown is not None:
            markdown = args.markdown.resolve()
            markdown.parent.mkdir(parents=True, exist_ok=True)
            markdown.write_text(render_fault_coverage_markdown(result), encoding="utf-8")

        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-fault-coverage: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-fault-coverage: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"cgqa-fault-coverage: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
