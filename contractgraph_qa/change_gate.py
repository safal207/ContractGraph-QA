"""Repository-level causal security change gate for pull-request review."""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from contractgraph_qa.graph_delta import compare_reachability_models
from contractgraph_qa.reachability import ReachabilityModel, reachability_model_from_dict


class ChangeGateError(ValueError):
    """Raised when gate configuration or repository state is invalid."""


@dataclass(frozen=True)
class GateModelSpec:
    id: str
    path: str


@dataclass(frozen=True)
class ChangeGateConfig:
    schema_version: int
    models: tuple[GateModelSpec, ...]


class RepositoryView(Protocol):
    def resolve_commit(self, ref: str) -> str: ...

    def read_at_commit(self, commit_sha: str, path: str) -> bytes: ...

    def read_worktree(self, path: str) -> bytes: ...


class GitRepository:
    """Read exact base bytes from git while keeping head bytes from the worktree."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def _git(self, *args: str, text: bool = False) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                check=False,
                capture_output=True,
                text=text,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ChangeGateError(f"git invocation failed: {exc}") from exc

    def resolve_commit(self, ref: str) -> str:
        completed = self._git("rev-parse", "--verify", f"{ref}^{{commit}}", text=True)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() if isinstance(completed.stderr, str) else ""
            raise ChangeGateError(f"cannot resolve git ref {ref!r}: {stderr or 'unknown git error'}")
        stdout = completed.stdout.strip() if isinstance(completed.stdout, str) else ""
        if len(stdout) != 40:
            raise ChangeGateError(f"git ref {ref!r} did not resolve to a full commit SHA")
        return stdout

    def read_at_commit(self, commit_sha: str, path: str) -> bytes:
        completed = self._git("show", f"{commit_sha}:{path}")
        if completed.returncode != 0:
            raise FileNotFoundError(path)
        assert isinstance(completed.stdout, bytes)
        return completed.stdout

    def read_worktree(self, path: str) -> bytes:
        source = (self.root / Path(path)).resolve()
        try:
            source.relative_to(self.root)
        except ValueError as exc:
            raise ChangeGateError(f"configured path escapes repository root: {path}") from exc
        return source.read_bytes()


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChangeGateError(f"{label} must be a non-empty string")
    return value.strip()


def _normalize_model_path(value: object, label: str) -> str:
    raw = _require_text(value, label).replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ChangeGateError(f"{label} must be a repository-relative path without traversal")
    return path.as_posix()


def _load_config_bytes(payload: bytes, label: str) -> ChangeGateConfig:
    try:
        data = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ChangeGateError(f"invalid change-gate TOML in {label}: {exc}") from exc
    if set(data) != {"schemaVersion", "models"}:
        raise ChangeGateError(f"{label} must contain exactly schemaVersion and models")
    if data["schemaVersion"] != 1:
        raise ChangeGateError(f"{label}.schemaVersion must be 1")
    raw_models = data["models"]
    if not isinstance(raw_models, list) or not raw_models:
        raise ChangeGateError(f"{label}.models must be a non-empty array")

    models: list[GateModelSpec] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for index, item in enumerate(raw_models):
        item_label = f"{label}.models[{index}]"
        if not isinstance(item, dict) or set(item) != {"id", "path"}:
            raise ChangeGateError(f"{item_label} must contain exactly id and path")
        model_id = _require_text(item["id"], f"{item_label}.id")
        model_path = _normalize_model_path(item["path"], f"{item_label}.path")
        if model_id in ids:
            raise ChangeGateError(f"duplicate change-gate model id: {model_id}")
        if model_path in paths:
            raise ChangeGateError(f"duplicate change-gate model path: {model_path}")
        ids.add(model_id)
        paths.add(model_path)
        models.append(GateModelSpec(model_id, model_path))

    return ChangeGateConfig(1, tuple(sorted(models, key=lambda item: item.id)))


def load_change_gate_config(path: Path) -> ChangeGateConfig:
    source = path.expanduser().resolve()
    try:
        return _load_config_bytes(source.read_bytes(), str(source))
    except OSError as exc:
        raise ChangeGateError(f"cannot read change-gate config {source}: {exc}") from exc


def _model_from_bytes(payload: bytes, label: str) -> ReachabilityModel:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChangeGateError(f"invalid reachability JSON in {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise ChangeGateError(f"{label} must contain a JSON object")
    try:
        return reachability_model_from_dict(data)
    except ValueError as exc:
        raise ChangeGateError(f"invalid reachability model in {label}: {exc}") from exc


def _blocking_result(model_id: str, path: str, reason: str) -> dict[str, object]:
    return {
        "id": model_id,
        "path": path,
        "status": "blocked",
        "blocking": True,
        "gateReasons": [reason],
    }


def _config_relative_path(config_path: Path, repo_root: Path) -> str:
    source = config_path.expanduser().resolve()
    root = repo_root.expanduser().resolve()
    try:
        relative = source.relative_to(root)
    except ValueError as exc:
        raise ChangeGateError("change-gate config must live inside repository root") from exc
    return PurePosixPath(relative.as_posix()).as_posix()


def run_change_gate(
    config_path: Path,
    base_ref: str,
    repo_root: Path | None = None,
    repository: RepositoryView | None = None,
) -> dict[str, object]:
    """Compare configured reachability models between an exact base commit and head worktree."""

    root = (repo_root or Path.cwd()).expanduser().resolve()
    repo = repository or GitRepository(root)
    config_rel = _config_relative_path(config_path, root)
    head_config = load_change_gate_config(config_path)
    base_sha = repo.resolve_commit(base_ref)
    head_sha = repo.resolve_commit("HEAD")

    try:
        base_config = _load_config_bytes(
            repo.read_at_commit(base_sha, config_rel),
            f"{base_sha}:{config_rel}",
        )
        baseline_config_present = True
    except FileNotFoundError:
        base_config = ChangeGateConfig(1, ())
        baseline_config_present = False

    base_specs = {item.id: item for item in base_config.models}
    head_specs = {item.id: item for item in head_config.models}
    results: list[dict[str, object]] = []

    for model_id in sorted(set(base_specs) | set(head_specs)):
        base_spec = base_specs.get(model_id)
        head_spec = head_specs.get(model_id)

        if base_spec is not None and head_spec is None:
            results.append(_blocking_result(model_id, base_spec.path, "configured_model_removed"))
            continue
        assert head_spec is not None
        if base_spec is not None and base_spec.path != head_spec.path:
            results.append(_blocking_result(model_id, head_spec.path, "configured_model_path_changed"))
            continue

        model_path = head_spec.path
        try:
            base_bytes = repo.read_at_commit(base_sha, model_path)
        except FileNotFoundError:
            results.append(_blocking_result(model_id, model_path, "base_model_missing"))
            continue
        try:
            head_bytes = repo.read_worktree(model_path)
        except FileNotFoundError:
            results.append(_blocking_result(model_id, model_path, "head_model_missing"))
            continue

        try:
            base_model = _model_from_bytes(base_bytes, f"{base_sha}:{model_path}")
            head_model = _model_from_bytes(head_bytes, f"worktree:{model_path}")
        except ChangeGateError as exc:
            results.append(
                {
                    **_blocking_result(model_id, model_path, "invalid_model"),
                    "error": str(exc),
                }
            )
            continue

        delta = compare_reachability_models(base_model, head_model)
        blocking = delta["status"] == "risk_increase_detected"
        review = delta["status"] == "control_boundary_change"
        results.append(
            {
                "id": model_id,
                "path": model_path,
                "status": "blocked" if blocking else "review" if review else "pass",
                "blocking": blocking,
                "gateReasons": delta["gateReasons"],
                "delta": delta,
            }
        )

    blocking_models = [item["id"] for item in results if item["blocking"] is True]
    review_models = [item["id"] for item in results if item["status"] == "review"]
    status = "blocked" if blocking_models else "review" if review_models else "pass"

    return {
        "schemaVersion": 1,
        "status": status,
        "baseRef": base_ref,
        "baseCommitSha": base_sha,
        "headCommitSha": head_sha,
        "configPath": config_rel,
        "baselineConfigPresent": baseline_config_present,
        "blockingModels": blocking_models,
        "reviewModels": review_models,
        "models": results,
    }
