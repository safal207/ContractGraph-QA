"""Provider Adapter Contract for Agent Payment Recovery Benchmark.

v0.1 requires a fully specified evidence precedence and retry policy.
v0.2 adds an explicit fail-closed representation for public contracts where
precedence or recovery semantics are not documented. No network calls occur
here: adapters only normalize already-captured observations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ADAPTER_SCHEMA_V1 = "cgqa.payment-provider-adapter.v0.1"
ADAPTER_SCHEMA_V2 = "cgqa.payment-provider-adapter.v0.2"
ADAPTER_SCHEMAS = {ADAPTER_SCHEMA_V1, ADAPTER_SCHEMA_V2}
OBSERVATION_SCHEMA = "cgqa.payment-provider-observations.v0.1"
RESULT_SCHEMA = "cgqa.payment-provider-reconciliation.v0.1"
_FINAL_OUTCOMES = {"committed", "failed"}
_ALLOWED_OUTCOMES = _FINAL_OUTCOMES | {"pending", "unknown"}


class ProviderAdapterError(ValueError):
    """Raised when an adapter profile or provider observation is invalid."""


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderAdapterError(f"{field} must be a non-empty string")
    return value.strip()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProviderAdapterError(f"unable to read {label}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderAdapterError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProviderAdapterError(f"{label} root must be an object")
    return payload


def load_provider_adapter(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "adapter")
    validate_provider_adapter(payload)
    return payload


def load_provider_observations(path: Path) -> dict[str, Any]:
    payload = _load_json(path, "observations")
    if payload.get("schema") != OBSERVATION_SCHEMA:
        raise ProviderAdapterError(f"observations.schema must be {OBSERVATION_SCHEMA}")
    _required_text(payload.get("logicalOperationId"), "logicalOperationId")
    _required_text(payload.get("executionId"), "executionId")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ProviderAdapterError("observations must be a non-empty array")
    return payload


def _validate_common(payload: dict[str, Any]) -> tuple[str, str, list[str], set[str], int]:
    provider_id = _required_text(payload.get("providerId"), "providerId")
    profile_version = _required_text(payload.get("profileVersion"), "profileVersion")

    create = payload.get("create")
    if not isinstance(create, dict):
        raise ProviderAdapterError("create must be an object")
    for field in ("supportsIdempotencyKey", "sameKeyReplayDocumented"):
        if not isinstance(create.get(field), bool):
            raise ProviderAdapterError(f"create.{field} must be boolean")

    state_map = payload.get("stateMap")
    if not isinstance(state_map, dict) or not state_map:
        raise ProviderAdapterError("stateMap must be a non-empty object")
    normalized_states: dict[str, str] = {}
    for provider_state, normalized in state_map.items():
        state = _required_text(provider_state, "stateMap key").lower()
        outcome = _required_text(normalized, f"stateMap.{provider_state}").lower()
        if outcome not in _ALLOWED_OUTCOMES:
            raise ProviderAdapterError(
                f"stateMap.{provider_state} must map to committed, failed, pending, or unknown"
            )
        normalized_states[state] = outcome

    evidence = payload.get("evidenceSources")
    if not isinstance(evidence, list) or not evidence:
        raise ProviderAdapterError("evidenceSources must be a non-empty array")
    source_names: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise ProviderAdapterError(f"evidenceSources[{index}] must be an object")
        source = _required_text(item.get("kind"), f"evidenceSources[{index}].kind")
        if source in seen:
            raise ProviderAdapterError(f"duplicate evidence source: {source}")
        seen.add(source)
        source_names.append(source)
        if not isinstance(item.get("authoritativeForFinality"), bool):
            raise ProviderAdapterError(
                f"evidenceSources[{index}].authoritativeForFinality must be boolean"
            )

    public_refs = payload.get("publicContractRefs", [])
    if not isinstance(public_refs, list):
        raise ProviderAdapterError("publicContractRefs must be an array")
    for index, ref in enumerate(public_refs):
        _required_text(ref, f"publicContractRefs[{index}]")

    return provider_id, profile_version, source_names, seen, len(normalized_states)


def validate_provider_adapter(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a declarative provider adapter and return a compact summary."""
    schema = payload.get("schema")
    if schema not in ADAPTER_SCHEMAS:
        raise ProviderAdapterError(
            f"schema must be one of {', '.join(sorted(ADAPTER_SCHEMAS))}"
        )

    provider_id, profile_version, source_names, seen, state_count = _validate_common(payload)

    if schema == ADAPTER_SCHEMA_V1:
        retry = payload.get("retryPolicy")
        if not isinstance(retry, dict):
            raise ProviderAdapterError("retryPolicy must be an object")
        for field in (
            "forbidBeforeFinalReconciliation",
            "forbidAfterCommitted",
            "requireSameLogicalOperationId",
            "requireSameIdempotencyKey",
        ):
            if not isinstance(retry.get(field), bool):
                raise ProviderAdapterError(f"retryPolicy.{field} must be boolean")

        precedence = payload.get("evidencePrecedence")
        if not isinstance(precedence, list) or not precedence:
            raise ProviderAdapterError("evidencePrecedence must be a non-empty array")
        precedence_names = [_required_text(item, "evidencePrecedence item") for item in precedence]
        if len(precedence_names) != len(set(precedence_names)):
            raise ProviderAdapterError("evidencePrecedence must not contain duplicates")
        if set(precedence_names) != seen:
            raise ProviderAdapterError(
                "evidencePrecedence must contain every evidence source exactly once"
            )
        precedence_status = "documented"
    else:
        precedence_status = _required_text(
            payload.get("evidencePrecedenceStatus"), "evidencePrecedenceStatus"
        ).lower()
        if precedence_status not in {"documented", "unresolved"}:
            raise ProviderAdapterError(
                "evidencePrecedenceStatus must be documented or unresolved"
            )
        precedence = payload.get("evidencePrecedence")
        if not isinstance(precedence, list):
            raise ProviderAdapterError("evidencePrecedence must be an array")
        precedence_names = [_required_text(item, "evidencePrecedence item") for item in precedence]
        if precedence_status == "documented":
            if not precedence_names:
                raise ProviderAdapterError(
                    "documented evidence precedence must be non-empty"
                )
            if len(precedence_names) != len(set(precedence_names)):
                raise ProviderAdapterError("evidencePrecedence must not contain duplicates")
            if set(precedence_names) != seen:
                raise ProviderAdapterError(
                    "documented evidencePrecedence must contain every evidence source exactly once"
                )
        elif precedence_names:
            raise ProviderAdapterError(
                "unresolved evidence precedence must not invent an ordering"
            )

        open_questions = payload.get("openQuestions", [])
        if not isinstance(open_questions, list):
            raise ProviderAdapterError("openQuestions must be an array")
        for index, question in enumerate(open_questions):
            _required_text(question, f"openQuestions[{index}]")

    return {
        "schema": schema,
        "providerId": provider_id,
        "profileVersion": profile_version,
        "states": state_count,
        "evidenceSources": source_names,
        "evidencePrecedenceStatus": precedence_status,
        "evidencePrecedence": precedence_names,
        "status": "valid",
        "authority": {
            "classification": "PUBLIC_CONTRACT_PROFILE",
            "securityCertification": False,
            "productionAuthorization": False,
        },
    }


