"""Deterministic evidence binding for provider-backed agent payment decisions.

The pack is intentionally self-contained: it preserves the exact reviewed adapter
profile, captured observations, explicit authority evidence, and derived provider
payment decision. Verification recomputes canonical digests and replays the decision
locally; it never performs network calls or treats provider state as actor authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision

EVIDENCE_SCHEMA = "cgqa.provider-payment-decision-evidence.v0.1"


class ProviderDecisionEvidenceError(ValueError):
    """Raised when provider decision evidence cannot be built or independently verified."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderDecisionEvidenceError(f"{field} must be an object")
    return value


def canonical_json_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 JSON representation used by evidence digests."""
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ProviderDecisionEvidenceError(f"value is not canonical-JSON encodable: {exc}") from exc
    return encoded.encode("utf-8")


def canonical_sha256(value: object) -> str:
    """Return a SHA-256 digest of canonical JSON bytes."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _replay(
    adapter: dict[str, Any],
    observations: dict[str, Any],
    authority: dict[str, Any],
    provider_decision: dict[str, Any],
) -> dict[str, Any]:
    decision_input = _object(provider_decision.get("decisionInput"), "providerDecision.decisionInput")
    fulfillment = _object(decision_input.get("fulfillment"), "providerDecision.decisionInput.fulfillment")
    decision_id = decision_input.get("decisionId")
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise ProviderDecisionEvidenceError(
            "providerDecision.decisionInput.decisionId must be a non-empty string"
        )
    try:
        return evaluate_provider_payment_decision(
            adapter,
            observations,
            authority,
            fulfillment=copy.deepcopy(fulfillment),
            decision_id=decision_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderDecisionEvidenceError(f"provider decision replay failed: {exc}") from exc


def _validate_binding(
    adapter: dict[str, Any],
    observations: dict[str, Any],
    authority: dict[str, Any],
    provider_decision: dict[str, Any],
) -> None:
    expected = _replay(adapter, observations, authority, provider_decision)
    if expected != provider_decision:
        raise ProviderDecisionEvidenceError(
            "providerDecision does not exactly match deterministic replay of embedded evidence"
        )


def build_provider_decision_evidence(
    adapter: dict[str, Any],
    observations: dict[str, Any],
    authority: dict[str, Any],
    provider_decision: dict[str, Any],
) -> dict[str, Any]:
    """Build a deterministic, independently replayable provider-decision evidence pack."""
    adapter = copy.deepcopy(_object(adapter, "adapter"))
    observations = copy.deepcopy(_object(observations, "observations"))
    authority = copy.deepcopy(_object(authority, "authority"))
    provider_decision = copy.deepcopy(_object(provider_decision, "providerDecision"))

    _validate_binding(adapter, observations, authority, provider_decision)

    payloads = {
        "adapter": adapter,
        "observations": observations,
        "authority": authority,
        "providerDecision": provider_decision,
    }
    return {
        "schema": EVIDENCE_SCHEMA,
        "digests": {name: canonical_sha256(payload) for name, payload in payloads.items()},
        "payloads": payloads,
        "claimBoundary": {
            "classification": "PUBLIC_CONTRACT_REPLAY_EVIDENCE",
            "networkCallsPerformed": False,
            "walletExecutionPerformed": False,
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }


def verify_provider_decision_evidence(pack: dict[str, Any]) -> dict[str, Any]:
    """Verify canonical hashes and independently replay the embedded monetary decision."""
    pack = _object(pack, "evidencePack")
    if pack.get("schema") != EVIDENCE_SCHEMA:
        raise ProviderDecisionEvidenceError(f"evidencePack.schema must be {EVIDENCE_SCHEMA}")

    payloads = _object(pack.get("payloads"), "evidencePack.payloads")
    digests = _object(pack.get("digests"), "evidencePack.digests")
    required = {"adapter", "observations", "authority", "providerDecision"}
    if set(payloads) != required or set(digests) != required:
        raise ProviderDecisionEvidenceError(
            "evidencePack payloads and digests must contain exactly adapter, observations, authority, and providerDecision"
        )

    for name in sorted(required):
        expected_digest = canonical_sha256(payloads[name])
        actual_digest = digests.get(name)
        if actual_digest != expected_digest:
            raise ProviderDecisionEvidenceError(f"{name} digest mismatch")

    adapter = _object(payloads["adapter"], "payloads.adapter")
    observations = _object(payloads["observations"], "payloads.observations")
    authority = _object(payloads["authority"], "payloads.authority")
    provider_decision = _object(payloads["providerDecision"], "payloads.providerDecision")
    _validate_binding(adapter, observations, authority, provider_decision)

    return copy.deepcopy(provider_decision)
