"""Fail-closed helpers for GONKA-ATMAN G-005 restart/recovery evidence."""
from __future__ import annotations

from typing import Any

PINNED_G005_REVISION = "379bebced638aeb5e6077bfd51c986f898443832"


def verify_runtime_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    required = {"source_revision", "runtime_artifacts", "config_generation"}
    missing = sorted(required - set(payload))
    if missing:
        return {"verdict": "UNPROVEN", "missing": missing, "target_claim_allowed": False}
    if payload["source_revision"] != PINNED_G005_REVISION:
        return {"verdict": "MISMATCH", "reason": "source revision differs from sealed G-005 pin", "target_claim_allowed": False}
    artifacts = payload.get("runtime_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return {"verdict": "UNPROVEN", "reason": "no runtime artifacts", "target_claim_allowed": False}
    components = set()
    for item in artifacts:
        if not isinstance(item, dict):
            return {"verdict": "UNPROVEN", "reason": "malformed runtime artifact", "target_claim_allowed": False}
        if not item.get("component") or not str(item.get("sha256", "")).startswith("sha256:"):
            return {"verdict": "UNPROVEN", "reason": "runtime artifact lacks component/digest", "target_claim_allowed": False}
        components.add(item["component"])
    required_components = {"devshardctl", "versiond", "devshardd"}
    missing_components = sorted(required_components - components)
    if missing_components:
        return {"verdict": "UNPROVEN", "missing_components": missing_components, "target_claim_allowed": False}
    return {"verdict": "PROVEN", "target_claim_allowed": True, "source_revision": PINNED_G005_REVISION}


def verify_restart_lineage(payload: dict[str, Any]) -> dict[str, Any]:
    fp = verify_runtime_fingerprint(payload.get("runtime_fingerprint", {}))
    if fp["verdict"] != "PROVEN":
        return {"verdict": "INCONCLUSIVE", "reason": "runtime generation not proven", "runtime": fp, "target_claim_allowed": False}
    op = payload.get("logical_operation_id")
    attempts = payload.get("attempts", [])
    unexplained = payload.get("unexplained_effects", [])
    if not op or not isinstance(attempts, list) or not attempts:
        return {"verdict": "INCONCLUSIVE", "reason": "lineage evidence incomplete", "target_claim_allowed": False}
    nonces = [a.get("nonce") for a in attempts if isinstance(a, dict)]
    if any(n is None for n in nonces) or len(nonces) != len(set(nonces)):
        return {"verdict": "FAIL_HYPOTHESIS", "broken_invariant": "execution nonce lineage is ambiguous", "target_claim_allowed": True}
    if unexplained:
        return {"verdict": "FAIL_HYPOTHESIS", "broken_invariant": "unexplained post-restart effects", "unexplained_effects": unexplained, "target_claim_allowed": True}
    if not payload.get("accounting_reconciles", False) or not payload.get("settlement_reconciles", False):
        return {"verdict": "FAIL_HYPOTHESIS", "broken_invariant": "restart recovery does not reconcile accounting/settlement", "target_claim_allowed": True}
    return {"verdict": "PASS", "logical_operation_id": op, "attempt_nonces": sorted(nonces), "target_claim_allowed": True}
