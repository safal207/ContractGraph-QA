#!/usr/bin/env python3
"""Verify ContractGraph-QA product version consistency."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

from contractgraph_qa import __version__

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional git tag, expected as v<version>")
    args = parser.parse_args()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    if not isinstance(project_version, str) or not SEMVER.fullmatch(project_version):
        raise SystemExit("pyproject project.version is not valid SemVer")
    if project_version != __version__:
        raise SystemExit(
            f"version mismatch: pyproject={project_version} package={__version__}"
        )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {project_version} " not in changelog:
        raise SystemExit(f"CHANGELOG.md has no release heading for {project_version}")

    if args.tag is not None and args.tag != f"v{project_version}":
        raise SystemExit(f"tag mismatch: expected v{project_version}, got {args.tag}")

    print(project_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