def _select_evidence(
    adapter: dict[str, Any],
    normalized: list[dict[str, Any]],
    latest_by_source: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool, str | None]:
    schema = adapter["schema"]
    if schema == ADAPTER_SCHEMA_V1 or adapter.get("evidencePrecedenceStatus") == "documented":
        precedence = [str(item) for item in adapter["evidencePrecedence"]]
        for source in precedence:
            if source in latest_by_source:
                return latest_by_source[source], True, None
        raise ProviderAdapterError("no selectable provider evidence")

    authoritative = [item for item in normalized if item["authoritativeForFinality"]]
    latest_authoritative: dict[str, dict[str, Any]] = {}
    for item in authoritative:
        latest_authoritative[str(item["source"])] = item
    authoritative = list(latest_authoritative.values())

    if len(authoritative) == 1:
        return authoritative[0], True, None

    # With unresolved precedence, multiple authoritative surfaces cannot be
    # silently ordered. Preserve observations and fail closed.
    selected = normalized[-1]
    reason = (
        "no_authoritative_finality_surface_observed"
        if not authoritative
        else "evidence_precedence_unresolved"
    )
    return selected, False, reason


def reconcile_provider_observations(
    adapter: dict[str, Any], observations_payload: dict[str, Any]
) -> dict[str, Any]:
    """Normalize provider evidence and derive a fail-closed reconciliation result."""
    validate_provider_adapter(adapter)
    if observations_payload.get("schema") != OBSERVATION_SCHEMA:
        raise ProviderAdapterError(f"observations.schema must be {OBSERVATION_SCHEMA}")

    logical_operation_id = _required_text(
        observations_payload.get("logicalOperationId"), "logicalOperationId"
    )
    execution_id = _required_text(observations_payload.get("executionId"), "executionId")
    observations = observations_payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ProviderAdapterError("observations must be a non-empty array")

    state_map = {str(key).lower(): str(value).lower() for key, value in adapter["stateMap"].items()}
    source_config = {str(item["kind"]): item for item in adapter["evidenceSources"]}

    normalized: list[dict[str, Any]] = []
    latest_by_source: dict[str, dict[str, Any]] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ProviderAdapterError(f"observations[{index}] must be an object")
        source = _required_text(observation.get("source"), f"observations[{index}].source")
        if source not in source_config:
            raise ProviderAdapterError(f"undeclared evidence source: {source}")
        provider_state = _required_text(
            observation.get("providerState"), f"observations[{index}].providerState"
        ).lower()
        if provider_state not in state_map:
            raise ProviderAdapterError(f"unmapped provider state: {provider_state}")
        evidence_ref = _required_text(
            observation.get("evidenceRef"), f"observations[{index}].evidenceRef"
        )
        normalized_item = {
            "source": source,
            "providerState": provider_state,
            "outcome": state_map[provider_state],
            "evidenceRef": evidence_ref,
            "authoritativeForFinality": bool(source_config[source]["authoritativeForFinality"]),
        }
        normalized.append(normalized_item)
        latest_by_source[source] = normalized_item

    selected, selection_safe, block_reason = _select_evidence(adapter, normalized, latest_by_source)
    selected_outcome = str(selected["outcome"])
    final = (
        selection_safe
        and bool(selected["authoritativeForFinality"])
        and selected_outcome in _FINAL_OUTCOMES
    )
    outcome = selected_outcome if final or selected_outcome in {"pending", "unknown"} else "unknown"

    overridden = [
        item
        for item in normalized
        if item["source"] != selected["source"] and item["outcome"] != outcome
    ]

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "adapterSchema": adapter["schema"],
        "providerId": adapter["providerId"],
        "profileVersion": adapter["profileVersion"],
        "logicalOperationId": logical_operation_id,
        "executionId": execution_id,
        "status": "final" if final else "nonfinal",
        "outcome": outcome,
        "selectedEvidence": selected,
        "overriddenEvidence": overridden,
        "normalizedObservations": normalized,
        "retryAllowed": bool(final and outcome == "failed"),
        "authority": {
            "classification": "RESEARCH_ONLY",
            "securityCertification": False,
            "productionAuthorization": False,
            "financialAuthorization": False,
        },
    }
    if block_reason:
        result["reconciliationBlockReason"] = block_reason
    if final:
        result["reconcileEvent"] = {
            "type": "reconcile",
            "logicalOperationId": logical_operation_id,
            "evidenceKind": selected["source"],
            "evidenceRef": selected["evidenceRef"],
            "outcome": outcome,
        }
    return result


def reconcile_provider_files(adapter_path: Path, observations_path: Path) -> dict[str, Any]:
    adapter = load_provider_adapter(adapter_path)
    observations = load_provider_observations(observations_path)
    return reconcile_provider_observations(adapter, observations)
