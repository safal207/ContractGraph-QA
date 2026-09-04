#!/usr/bin/env python3
"""Verify immutable SDK registry inputs without performing publication."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "sdks/registry-release-v0.1.0.json"
SHA256_LINE = re.compile(r"^([0-9a-f]{64})  ([^/\\]+)$")


class VerificationError(ValueError):
    """The candidate is not the exact preregistered registry input."""


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse JSON {path.name}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise VerificationError(f"cannot read {path.name}: {exc}") from exc
    return digest.hexdigest()


def _regular_file(root: Path, name: str) -> Path:
    if Path(name).name != name:
        raise VerificationError(f"non-basename artifact name: {name!r}")
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise VerificationError(f"missing regular artifact: {name}")
    return path


def _load_policy(path: Path) -> dict[str, object]:
    policy = _read_json(path)
    if not isinstance(policy, dict):
        raise VerificationError("policy must be a JSON object")
    if policy.get("schema") != "contractgraph-qa-sdk-registry-release-policy-v0.1":
        raise VerificationError("unsupported registry release policy schema")
    return policy


def _parse_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"cannot parse {path.name}: {exc}") from exc
    for line in lines:
        match = SHA256_LINE.fullmatch(line)
        if match is None:
            raise VerificationError(f"malformed SHA256SUMS line: {line!r}")
        digest, name = match.groups()
        if name in result:
            raise VerificationError(f"duplicate SHA256SUMS entry: {name}")
        result[name] = digest
    if not result:
        raise VerificationError("SHA256SUMS is empty")
    return result


def _manifest_artifacts(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    raw = manifest.get("artifacts")
    if not isinstance(raw, list):
        raise VerificationError("release manifest artifacts must be an array")
    result: dict[str, dict[str, object]] = {}
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise VerificationError("malformed release manifest artifact")
        name = entry["name"]
        if name in result:
            raise VerificationError(f"duplicate release manifest artifact: {name}")
        result[name] = entry
    return result


def _verify_release_bindings(
    root: Path, policy: dict[str, object], registry: str
) -> tuple[dict[str, object], dict[str, object], Path]:
    release = policy.get("release")
    registries = policy.get("registries")
    if not isinstance(release, dict) or not isinstance(registries, dict):
        raise VerificationError("policy release/registries sections are required")
    registry_policy = registries.get(registry)
    if not isinstance(registry_policy, dict):
        raise VerificationError(f"unsupported registry: {registry}")
    if not str(registry_policy.get("state", "")).startswith("READY_"):
        raise VerificationError(
            f"{registry} transition is not armed: {registry_policy.get('state')}"
        )

    sums_path = _regular_file(root, "SHA256SUMS")
    manifest_path = _regular_file(root, "release-manifest.json")
    if _sha256(sums_path) != release.get("sha256SumsSha256"):
        raise VerificationError("SHA256SUMS digest differs from the frozen policy")
    if _sha256(manifest_path) != release.get("releaseManifestSha256"):
        raise VerificationError("release-manifest.json digest differs from the frozen policy")

    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise VerificationError("release manifest must be a JSON object")
    expected_manifest = {
        "schema": "contractgraph-qa-sdk-release-v0.1",
        "releaseTag": release.get("tag"),
        "version": release.get("version"),
        "sourceCommit": release.get("sourceCommit"),
        "workflowCommit": release.get("workflowCommit"),
        "suiteSha256": release.get("suiteSha256"),
    }
    for field, expected in expected_manifest.items():
        if manifest.get(field) != expected:
            raise VerificationError(
                f"release manifest {field}={manifest.get(field)!r}, expected {expected!r}"
            )
    if manifest.get("authority") != {
        "claimBoundary": release.get("claimBoundary"),
        "mayAuthorizeAction": release.get("mayAuthorizeAction"),
    }:
        raise VerificationError("release manifest authority boundary differs from policy")

    asset_name = registry_policy.get("asset")
    if not isinstance(asset_name, str):
        raise VerificationError(f"{registry} policy omits an asset")
    asset = _regular_file(root, asset_name)
    actual_sha256 = _sha256(asset)
    actual_bytes = asset.stat().st_size
    if actual_sha256 != registry_policy.get("sha256"):
        raise VerificationError(f"{asset_name} digest differs from the frozen policy")
    if actual_bytes != registry_policy.get("bytes"):
        raise VerificationError(f"{asset_name} size differs from the frozen policy")

    checksums = _parse_checksums(sums_path)
    if checksums.get(asset_name) != actual_sha256:
        raise VerificationError(f"SHA256SUMS does not bind {asset_name}")
    artifacts = _manifest_artifacts(manifest)
    if artifacts.get(asset_name) != {
        "bytes": actual_bytes,
        "name": asset_name,
        "sha256": actual_sha256,
    }:
        raise VerificationError(f"release manifest does not bind {asset_name}")
    return release, registry_policy, asset


def _safe_posix_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise VerificationError(f"unsafe archive member: {name!r}")
    return path


def _verify_npm(root: Path, release: dict[str, object], policy: dict[str, object], asset: Path) -> None:
    pack_name = policy.get("npmPackAsset")
    if not isinstance(pack_name, str):
        raise VerificationError("npm policy omits npmPackAsset")
    pack_path = _regular_file(root, pack_name)
    if _sha256(pack_path) != policy.get("npmPackSha256"):
        raise VerificationError("npm-pack.json digest differs from the frozen policy")
    sums = _parse_checksums(_regular_file(root, "SHA256SUMS"))
    if sums.get(pack_name) != policy.get("npmPackSha256"):
        raise VerificationError("SHA256SUMS does not bind npm-pack.json")

    pack = _read_json(pack_path)
    if not isinstance(pack, list) or len(pack) != 1 or not isinstance(pack[0], dict):
        raise VerificationError("npm-pack.json must describe exactly one package")
    metadata = pack[0]
    expected_pack = {
        "id": policy.get("coordinate"),
        "name": policy.get("packageName"),
        "version": release.get("version"),
        "size": policy.get("bytes"),
        "filename": policy.get("asset"),
        "shasum": policy.get("shasum"),
        "integrity": policy.get("integrity"),
    }
    for field, expected in expected_pack.items():
        if metadata.get(field) != expected:
            raise VerificationError(f"npm pack {field} differs from policy")

    payload = asset.read_bytes()
    if hashlib.sha1(payload).hexdigest() != policy.get("shasum"):
        raise VerificationError("npm tarball SHA-1 differs from npm pack metadata")
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")
    if integrity != policy.get("integrity"):
        raise VerificationError("npm tarball integrity differs from npm pack metadata")

    try:
        with tarfile.open(asset, "r:gz") as archive:
            files: dict[str, tarfile.TarInfo] = {}
            for member in archive.getmembers():
                path = _safe_posix_name(member.name)
                if not path.parts or path.parts[0] != "package":
                    raise VerificationError(f"npm member escapes package/: {member.name}")
                if member.issym() or member.islnk() or member.isdev():
                    raise VerificationError(f"npm archive contains a special member: {member.name}")
                if member.isfile():
                    if member.name in files:
                        raise VerificationError(f"duplicate npm archive member: {member.name}")
                    files[member.name] = member
            package_member = files.get("package/package.json")
            if package_member is None:
                raise VerificationError("npm tarball omits package/package.json")
            stream = archive.extractfile(package_member)
            if stream is None:
                raise VerificationError("cannot read npm package.json")
            package_json = json.loads(stream.read().decode("utf-8"))
    except (tarfile.TarError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid npm tarball: {exc}") from exc

    listed_files = metadata.get("files")
    if not isinstance(listed_files, list) or not all(
        isinstance(item, dict) and isinstance(item.get("path"), str)
        for item in listed_files
    ):
        raise VerificationError("npm-pack.json contains a malformed files list")
    expected_files = {"package/" + item["path"] for item in listed_files}
    if len(expected_files) != len(listed_files):
        raise VerificationError("npm-pack.json contains duplicate file entries")
    if set(files) != expected_files:
        raise VerificationError("npm tarball members differ from npm-pack.json")
    if package_json.get("name") != policy.get("packageName"):
        raise VerificationError("npm package name differs from policy")
    if package_json.get("version") != release.get("version"):
        raise VerificationError("npm package version differs from policy")
    if package_json.get("publishConfig") != {"access": "public"}:
        raise VerificationError("npm package is not explicitly public")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _nuget_entries(path: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            entries: dict[str, bytes] = {}
            infos = archive.infolist()
            if len(infos) > 100:
                raise VerificationError("NuGet package contains too many members")
            if sum(info.file_size for info in infos) > 16 * 1024 * 1024:
                raise VerificationError("NuGet package expands beyond 16 MiB")
            for info in infos:
                _safe_posix_name(info.filename)
                if info.flag_bits & 0x1:
                    raise VerificationError(f"encrypted NuGet member: {info.filename}")
                if info.is_dir():
                    continue
                if info.filename in entries:
                    raise VerificationError(f"duplicate NuGet member: {info.filename}")
                entries[info.filename] = archive.read(info)
    except (zipfile.BadZipFile, OSError) as exc:
        raise VerificationError(f"invalid NuGet package: {exc}") from exc

    nuspec_names = [name for name in entries if name.lower().endswith(".nuspec")]
    if len(nuspec_names) != 1:
        raise VerificationError("NuGet package must contain exactly one nuspec")
    try:
        root = ET.fromstring(entries[nuspec_names[0]].decode("utf-8-sig"))
    except (UnicodeError, ET.ParseError) as exc:
        raise VerificationError(f"invalid NuGet nuspec: {exc}") from exc
    metadata_node = next((node for node in root if _local_name(node.tag) == "metadata"), None)
    if metadata_node is None:
        raise VerificationError("NuGet nuspec omits metadata")
    metadata = {
        _local_name(node.tag): (node.text or "").strip()
        for node in metadata_node
        if _local_name(node.tag) != "dependencies"
    }
    repository = next(
        (node for node in metadata_node if _local_name(node.tag) == "repository"), None
    )
    if repository is not None:
        metadata.update({f"repository.{key}": value for key, value in repository.attrib.items()})
    return entries, metadata


def _verify_nuget(release: dict[str, object], policy: dict[str, object], asset: Path) -> None:
    entries, metadata = _nuget_entries(asset)
    expected = {
        "id": policy.get("packageName"),
        "version": release.get("version"),
        "authors": "safal207",
        "license": "Apache-2.0",
        "repository.type": "git",
        "repository.url": "https://github.com/safal207/ContractGraph-QA",
        "repository.commit": release.get("sourceCommit"),
    }
    for field, value in expected.items():
        if metadata.get(field) != value:
            raise VerificationError(f"NuGet {field} differs from policy")
    if "lib/net8.0/ContractGraphQA.Interop.dll" not in entries:
        raise VerificationError("NuGet package omits the net8.0 adapter DLL")
    if "README.md" not in entries:
        raise VerificationError("NuGet package omits README.md")


def verify_bundle(registry: str, bundle: Path, policy_path: Path) -> dict[str, object]:
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise VerificationError(f"bundle is not a directory: {bundle}")
    policy = _load_policy(policy_path)
    release, registry_policy, asset = _verify_release_bindings(bundle, policy, registry)
    if registry == "npm":
        _verify_npm(bundle, release, registry_policy, asset)
    elif registry == "nuget":
        _verify_nuget(release, registry_policy, asset)
    else:
        raise VerificationError(f"unsupported registry: {registry}")
    return {
        "schema": "contractgraph-qa-sdk-registry-preflight-v0.1",
        "status": "VERIFIED",
        "registry": registry,
        "coordinate": registry_policy["coordinate"],
        "asset": asset.name,
        "assetSha256": registry_policy["sha256"],
        "releaseTag": release["tag"],
        "sourceCommit": release["sourceCommit"],
        "claimBoundary": release["claimBoundary"],
        "mayAuthorizeAction": False,
    }


def compare_nuget(source: Path, candidate: Path, policy_path: Path) -> dict[str, object]:
    policy = _load_policy(policy_path)
    release = policy["release"]
    nuget_policy = policy["registries"]["nuget"]
    if _sha256(source) != nuget_policy["sha256"]:
        raise VerificationError("source NuGet digest differs from the frozen policy")
    if source.stat().st_size != nuget_policy["bytes"]:
        raise VerificationError("source NuGet size differs from the frozen policy")
    source_entries, _ = _nuget_entries(source)
    candidate_entries, candidate_metadata = _nuget_entries(candidate)
    _verify_nuget(release, nuget_policy, source)
    _verify_nuget(release, nuget_policy, candidate)
    allowed_candidate_entries = set(source_entries) | {".signature.p7s"}
    if set(candidate_entries) not in (set(source_entries), allowed_candidate_entries):
        raise VerificationError("registry NuGet contains an unexpected archive delta")
    compared = sorted(source_entries)
    for name in compared:
        if source_entries.get(name) != candidate_entries.get(name):
            raise VerificationError(f"registry NuGet payload differs at {name}")
    return {
        "schema": "contractgraph-qa-sdk-nuget-replication-v0.1",
        "status": "VERIFIED",
        "coordinate": nuget_policy["coordinate"],
        "sourceCommit": release["sourceCommit"],
        "repositoryCommit": candidate_metadata["repository.commit"],
        "comparedPayloads": compared,
        "registrySignatureAllowed": True,
        "mayAuthorizeAction": False,
    }


def _write_evidence(result: dict[str, object], output: Path | None) -> None:
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output is None:
        sys.stdout.write(serialized)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-bundle")
    verify.add_argument("--registry", choices=("npm", "nuget"), required=True)
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--evidence", type=Path)

    compare = subparsers.add_parser("compare-nuget")
    compare.add_argument("--source", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    compare.add_argument("--evidence", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "verify-bundle":
            result = verify_bundle(args.registry, args.bundle, args.policy)
        else:
            result = compare_nuget(args.source, args.candidate, args.policy)
        _write_evidence(result, args.evidence)
    except VerificationError as exc:
        print(f"registry release verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
