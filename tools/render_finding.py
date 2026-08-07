#!/usr/bin/env python3
"""Render a deterministic client-facing Markdown finding from ContractGraph-QA JSON evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from contractgraph_qa.report import load_finding, render_markdown, validate_finding

__all__ = ["load_finding", "render_markdown", "validate_finding"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Finding JSON file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="Write rendered Markdown")
    group.add_argument("--check", type=Path, help="Compare rendering with an existing Markdown file")
    args = parser.parse_args()

    rendered = render_markdown(load_finding(args.input))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        return 0

    expected = args.check.read_text(encoding="utf-8")
    if expected != rendered:
        raise SystemExit(f"rendered report differs from {args.check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
