#!/usr/bin/env python3
"""Run repository-local containment/recovery/verification analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.postimpact import load_post_impact_model, run_post_impact_model  # noqa: E402
from contractgraph_qa.reachability import load_reachability_model, run_reachability_model  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bind a post-impact control graph to a deterministic reachability result."
    )
    parser.add_argument("--reachability-model", type=Path, required=True)
    parser.add_argument("--post-impact-model", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        reachability_model = load_reachability_model(args.reachability_model.resolve())
        reachability_result = run_reachability_model(reachability_model)
        post_impact_model = load_post_impact_model(args.post_impact_model.resolve())
        result = run_post_impact_model(post_impact_model, reachability_model, reachability_result)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"post-impact: {exc}", file=sys.stderr)
        return 10

    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
