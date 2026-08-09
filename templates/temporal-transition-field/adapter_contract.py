#!/usr/bin/env python3
"""Fail-closed adapter contract for Temporal Transition Field v0.6.

The engine remains target-agnostic. A concrete adapter is admitted only when a
machine-readable manifest proves that the target is authorized, non-production,
bounded, and compatible with the declared state/evidence contract.

This module performs no network activity by itself and never reads credential
values. Manifests may name required environment variables but must not contain
literal secrets.
"""
from __future__ import annotations

from typing import Any, Iterable


ALLOWED_ENVIRONMENTS = {"local", "sandbox", "test", "local-fork"}
ALLOWED_TARGET_KINDS = {"synthetic", "rest_api", "smart_contract", "agent_wallet", "workflow"}
ALLOWED_CREDENTIAL_SOURCES = {"none", "environment"}
MAX_CONCURRENCY_HARD = 8
MAX_DEPTH_HARD = 32
MAX_PATHS_HARD = 10000
FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "token",
    "secret",
    "password",
    "private_key",
    "credentials_value",
    "authorization_header",
}


class AdapterContractError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AdapterContractError(message)


def _reject_literal_secret_fields(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            _require(
                normalized not in FORBIDDEN_SECRET_KEYS,
                f"literal secret field is forbidden in adapter manifest: {path}.{key}",
            )
            _reject_literal_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_literal_secret_fields(child, f"{path}[{index}]")


def get_path(document: Any, dotted_path: str) -> Any:
    current = document
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise AdapterContractError(f"missing required field: {dotted_path}")
        current = current[part]
    return current


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    _require(isinstance(manifest, dict), "adapter manifest must be an object")
    _reject_literal_secret_fields(manifest)
    _require(manifest.get("schema_version") == "0.6", "adapter manifest schema_version must be 0.6")
    _require(bool(manifest.get("adapter_id")), "adapter_id is required")
    _require(manifest.get("target_kind") in ALLOWED_TARGET_KINDS, "unsupported target_kind")

    scope = manifest.get("scope")
    _require(isinstance(scope, dict), "scope is required")
    _require(scope.get("authorized") is True, "scope.authorized must be true")
    _require(scope.get("production") is False, "production targets are forbidden by this template")
    _require(scope.get("environment") in ALLOWED_ENVIRONMENTS, "unsupported or production-like environment")
    _require(bool(scope.get("target")), "scope.target is required")

    execution = manifest.get("execution")
    _require(isinstance(execution, dict), "execution is required")
    _require(execution.get("dry_run_default") is True, "execution.dry_run_default must be true")
    max_concurrency = execution.get("max_concurrency")
    max_depth = execution.get("max_depth")
    max_paths = execution.get("max_paths")
    _require(
        isinstance(max_concurrency, int) and 1 <= max_concurrency <= MAX_CONCURRENCY_HARD,
        f"max_concurrency must be within 1..{MAX_CONCURRENCY_HARD}",
    )
    _require(
        isinstance(max_depth, int) and 1 <= max_depth <= MAX_DEPTH_HARD,
        f"max_depth must be within 1..{MAX_DEPTH_HARD}",
    )
    _require(
        isinstance(max_paths, int) and 1 <= max_paths <= MAX_PATHS_HARD,
        f"max_paths must be within 1..{MAX_PATHS_HARD}",
    )

    credentials = manifest.get("credentials")
    _require(isinstance(credentials, dict), "credentials is required")
    source = credentials.get("source")
    _require(source in ALLOWED_CREDENTIAL_SOURCES, "credentials.source must be none or environment")
    env_vars = credentials.get("required_env_vars")
    _require(isinstance(env_vars, list), "credentials.required_env_vars must be a list")
    _require(
        all(isinstance(item, str) and item for item in env_vars),
        "credential env-var names must be non-empty strings",
    )
    _require(len(env_vars) == len(set(env_vars)), "credential env-var names must be unique")
    if source == "none":
        _require(not env_vars, "credentials.source=none cannot require environment variables")
    else:
        _require(bool(env_vars), "credentials.source=environment must name at least one environment variable")

    capabilities = manifest.get("capabilities")
    _require(isinstance(capabilities, dict), "capabilities is required")
    _require(capabilities.get("snapshot") is True, "snapshot capability is required")
    _require(capabilities.get("apply") is True, "apply capability is required")
    _require(capabilities.get("coverage_mode") == "full_model", "v0.6 requires coverage_mode=full_model")
    events = capabilities.get("supported_events")
    _require(isinstance(events, list) and events, "supported_events must be a non-empty list")
    _require(
        all(isinstance(item, str) and item for item in events),
        "supported_events must contain non-empty strings",
    )
    _require(len(events) == len(set(events)), "supported_events must be unique")

    state_contract = manifest.get("state_contract")
    _require(isinstance(state_contract, dict), "state_contract is required")
    required_values = state_contract.get("required_values")
    _require(isinstance(required_values, list), "state_contract.required_values must be a list")
    _require(
        all(isinstance(item, str) and item for item in required_values),
        "required state fields must be non-empty strings",
    )

    evidence_contract = manifest.get("evidence_contract")
    _require(isinstance(evidence_contract, dict), "evidence_contract is required")
    required_fields = evidence_contract.get("required_fields")
    _require(isinstance(required_fields, list), "evidence_contract.required_fields must be a list")
    _require(
        all(isinstance(item, str) and item for item in required_fields),
        "required evidence fields must be non-empty strings",
    )

    return manifest


def enforce_search_bounds(manifest: dict[str, Any], *, max_depth: int, max_paths: int) -> None:
    execution = manifest["execution"]
    _require(max_depth <= execution["max_depth"], "requested max_depth exceeds adapter manifest bound")
    _require(max_paths <= execution["max_paths"], "requested max_paths exceeds adapter manifest bound")


def validate_model_coverage(manifest: dict[str, Any], transitions: Iterable[tuple[str, str, str]]) -> None:
    modeled_events = {event for _, event, _ in transitions}
    supported = set(manifest["capabilities"]["supported_events"])
    missing = sorted(modeled_events - supported)
    _require(not missing, f"adapter manifest does not cover modeled events: {', '.join(missing)}")


def validate_snapshot(snapshot: dict[str, Any], manifest: dict[str, Any]) -> None:
    _require(isinstance(snapshot, dict), "adapter snapshot must be an object")
    _require(
        isinstance(snapshot.get("state_id"), str) and snapshot["state_id"],
        "snapshot.state_id is required",
    )
    values = snapshot.get("values")
    _require(isinstance(values, dict), "snapshot.values must be an object")
    missing = [field for field in manifest["state_contract"]["required_values"] if field not in values]
    _require(not missing, f"snapshot missing required state values: {', '.join(missing)}")


def validate_observation(observation: dict[str, Any], event: str, manifest: dict[str, Any]) -> None:
    _require(isinstance(observation, dict), "adapter observation must be an object")
    _require(
        event in manifest["capabilities"]["supported_events"],
        f"event not allowed by adapter manifest: {event}",
    )
    for dotted in manifest["evidence_contract"]["required_fields"]:
        get_path(observation, dotted)
    observed_action = get_path(observation, "request.action")
    _require(
        observed_action == event,
        f"observation request.action mismatch: expected {event}, got {observed_action}",
    )


class ContractBoundAdapter:
    """Runtime wrapper enforcing a validated adapter manifest on every call."""

    def __init__(self, adapter: Any, manifest: dict[str, Any]):
        self._adapter = adapter
        self.manifest = validate_manifest(manifest)
        _require(callable(getattr(adapter, "snapshot", None)), "adapter.snapshot() is required")
        _require(callable(getattr(adapter, "apply", None)), "adapter.apply(event) is required")
        validate_snapshot(adapter.snapshot(), self.manifest)

    def snapshot(self) -> dict[str, Any]:
        snapshot = self._adapter.snapshot()
        validate_snapshot(snapshot, self.manifest)
        return snapshot

    def apply(self, event: str) -> dict[str, Any]:
        _require(
            event in self.manifest["capabilities"]["supported_events"],
            f"event not allowed by adapter manifest: {event}",
        )
        observation = self._adapter.apply(event)
        validate_observation(observation, event, self.manifest)
        return observation


def evidence_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    scope = manifest["scope"]
    return {
        "environment": scope["environment"],
        "authorized": True,
        "target": scope["target"],
        "notes": f"Adapter contract: {manifest['adapter_id']}; target_kind={manifest['target_kind']}",
    }
