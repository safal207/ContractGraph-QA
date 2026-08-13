#!/usr/bin/env python3
"""Build or verify deterministic post-impact control evidence bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.control_bundle import (  # noqa: E402
    create_control_evidence_bundle,
    verify_control_evidence_bundle,
)
from contractgraph_qa.postimpact import load_post_impact_model  # noqa: E402
from contractgraph_qa.product import ProductError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="upgrade a verified reachability bundle v2 to control bundle v3")
    build.add_argument("--base-bundle", required=True, type=Path)
    build.add_argument("--post-impact-model", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)

    verify = sub.add_parser("verify", help="independently verify a control evidence bundle v3")
    verify.add_argument("bundle", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            model = load_post_impact_model(args.post_impact_model)
            result = create_control_evidence_bundle(args.base_bundle, model, args.output)
        else:
            result = verify_control_evidence_bundle(args.bundle)
    except (OSError, ValueError, ProductError) as exc:
        print(f"control-bundle: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
