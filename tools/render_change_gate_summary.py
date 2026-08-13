#!/usr/bin/env python3
"""Render a GitHub-friendly Markdown summary from change-gate JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contractgraph_qa.change_gate_summary import render_change_gate_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Render causal security change-gate Markdown")
    parser.add_argument("--input", type=Path, required=True, help="Change-gate JSON result")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("change-gate result must be a JSON object")
    print(render_change_gate_summary(data), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
