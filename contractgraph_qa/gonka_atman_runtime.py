"""Fail-closed helpers for GONKA-ATMAN G-005 restart/recovery evidence."""
from __future__ import annotations

from typing import Any

PINNED_G005_REVISION = "379bebced638aeb5e6077bfd51c986f898443832"
REQUIRED_COMPONENTS = {"devshardctl", "versiond", "devshardd"}
PROVENANCE_METHODS = {"local-build-from-pinned-source", "oci-attestation"}


def _digest(value: Any) -> bool:
    text = str(value or "")
    return text.startswith("sha256:") and len(text) == 71


def verify_runtime_fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify source -> build/image -> running-container provenance.

    Container metadata alone is never sufficient.  A runtime is PROVEN only when
    every required running component exposes an immutable image digest and those
    digests are bound by an independent provenance record to the sealed source SHA.
    """
    required = {"source_revision", "runtime_artifacts", "config_generation", "provenance"}
    missing = sorted(required - set(payload))
    if missing:
        return {"verdict": "UNPROVEN", "missing": missing, "target_claim_allowed": False}
    if payload["source_revision"] != PINNED_G005_REVISION:
        return {"verdict": "MISMATCH", "reason": "source revision differs from sealed G-005 pin", "target_claim_allowed": False}

    artifacts = payload.get("runtime_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return {"verdict": "UNPROVEN", "reason": "no runtime artifacts", "target_claim_allowed": False}

    components: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            return {"verdict": "UNPROVEN", "reason": "malformed runtime artifact", "target_claim_allowed": False}
        component = item.get("component")
        if not component or not item.get("container_id") or not item.get("image_id"):
            return {"verdict": "UNPROVEN", "reason": "runtime artifact lacks container/image identity", "target_claim_allowed": False}
        if not _digest(item.get("image_digest")):
            return {"verdict": "UNPROVEN", "reason": f"{component} lacks immutable OCI image digest", "target_claim_allowed": False}
        if component in components:
            return {"verdict": "UNPROVEN", "reason": f"duplicate runtime component {component}", "target_claim_allowed": False}
        components[str(component)] = item

    missing_components = sorted(REQUIRED_COMPONENTS - set(components))
    if missing_components:
        return {"verdict": "UNPROVEN", "missing_components": missing_components, "target_claim_allowed": False}

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return {"verdict": "UNPROVEN", "reason": "provenance record missing", "target_claim_allowed": False}
    if provenance.get("method") not in PROVENANCE_METHODS:
        return {"verdict": "UNPROVEN", "reason": "unsupported provenance method", "target_claim_allowed": False}
    if provenance.get("source_revision") != PINNED_G005_REVISION:
        return {"verdict": "MISMATCH", "reason": "provenance source revision differs from sealed G-005 pin", "target_claim_allowed": False}
    if not _digest(provenance.get("evidence_sha256")):
        return {"verdict": "UNPROVEN", "reason": "provenance evidence digest missing", "target_claim_allowed": False}

    bindings = provenance.get("component_image_digests")
    if not isinstance(bindings, dict):
        return {"verdict": "UNPROVEN", "reason": "provenance image bindings missing", "target_claim_allowed": False}
    for component in REQUIRED_COMPONENTS:
        runtime_digest = components[component]["image_digest"]
        if bindings.get(component) != runtime_digest:
            return {
                "verdict": "MISMATCH",
                "reason": f"{component} running image digest is not bound to pinned-source provenance",
                "target_claim_allowed": False,
            }

    return {
        "verdict": "PROVEN",
        "target_claim_allowed": True,
        "source_revision": PINNED_G005_REVISION,
        "provenance_method": provenance["method"],
    }


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
