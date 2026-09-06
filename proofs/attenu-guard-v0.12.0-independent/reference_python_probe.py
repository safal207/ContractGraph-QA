#!/usr/bin/env python3
"""Probe the released Python package at the bundle-verifier defect boundary.

The caller supplies the expected package version and controls which package is
imported through ``PYTHONPATH``.  This file intentionally reports observations
only; ``replay_reference_releases.py`` owns the before/after expectations.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from typing import Any

import attenu_guard
from attenu_guard import Authority, Guard, RowLimit, evidence
from attenu_guard.audit import AuditLog, GENESIS, _hash as entry_hash
from attenu_guard.wire import HS256TestSigner


SIGNER = HS256TestSigner(b"k", kid="k")
DEFECT_CASES = {
    "increased_ttl",
    "loosened_ceiling",
    "unbounded_ttl",
    "dropped_ceiling",
}
FIXED_PARAMS_SALT_HEX = "00" * 16
BUNDLE_CANONICALIZATION = "sorted-key compact JSON UTF-8"


def _index_of(bundle: dict[str, Any], event: str) -> int:
    for index, entry in enumerate(bundle["entries"]):
        if entry.get("event") == event:
            return index
    raise AssertionError(f"no {event!r} entry")


def _rehash_and_reanchor(bundle: dict[str, Any]) -> None:
    previous = GENESIS
    for entry in bundle["entries"]:
        entry["prev_hash"] = previous
        payload = {key: value for key, value in entry.items() if key != "hash"}
        entry["hash"] = entry_hash(previous, payload)
        previous = entry["hash"]

    anchor = evidence._anchor_for(bundle["entries"], SIGNER, 0)
    anchor["verified"] = AuditLog.verify_anchor(bundle["entries"], anchor, SIGNER)[0]
    bundle["anchor"] = anchor


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bundle(granted: dict[str, Any]) -> dict[str, Any]:
    parent = Authority(
        {"crm.read", "mail.send"},
        [RowLimit(100)],
        ttl=3600,
    )
    root = Guard.issue(
        "orchestrator",
        parent,
        chain_id="t",
        schema_version=2,
    )
    child = root.delegate(
        "summarizer",
        Authority({"crm.read"}, [RowLimit(50)], ttl=900),
        task="summarize",
    )
    child.complete()
    root.complete()
    bundle = evidence.export_bundle(root.audit_log(), SIGNER)
    bundle["entries"][_index_of(bundle, "root")]["params_salt"] = (
        FIXED_PARAMS_SALT_HEX
    )
    bundle["entries"][_index_of(bundle, "spawn")]["granted"] = granted
    _rehash_and_reanchor(bundle)
    return bundle


def _granted(
    *,
    scopes: tuple[str, ...] = ("crm.read",),
    max_rows: int | None = 50,
    ttl: int | None = 900,
) -> dict[str, Any]:
    constraints = [] if max_rows is None else [{"key": "max_rows", "max": max_rows}]
    return {"scopes": list(scopes), "constraints": constraints, "ttl": ttl}


def _observe(name: str, granted: dict[str, Any]) -> dict[str, Any]:
    bundle = _bundle(granted)
    report = evidence.verify_bundle(bundle, SIGNER)
    return {
        "name": name,
        "bundle_sha256": _canonical_sha256(bundle),
        "decision": "accept" if report["ok"] else "reject",
        "checks": {
            "anchor": report["checks"]["anchor"],
            "containment": report["checks"]["containment"],
            "integrity": report["checks"]["integrity"],
            "monotonicity": report["checks"]["monotonicity"],
        },
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
            f"loaded attenu_guard {attenu_guard.__version__!r}, expected {expected_version!r}"
        )

    cases = [
        _observe("literal_subset_base", _granted()),
        _observe("increased_ttl", _granted(ttl=7200)),
        _observe("loosened_ceiling", _granted(max_rows=250)),
        _observe("unbounded_ttl", _granted(ttl=None)),
        _observe("dropped_ceiling", _granted(max_rows=None)),
        _observe(
            "widened_scope_control",
            _granted(scopes=("crm.read", "pay.transfer")),
        ),
    ]
    report = {
        "implementation": "python",
        "package": "attenu-guard",
        "version": attenu_guard.__version__,
        "runtime": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "platform": sys.platform,
            "machine": platform.machine(),
        },
        "defect_cases": sorted(DEFECT_CASES),
        "bundle_profile": {
            "canonicalization": BUNDLE_CANONICALIZATION,
            "params_salt_hex": FIXED_PARAMS_SALT_HEX,
        },
        "cases": cases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
