"""CLI for zero-config smart-contract project discovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa.project_quickstart import ProjectQuickstartError, write_quickstart


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cgqa quickstart",
        description=(
            "Detect a smart-contract project, inventory contracts, surface review signals, "
            "and produce a safe starter report. Native project tests run only with --run-native."
        ),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("."),
        help="Project root; defaults to the current directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory; defaults to <target>/.cgqa/quickstart",
    )
    parser.add_argument(
        "--run-native",
        action="store_true",
        help="Run the detected local project test command; never enabled by default",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Native test timeout in seconds (1..3600; default 300)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output directory inside the target project",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = write_quickstart(
            args.target,
            output_directory=args.output_dir,
            run_native=args.run_native,
            force=args.force,
            timeout_seconds=args.timeout,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] != "fail" else 10
    except (ProjectQuickstartError, OSError, ValueError) as exc:
        print(f"cgqa quickstart: {exc}", file=sys.stderr)
        return 10
    except KeyboardInterrupt:
        print("cgqa quickstart: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa quickstart: unexpected error: {exc}", file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
