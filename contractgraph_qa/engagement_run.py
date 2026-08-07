"""One-command direct multi-invariant engagement runtime."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contractgraph_qa import __version__
from contractgraph_qa.engagement import verify_engagement_bundle, write_engagement_bundle
from contractgraph_qa.finding import load_json_object, manifest_sha256, validate_manifest

CONFIG_KEYS = {
    "schemaVersion",
    "workingDirectory",
    "manifest",
    "result",
    "outputDirectory",
    "bundle",
    "capture",
}
CAPTURE_KEYS = {"profile", "test", "verbosity"}
SAFE_PROFILE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_TEST = re.compile(r"^[A-Za-z0-9_]+$")


class EngagementRunError(RuntimeError):
    """Expected one-command engagement execution failure."""


@dataclass(frozen=True)
class EngagementCaptureConfig:
    profile: str
    test: str
    verbosity: int


@dataclass(frozen=True)
class EngagementRunConfig:
    source: Path
    working_directory: Path
    manifest: Path
    result: Path
    output_directory: Path
    bundle: Path
    capture: EngagementCaptureConfig


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngagementRunError(message)


def _non_blank(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _resolve(base: Path, value: Any, field: str) -> Path:
    raw = _non_blank(value, field)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_engagement_run_config(path: Path) -> EngagementRunConfig:
    source = path.expanduser().resolve()
    _require(source.is_file(), f"engagement-run config not found: {source}")
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise EngagementRunError(f"invalid engagement-run config: {exc}") from exc

    _require(isinstance(data, dict), "engagement-run config must be a TOML table")
    _reject_extra_keys(data, CONFIG_KEYS, "config")
    _require(data.get("schemaVersion") == 1, "config.schemaVersion must equal 1")

    base = source.parent
    working_directory = _resolve(base, data.get("workingDirectory", "."), "config.workingDirectory")
    manifest = _resolve(base, data.get("manifest"), "config.manifest")
    result = _resolve(base, data.get("result"), "config.result")
    output_directory = _resolve(base, data.get("outputDirectory"), "config.outputDirectory")
    bundle = _resolve(base, data.get("bundle"), "config.bundle")

    _require(working_directory.is_dir(), f"working directory not found: {working_directory}")
    _require(manifest != result, "config.manifest and config.result must be distinct")
    _require(bundle.suffix.lower() == ".zip", "config.bundle must use a .zip extension")
    _require(bundle != result and bundle != manifest, "config bundle path collides with an input artifact")
    _require(output_directory != working_directory, "config.outputDirectory must not equal workingDirectory")
    _require(output_directory != manifest.parent, "config.outputDirectory must not equal manifest directory")

    capture_data = data.get("capture")
    _require(isinstance(capture_data, dict), "config.capture must be a table")
    _reject_extra_keys(capture_data, CAPTURE_KEYS, "config.capture")
    profile = _non_blank(capture_data.get("profile", "capture"), "config.capture.profile")
    test = _non_blank(
        capture_data.get("test", "test_CaptureMultiInvariantEngagementResult"),
        "config.capture.test",
    )
    verbosity = capture_data.get("verbosity", 3)
    _require(
        isinstance(verbosity, int) and not isinstance(verbosity, bool) and 0 <= verbosity <= 5,
        "config.capture.verbosity must be an integer from 0 to 5",
    )
    _require(bool(SAFE_PROFILE.fullmatch(profile)), "config.capture.profile contains unsafe characters")
    _require(bool(SAFE_TEST.fullmatch(test)), "config.capture.test contains unsafe characters")

    return EngagementRunConfig(
        source=source,
        working_directory=working_directory,
        manifest=manifest,
        result=result,
        output_directory=output_directory,
        bundle=bundle,
        capture=EngagementCaptureConfig(profile=profile, test=test, verbosity=verbosity),
    )


def _run_direct_capture(config: EngagementRunConfig, fingerprint: str) -> None:
    forge = shutil.which("forge")
    _require(forge is not None, "forge is required for engagement-run but was not found on PATH")
    config.result.parent.mkdir(parents=True, exist_ok=True)
    if config.result.is_file():
        config.result.unlink()

    env = os.environ.copy()
    env["FOUNDRY_PROFILE"] = config.capture.profile
    env["CGQA_ENGAGEMENT_MANIFEST_SHA256"] = fingerprint
    env["CGQA_ENGAGEMENT_RESULT_PATH"] = os.path.relpath(
        config.result, config.working_directory
    )
    command = [forge, "test", "--match-test", config.capture.test]
    if config.capture.verbosity:
        command.append("-" + ("v" * config.capture.verbosity))

    try:
        completed = subprocess.run(
            command,
            cwd=config.working_directory,
            env=env,
            check=False,
            text=True,
        )
    except OSError as exc:
        raise EngagementRunError(f"failed to start Foundry engagement capture: {exc}") from exc
    _require(
        completed.returncode == 0,
        f"Foundry engagement capture failed with exit code {completed.returncode}",
    )
    _require(
        config.result.is_file(),
        f"Foundry engagement capture did not produce a fresh result: {config.result}",
    )


def run_engagement_pipeline(config: EngagementRunConfig) -> dict[str, Any]:
    _require(config.manifest.is_file(), f"manifest not found: {config.manifest}")
    manifest = load_json_object(config.manifest, "manifest")
    validate_manifest(manifest)
    fingerprint = manifest_sha256(manifest)

    _run_direct_capture(config, fingerprint)
    generated = write_engagement_bundle(
        config.manifest,
        config.result,
        config.output_directory,
        config.bundle,
    )
    verification = verify_engagement_bundle(config.bundle)

    _require(
        generated["bundleSha256"] == verification["bundleSha256"],
        "engagement bundle verification hash mismatch",
    )
    return {
        "ok": True,
        "cgqaVersion": __version__,
        "engagementId": verification["engagementId"],
        "manifestSha256": fingerprint,
        "coverage": verification["coverage"],
        "findingIds": verification["findingIds"],
        "result": str(config.result),
        "outputDirectory": str(config.output_directory),
        "bundle": str(config.bundle),
        "bundleSha256": verification["bundleSha256"],
    }
