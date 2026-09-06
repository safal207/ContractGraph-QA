#!/usr/bin/env python3
"""Run the envelope-v1.1 scorer against the exact published source copies.

The cryptographic and semantic checks live in ``verify_envelope_vectors.py``.
This small runner binds those checks to the actual distribution topology:

- the Python repository at one exact commit;
- the PyPI wheel for ``attenu-guard==0.13.0``;
- the TypeScript repository at the commit behind release ``v0.8.0``.

The npm tarball is deliberately not treated as a vector source because that
package publishes runtime files, not the raw interoperability fixture.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

TYPESCRIPT_REPOSITORY = "attenu-io/attenu-guard-ts"
TYPESCRIPT_COMMIT = "51eebfc957c47aeba3738e5f1f67e8d3d55da50f"
TYPESCRIPT_RELEASE = "v0.8.0"
TYPESCRIPT_VECTOR_PATH = "test/fixtures/vectors/envelopes/envelope_vectors_v1.json"
TYPESCRIPT_SOURCE = (
    f"{TYPESCRIPT_REPOSITORY}@{TYPESCRIPT_COMMIT}:{TYPESCRIPT_VECTOR_PATH}"
)
OLD_PROOF_TEXT = "byte identity of repository, PyPI, and npm vector copies"
NEW_PROOF_TEXT = (
    "byte identity of Python repository, PyPI wheel, and TypeScript "
    "repository vector copies"
)


def _load_core() -> Any:
    path = Path(__file__).with_name("verify_envelope_vectors.py")
    spec = importlib.util.spec_from_file_location("cgqa_envelope_v11_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load core verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", required=True, type=Path)
    parser.add_argument("--python-vector", required=True, type=Path)
    parser.add_argument("--typescript-vector", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()

    core = _load_core()
    try:
        report, errors = core.build_report(
            args.vectors,
            args.python_vector,
            args.typescript_vector,
        )

        copies = report.get("subject", {}).get("source_copies")
        if not isinstance(copies, list) or len(copies) != 3:
            errors.append(
                "source topology mismatch: expected repository, PyPI, and "
                "TypeScript repository copies"
            )
        else:
            copies[2]["source"] = TYPESCRIPT_SOURCE

        proved = report.get("claim_boundary", {}).get("proved")
        if not isinstance(proved, list) or OLD_PROOF_TEXT not in proved:
            errors.append("core report no longer exposes the expected source-copy claim")
        else:
            proved[proved.index(OLD_PROOF_TEXT)] = NEW_PROOF_TEXT

        errors = [
            error.replace("npm attenu-guard@0.8.0", TYPESCRIPT_SOURCE)
            for error in errors
        ]
        report["summary"]["overall"] = "AGREE" if not errors else "DISAGREE"
        core.write_json(args.json_out, report)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report["summary"], sort_keys=True))
    if errors:
        for error in errors:
            print(f"DISAGREE: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
