"""CLI for deterministic idea/plan/fact graph comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contractgraph_qa.graph_layers import compare_graph_layers


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cgqa-graph-layers",
        description="Compare a declared idea/plan graph with observed fact edges.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Graph-layer JSON")
    parser.add_argument("--output", type=Path, help="Optional diff JSON destination")
    parser.add_argument("--force", action="store_true", help="Replace an existing output")
    return parser


def _stable(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as handle:
            result = compare_graph_layers(json.load(handle))
        rendered = _stable(result)
        if args.output is not None:
            if args.output.exists() and not args.force:
                raise ValueError(f"output already exists: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _parser().error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
