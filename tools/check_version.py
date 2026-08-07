#!/usr/bin/env python3
"""Verify ContractGraph-QA product version consistency."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
PACKAGE_VERSION = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE)


def _package_version() -> str:
    source = (ROOT / "contractgraph_qa/__init__.py").read_text(encoding="utf-8")
    match = PACKAGE_VERSION.search(source)
    if match is None:
        raise SystemExit("contractgraph_qa.__version__ not found")
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Optional git tag, expected as v<version>")
    args = parser.parse_args()

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]
    package_version = _package_version()
    if not isinstance(project_version, str) or not SEMVER.fullmatch(project_version):
        raise SystemExit("pyproject project.version is not valid SemVer")
    if project_version != package_version:
        raise SystemExit(
            f"version mismatch: pyproject={project_version} package={package_version}"
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
