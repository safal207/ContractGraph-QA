"""ASTRA state-plane and independent-witness analysis.

This layer is deliberately diagnostic. It does not declare a target defect from a
state mismatch. It records whether primary/mirror/witness observations disagree
and whether a configured state hash may be collapsing causally distinct states.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class AstraStatePlaneError(ValueError):
    """Raised when ASTRA state-plane input is malformed."""


def _text(obj: dict[str, Any], key: str, where: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AstraStatePlaneError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def _observations(raw: Any, where: str) -> list[dict[str, str | bool]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise AstraStatePlaneError(f"{where} must be an array")
    result: list[dict[str, str | bool]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        item_where = f"{where}[{index}]"
        if not isinstance(item, dict):
            raise AstraStatePlaneError(f"{item_where} must be an object")
        obs_id = _text(item, "id", item_where)
        if obs_id in seen:
            raise AstraStatePlaneError(f"duplicate observation id in {where}: {obs_id}")
        seen.add(obs_id)
        fingerprint = _text(item, "fingerprint", item_where)
        source_root = _text(item, "source_root", item_where)
        independent = item.get("independent", False)
        if not isinstance(independent, bool):
            raise AstraStatePlaneError(f"{item_where}.independent must be boolean")
        result.append(
            {
                "id": obs_id,
                "fingerprint": fingerprint,
                "source_root": source_root,
                "independent": independent,
            }
        )
    return result


def analyze_state_planes(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze observed state planes and detect state-hash suspicion.

    Each state must declare a stable ``future_signature`` supplied by the reviewed
    adapter/model. Two observations sharing the same ``state_hash`` but carrying
    different future signatures are not proven equivalent for pruning purposes;
    ASTRA reports that pair as ``STATE_HASH_SUSPECT``.
    """
    if not isinstance(payload, dict):
        raise AstraStatePlaneError("input must be an object")
    raw_states = payload.get("states")
    if not isinstance(raw_states, list) or not raw_states:
        raise AstraStatePlaneError("states must be a non-empty array")

    states: list[dict[str, Any]] = []
    ids: set[str] = set()
    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for index, raw in enumerate(raw_states):
        where = f"states[{index}]"
        if not isinstance(raw, dict):
            raise AstraStatePlaneError(f"{where} must be an object")
        state_id = _text(raw, "id", where)
        if state_id in ids:
            raise AstraStatePlaneError(f"duplicate state id: {state_id}")
        ids.add(state_id)
        state_hash = _text(raw, "state_hash", where)
        future_signature = _text(raw, "future_signature", where)

        primary = raw.get("primary")
        if not isinstance(primary, dict):
            raise AstraStatePlaneError(f"{where}.primary must be an object")
        primary_fingerprint = _text(primary, "fingerprint", f"{where}.primary")
        primary_source_root = _text(primary, "source_root", f"{where}.primary")

        mirrors = _observations(raw.get("mirrors", []), f"{where}.mirrors")
        witnesses = _observations(raw.get("witnesses", []), f"{where}.witnesses")

        mirror_disagreements = [
            str(item["id"]) for item in mirrors if item["fingerprint"] != primary_fingerprint
        ]
        independent = [
            item
            for item in witnesses
            if item["independent"] and item["source_root"] != primary_source_root
        ]
        independent_disagreements = [
            str(item["id"])
            for item in independent
            if item["fingerprint"] != primary_fingerprint
        ]

        witness_gap = 1.0 if not independent else 0.0
        mirror_divergence = (
            round(len(mirror_disagreements) / len(mirrors), 6) if mirrors else 0.0
        )
        witness_divergence = (
            round(len(independent_disagreements) / len(independent), 6)
            if independent
            else 0.0
        )

        normalized = {
            "state_id": state_id,
            "state_hash": state_hash,
            "future_signature": future_signature,
            "primary": {
                "fingerprint": primary_fingerprint,
                "source_root": primary_source_root,
            },
            "mirrors": mirrors,
            "witnesses": witnesses,
            "independent_witness_count": len(independent),
            "witness_gap": witness_gap,
            "mirror_divergence": mirror_divergence,
            "witness_divergence": witness_divergence,
            "mirror_disagreements": mirror_disagreements,
            "independent_witness_disagreements": independent_disagreements,
            "state_plane_ambiguity": bool(
                mirror_disagreements or independent_disagreements or not independent
            ),
        }
        states.append(normalized)
        by_hash[state_hash].append(normalized)

    suspicions: list[dict[str, Any]] = []
    for state_hash, members in sorted(by_hash.items()):
        if len(members) < 2:
            continue
        signatures = {str(item["future_signature"]) for item in members}
        independent_fingerprints = {
            str(witness["fingerprint"])
            for item in members
            for witness in item["witnesses"]
            if witness["independent"]
            and witness["source_root"] != item["primary"]["source_root"]
        }
        reasons: list[str] = []
        if len(signatures) > 1:
            reasons.append("different_future_signature")
        if len(independent_fingerprints) > 1:
            reasons.append("different_independent_witness_state")
        if reasons:
            suspicions.append(
                {
                    "state_hash": state_hash,
                    "state_ids": [str(item["state_id"]) for item in members],
                    "status": "STATE_HASH_SUSPECT",
                    "reasons": reasons,
                }
            )

    any_ambiguity = any(bool(item["state_plane_ambiguity"]) for item in states)
    verdict = "REVIEW_REQUIRED" if suspicions or any_ambiguity else "CONSISTENT_WITH_INPUT"

    return {
        "schema_version": "astra-state-planes-v0.1",
        "baseline_preserved": True,
        "states": states,
        "state_hash_suspicions": suspicions,
        "verdict": verdict,
        "semantics": {
            "state_hash_suspect_is_not_target_failure": True,
            "missing_independent_witness_fails_closed": True,
        },
    }
