"""Product runtime for deterministic ContractGraph-QA engagement pipelines."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contractgraph_qa import __version__
from tools.export_finding import (
    canonical_json,
    export_finding,
    load_json_object,
    manifest_sha256,
    validate_manifest,
    validate_result,
)
from tools.render_finding import render_markdown

CONFIG_KEYS = {
    "schemaVersion",
    "manifest",
    "result",
    "finding",
    "report",
    "bundle",
    "workingDirectory",
    "capture",
}
CAPTURE_KEYS = {"enabled", "profile", "test", "verbosity"}
BUNDLE_MANIFEST_KEYS = {"bundleVersion", "tool", "findingId", "manifestSha256", "artifacts"}
BUNDLE_TOOL_KEYS = {"name", "version"}
ARTIFACT_RECORD_KEYS = {"sha256", "bytes"}
SAFE_PROFILE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_TEST = re.compile(r"^[A-Za-z0-9_]+$")
BUNDLE_FILES = ("manifest.json", "result.json", "finding.json", "report.md", "bundle.json")
MAX_BUNDLE_ENTRY_BYTES = 16 * 1024 * 1024


class ProductError(RuntimeError):
    """Expected product/runtime failure with a user-actionable message."""


@dataclass(frozen=True)
class CaptureConfig:
    enabled: bool
    profile: str
    test: str
    verbosity: int


@dataclass(frozen=True)
class ProductConfig:
    source: Path
    working_directory: Path
    manifest: Path
    result: Path
    finding: Path
    report: Path
    bundle: Path
    capture: CaptureConfig


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductError(message)


def _non_empty_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _reject_extra_keys(data: dict[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _resolve(base: Path, value: Any, field: str) -> Path:
    raw = _non_empty_string(value, field)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def load_product_config(path: Path) -> ProductConfig:
    source = path.expanduser().resolve()
    _require(source.is_file(), f"config file not found: {source}")
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProductError(f"invalid product config: {exc}") from exc

    _require(isinstance(data, dict), "product config must be a TOML table")
    _reject_extra_keys(data, CONFIG_KEYS, "config")
    _require(data.get("schemaVersion") == 1, "config.schemaVersion must equal 1")

    config_dir = source.parent
    working_directory = _resolve(
        config_dir, data.get("workingDirectory", "."), "config.workingDirectory"
    )

    capture_data = data.get("capture", {})
    _require(isinstance(capture_data, dict), "config.capture must be a table")
    _reject_extra_keys(capture_data, CAPTURE_KEYS, "config.capture")

    enabled = capture_data.get("enabled", True)
    _require(isinstance(enabled, bool), "config.capture.enabled must be boolean")
    profile = _non_empty_string(capture_data.get("profile", "capture"), "config.capture.profile")
    test = _non_empty_string(capture_data.get("test", "test_CaptureExplorerResult"), "config.capture.test")
    verbosity = capture_data.get("verbosity", 3)
    _require(
        isinstance(verbosity, int) and not isinstance(verbosity, bool) and 0 <= verbosity <= 5,
        "config.capture.verbosity must be an integer from 0 to 5",
    )
    _require(bool(SAFE_PROFILE.fullmatch(profile)), "config.capture.profile contains unsafe characters")
    _require(bool(SAFE_TEST.fullmatch(test)), "config.capture.test contains unsafe characters")

    manifest = _resolve(config_dir, data.get("manifest"), "config.manifest")
    result = _resolve(config_dir, data.get("result"), "config.result")
    finding = _resolve(config_dir, data.get("finding"), "config.finding")
    report = _resolve(config_dir, data.get("report"), "config.report")
    bundle = _resolve(config_dir, data.get("bundle"), "config.bundle")
    artifact_paths = (manifest, result, finding, report, bundle)
    _require(len(set(artifact_paths)) == len(artifact_paths), "config artifact paths must be distinct")
    _require(bundle.suffix.lower() == ".zip", "config.bundle must use a .zip extension")

    return ProductConfig(
        source=source,
        working_directory=working_directory,
        manifest=manifest,
        result=result,
        finding=finding,
        report=report,
        bundle=bundle,
        capture=CaptureConfig(enabled=enabled, profile=profile, test=test, verbosity=verbosity),
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_manifest(path: Path) -> str:
    manifest = load_json_object(path, "manifest")
    validate_manifest(manifest)
    return manifest_sha256(manifest)


def validate_manifest_result(manifest_path: Path, result_path: Path | None = None) -> dict[str, Any]:
    manifest = load_json_object(manifest_path, "manifest")
    validate_manifest(manifest)
    summary: dict[str, Any] = {
        "manifest": str(manifest_path),
        "manifestSha256": manifest_sha256(manifest),
        "adapterId": manifest["adapterId"],
        "scopeId": manifest["scope"]["scopeId"],
    }
    if result_path is not None:
        result = load_json_object(result_path, "result")
        validate_result(result)
        finding = export_finding(manifest, result)
        summary.update(
            {
                "result": str(result_path),
                "findingId": finding["id"],
                "pathLength": len(finding["minimalFailingPath"]),
            }
        )
    return summary


def _forge_version() -> str | None:
    executable = shutil.which("forge")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else "forge"


def doctor(require_forge: bool = False) -> dict[str, Any]:
    forge = _forge_version()
    if require_forge and forge is None:
        raise ProductError("forge is required but was not found or could not be executed")
    slither_path = shutil.which("slither")
    return {
        "ok": forge is not None or not require_forge,
        "cgqaVersion": __version__,
        "python": sys.version.split()[0],
        "forge": forge,
        "slither": slither_path,
    }


def run_capture(config: ProductConfig, manifest_fingerprint: str) -> None:
    if not config.capture.enabled:
        _require(config.result.is_file(), f"capture disabled and result not found: {config.result}")
        return

    forge = shutil.which("forge")
    _require(forge is not None, "forge is required for capture but was not found on PATH")
    _require(config.working_directory.is_dir(), f"working directory not found: {config.working_directory}")

    config.result.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FOUNDRY_PROFILE"] = config.capture.profile
    env["CGQA_MANIFEST_SHA256"] = manifest_fingerprint
    env["CGQA_RESULT_PATH"] = os.path.relpath(config.result, config.working_directory)

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
        raise ProductError(f"failed to start Foundry capture: {exc}") from exc
    _require(completed.returncode == 0, f"Foundry capture failed with exit code {completed.returncode}")
    _require(config.result.is_file(), f"capture completed but result file was not produced: {config.result}")


def write_finding_and_report(config: ProductConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_json_object(config.manifest, "manifest")
    result = load_json_object(config.result, "result")
    finding = export_finding(manifest, result)
    rendered = render_markdown(finding)

    config.finding.parent.mkdir(parents=True, exist_ok=True)
    config.report.parent.mkdir(parents=True, exist_ok=True)
    config.finding.write_text(canonical_json(finding), encoding="utf-8")
    config.report.write_text(rendered, encoding="utf-8")
    return manifest, finding


def _bundle_manifest(
    manifest: dict[str, Any], finding: dict[str, Any], payloads: dict[str, bytes]
) -> dict[str, Any]:
    return {
        "bundleVersion": 1,
        "tool": {"name": "contractgraph-qa", "version": __version__},
        "findingId": finding["id"],
        "manifestSha256": manifest_sha256(manifest),
        "artifacts": {
            name: {"sha256": sha256_bytes(payloads[name]), "bytes": len(payloads[name])}
            for name in ("manifest.json", "result.json", "finding.json", "report.md")
        },
    }


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def create_evidence_bundle(config: ProductConfig, manifest: dict[str, Any], finding: dict[str, Any]) -> dict[str, Any]:
    payloads = {
        "manifest.json": config.manifest.read_bytes(),
        "result.json": config.result.read_bytes(),
        "finding.json": config.finding.read_bytes(),
        "report.md": config.report.read_bytes(),
    }
    for name, payload in payloads.items():
        _require(len(payload) <= MAX_BUNDLE_ENTRY_BYTES, f"artifact too large for evidence bundle: {name}")

    bundle_manifest = _bundle_manifest(manifest, finding, payloads)
    payloads["bundle.json"] = canonical_json(bundle_manifest).encode("utf-8")

    config.bundle.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(config.bundle, "w") as archive:
        for name in BUNDLE_FILES:
            archive.writestr(_zip_entry(name), payloads[name])
    return bundle_manifest


def verify_evidence_bundle(path: Path) -> dict[str, Any]:
    source = path.expanduser().resolve()
    _require(source.is_file(), f"bundle not found: {source}")
    try:
        with zipfile.ZipFile(source, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _require(names == list(BUNDLE_FILES), "bundle entries are missing, reordered, or unexpected")
            for info in infos:
                _require(info.file_size <= MAX_BUNDLE_ENTRY_BYTES, f"bundle entry exceeds size limit: {info.filename}")
            payloads = {name: archive.read(name) for name in BUNDLE_FILES}
    except (OSError, zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise ProductError(f"invalid evidence bundle: {exc}") from exc

    try:
        bundle_manifest = json.loads(payloads["bundle.json"].decode("utf-8"))
        manifest = json.loads(payloads["manifest.json"].decode("utf-8"))
        result = json.loads(payloads["result.json"].decode("utf-8"))
        finding = json.loads(payloads["finding.json"].decode("utf-8"))
        report = payloads["report.md"].decode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProductError(f"bundle contains invalid text/JSON: {exc}") from exc

    _require(isinstance(bundle_manifest, dict), "bundle.json must be an object")
    _reject_extra_keys(bundle_manifest, BUNDLE_MANIFEST_KEYS, "bundle")
    _require(bundle_manifest.get("bundleVersion") == 1, "unsupported bundleVersion")
    _require(isinstance(manifest, dict), "manifest.json must be an object")
    _require(isinstance(result, dict), "result.json must be an object")
    _require(isinstance(finding, dict), "finding.json must be an object")

    tool = bundle_manifest.get("tool")
    _require(isinstance(tool, dict), "bundle.tool must be an object")
    _reject_extra_keys(tool, BUNDLE_TOOL_KEYS, "bundle.tool")
    _require(_non_empty_string(tool.get("name"), "bundle.tool.name") == "contractgraph-qa", "bundle.tool.name mismatch")
    _non_empty_string(tool.get("version"), "bundle.tool.version")

    artifacts = bundle_manifest.get("artifacts")
    _require(isinstance(artifacts, dict), "bundle.json artifacts must be an object")
    _require(set(artifacts) == {"manifest.json", "result.json", "finding.json", "report.md"}, "bundle artifact set mismatch")
    for name in ("manifest.json", "result.json", "finding.json", "report.md"):
        record = artifacts.get(name)
        _require(isinstance(record, dict), f"bundle artifact record missing: {name}")
        _reject_extra_keys(record, ARTIFACT_RECORD_KEYS, f"bundle.artifacts.{name}")
        _require(record.get("sha256") == sha256_bytes(payloads[name]), f"bundle hash mismatch: {name}")
        _require(record.get("bytes") == len(payloads[name]), f"bundle size mismatch: {name}")

    validate_manifest(manifest)
    validate_result(result)
    expected_finding = export_finding(manifest, result)
    _require(
        canonical_json(expected_finding).encode("utf-8") == payloads["finding.json"],
        "finding.json does not match manifest + result",
    )
    _require(render_markdown(expected_finding) == report, "report.md does not match finding.json")
    _require(bundle_manifest.get("findingId") == expected_finding["id"], "bundle findingId mismatch")
    _require(
        bundle_manifest.get("manifestSha256") == manifest_sha256(manifest),
        "bundle manifestSha256 mismatch",
    )

    return {
        "ok": True,
        "bundle": str(source),
        "findingId": expected_finding["id"],
        "manifestSha256": manifest_sha256(manifest),
        "bundleSha256": sha256_file(source),
    }


def run_pipeline(config: ProductConfig, clean: bool = False) -> dict[str, Any]:
    _require(config.manifest.is_file(), f"manifest not found: {config.manifest}")
    manifest = load_json_object(config.manifest, "manifest")
    validate_manifest(manifest)
    fingerprint = manifest_sha256(manifest)

    if clean:
        generated = [config.finding, config.report, config.bundle]
        if config.capture.enabled:
            generated.insert(0, config.result)
        for path in generated:
            if path.is_file():
                path.unlink()

    run_capture(config, fingerprint)
    manifest, finding = write_finding_and_report(config)
    create_evidence_bundle(config, manifest, finding)
    verification = verify_evidence_bundle(config.bundle)

    return {
        "ok": True,
        "cgqaVersion": __version__,
        "findingId": finding["id"],
        "manifestSha256": fingerprint,
        "pathLength": len(finding["minimalFailingPath"]),
        "result": str(config.result),
        "finding": str(config.finding),
        "report": str(config.report),
        "bundle": str(config.bundle),
        "bundleSha256": verification["bundleSha256"],
    }
