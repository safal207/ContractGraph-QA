"""Shared deterministic helpers for causal-temporal verification capabilities."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class CausalTemporalError(ValueError):
    """Base validation error for causal-temporal capability inputs."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CausalTemporalError(f"{name} must be an object")
    return value


def require_list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise CausalTemporalError(f"{name} must be a list")
    return value


def require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CausalTemporalError(f"{name} must be a non-empty string")
    return value


def require_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CausalTemporalError(f"{name} must be an integer")
    return value


def require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise CausalTemporalError(f"{name} must be boolean")
    return value


def require_subject(container: dict[str, Any], name: str = "subject") -> tuple[dict[str, Any], str]:
    subject = require_object(container.get(name), name)
    if not subject:
        raise CausalTemporalError(f"{name} must not be empty")
    return subject, canonical_sha256(subject)
