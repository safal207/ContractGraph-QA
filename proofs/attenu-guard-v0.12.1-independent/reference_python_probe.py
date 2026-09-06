#!/usr/bin/env python3
"""Score exact official v1.2 cases with one extracted Python release.

The replay driver verifies and freezes both the fixture and package bytes, then
passes the selected official case objects over stdin. This probe intentionally
reports observations only; it does not own the before/after expectations.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from typing import Any

import attenu_guard
from attenu_guard import evidence
from attenu_guard.wire import HS256TestSigner


VECTOR_CONTRACT = "bundle_vectors_v1"
VECTOR_REVISION = "bundle_vectors_v1.2"
CASE_CANONICALIZATION = "sorted-key compact JSON UTF-8"


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _observe(case: dict[str, Any]) -> dict[str, Any]:
    signer_config = case.get("signer")
    if not isinstance(signer_config, dict) or signer_config.get("alg") != "HS256":
        raise ValueError(f"{case.get('name')!r}: unsupported signer")
    signer = HS256TestSigner(
        bytes.fromhex(signer_config["secret_hex"]),
        kid=signer_config["kid"],
    )
    report = evidence.verify_bundle(case["bundle"], signer)
    return {
        "name": case["name"],
        "case_sha256": _canonical_sha256(case),
        "bundle_sha256": _canonical_sha256(case["bundle"]),
        "decision": "accept" if report["ok"] else "reject",
        "checks": {
            "anchor": report["checks"]["anchor"],
            "containment": report["checks"]["containment"],
            "integrity": report["checks"]["integrity"],
            "monotonicity": report["checks"]["monotonicity"],
        },
        "failure_details": report["failure_details"],
        "failure_positions": [
            {
                "reason": failure["reason"],
                "seq": failure["seq"],
                "node": failure["node"],
            }
            for failure in report["failure_details"]
        ],
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: reference_python_probe.py EXPECTED_VERSION")
    expected_version = sys.argv[1]
    if attenu_guard.__version__ != expected_version:
        raise RuntimeError(
            f"loaded attenu_guard {attenu_guard.__version__!r}, "
            f"expected {expected_version!r}"
        )

    document = json.load(sys.stdin)
    if not isinstance(document, dict):
        raise ValueError("stdin must contain a JSON object")
    if document.get("version") != VECTOR_CONTRACT:
        raise ValueError("vector contract mismatch")
    if document.get("revision") != VECTOR_REVISION:
        raise ValueError("vector revision mismatch")
    cases = document.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("stdin has no case list")

    output = {
        "implementation": "python",
        "package": "attenu-guard",
        "version": attenu_guard.__version__,
        "runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "platform": sys.platform,
            "machine": platform.machine(),
        },
        "fixture": {
            "contract": document["version"],
            "revision": document["revision"],
            "sha256": document["fixture_sha256"],
        },
        "case_canonicalization": CASE_CANONICALIZATION,
        "cases": [_observe(case) for case in cases],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
