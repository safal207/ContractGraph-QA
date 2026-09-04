from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
import zipfile

from tools.sdk_registry_release import VerificationError, compare_nuget, verify_bundle


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/publish-sdk-registries-v0.1.0.yml"
POLICY = ROOT / "sdks/registry-release-v0.1.0.json"


def _digest(path: Path, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, path.read_bytes()).hexdigest()


def _write_npm_fixture(root: Path) -> Path:
    package = {
        "name": "@contractgraph-qa/interop-report",
        "version": "0.1.0",
        "publishConfig": {"access": "public"},
    }
    payloads = {
        "package/package.json": json.dumps(package, sort_keys=True).encode(),
        "package/README.md": b"bounded evidence only\n",
    }
    asset = root / "contractgraph-qa-interop-report-0.1.0.tgz"
    with tarfile.open(asset, "w:gz") as archive:
        for name, payload in payloads.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(payload))

    shasum = _digest(asset, "sha1")
    integrity = "sha512-" + base64.b64encode(
        hashlib.sha512(asset.read_bytes()).digest()
    ).decode("ascii")
    pack = [
        {
            "id": "@contractgraph-qa/interop-report@0.1.0",
            "name": "@contractgraph-qa/interop-report",
            "version": "0.1.0",
            "size": asset.stat().st_size,
            "filename": asset.name,
            "shasum": shasum,
            "integrity": integrity,
            "files": [
                {"path": "README.md", "size": len(payloads["package/README.md"])},
                {"path": "package.json", "size": len(payloads["package/package.json"])},
            ],
        }
    ]
    pack_path = root / "npm-pack.json"
    pack_path.write_text(json.dumps(pack), encoding="utf-8")

    release = {
        "tag": "interop-sdk-v0.1.0",
        "version": "0.1.0",
        "sourceCommit": "d" * 40,
        "workflowCommit": "9" * 40,
        "suiteSha256": "5" * 64,
        "claimBoundary": "conformance_evidence_only",
        "mayAuthorizeAction": False,
    }
    manifest = {
        "schema": "contractgraph-qa-sdk-release-v0.1",
        "releaseTag": release["tag"],
        "version": release["version"],
        "sourceCommit": release["sourceCommit"],
        "workflowCommit": release["workflowCommit"],
        "suiteSha256": release["suiteSha256"],
        "authority": {
            "claimBoundary": release["claimBoundary"],
            "mayAuthorizeAction": False,
        },
        "artifacts": [
            {"name": asset.name, "bytes": asset.stat().st_size, "sha256": _digest(asset)},
            {
                "name": pack_path.name,
                "bytes": pack_path.stat().st_size,
                "sha256": _digest(pack_path),
            },
        ],
    }
    manifest_path = root / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    sums_path = root / "SHA256SUMS"
    sums_path.write_text(
        "".join(
            f"{_digest(path)}  {path.name}\n"
            for path in (asset, pack_path, manifest_path)
        ),
        encoding="ascii",
    )
    release.update(
        {
            "releaseManifestSha256": _digest(manifest_path),
            "sha256SumsSha256": _digest(sums_path),
        }
    )
    policy = {
        "schema": "contractgraph-qa-sdk-registry-release-policy-v0.1",
        "release": release,
        "registries": {
            "npm": {
                "state": "READY_TEST",
                "coordinate": "@contractgraph-qa/interop-report@0.1.0",
                "packageName": "@contractgraph-qa/interop-report",
                "asset": asset.name,
                "bytes": asset.stat().st_size,
                "sha256": _digest(asset),
                "npmPackAsset": pack_path.name,
                "npmPackSha256": _digest(pack_path),
                "shasum": shasum,
                "integrity": integrity,
            }
        },
    }
    policy_path = root / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return policy_path


def _write_nuget(path: Path, *, dll: bytes = b"adapter", signature: bool = False) -> None:
    nuspec = b"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://schemas.microsoft.com/packaging/2012/06/nuspec.xsd">
  <metadata>
    <id>ContractGraphQA.Interop</id>
    <version>0.1.0</version>
    <authors>safal207</authors>
    <license type="expression">Apache-2.0</license>
    <repository type="git" url="https://github.com/safal207/ContractGraph-QA" commit="de7c765243dc86226b8554757ef1f9419c194a4c" />
  </metadata>
</package>
"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ContractGraphQA.Interop.nuspec", nuspec)
        archive.writestr("README.md", b"bounded evidence only\n")
        archive.writestr("lib/net8.0/ContractGraphQA.Interop.dll", dll)
        if signature:
            archive.writestr(".signature.p7s", b"registry signature")


class SdkRegistryReleaseTest(unittest.TestCase):
    def test_synthetic_npm_bundle_verifies_and_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = _write_npm_fixture(root)
            result = verify_bundle("npm", root, policy)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertFalse(result["mayAuthorizeAction"])

            asset = root / "contractgraph-qa-interop-report-0.1.0.tgz"
            asset.write_bytes(asset.read_bytes() + b"tamper")
            with self.assertRaisesRegex(VerificationError, "digest differs"):
                verify_bundle("npm", root, policy)

    def test_nuget_replication_allows_only_registry_signature_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.nupkg"
            candidate = root / "candidate.nupkg"
            _write_nuget(source)
            _write_nuget(candidate, signature=True)
            policy_data = json.loads(POLICY.read_text(encoding="utf-8"))
            policy_data["registries"]["nuget"]["sha256"] = _digest(source)
            policy_data["registries"]["nuget"]["bytes"] = source.stat().st_size
            policy = root / "policy.json"
            policy.write_text(json.dumps(policy_data), encoding="utf-8")

            result = compare_nuget(source, candidate, policy)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertTrue(result["registrySignatureAllowed"])

            _write_nuget(candidate, dll=b"different", signature=True)
            with self.assertRaisesRegex(VerificationError, "differs at"):
                compare_nuget(source, candidate, policy)

    def test_frozen_policy_matches_released_source_metadata(self) -> None:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(policy["release"]["sourceCommit"], "de7c765243dc86226b8554757ef1f9419c194a4c")
        self.assertFalse(policy["release"]["mayAuthorizeAction"])
        self.assertEqual(
            policy["registries"]["npm"]["packageName"],
            json.loads((ROOT / "sdks/typescript/package.json").read_text())["name"],
        )
        self.assertEqual(
            policy["registries"]["nuget"]["packageName"],
            "ContractGraphQA.Interop",
        )
        self.assertEqual(
            policy["registries"]["mavenCentral"]["state"],
            "HOLD_FOR_CENTRAL_COMPLETE_0.1.1",
        )

    def test_manual_workflow_has_separated_guards_and_pinned_actions(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:\n", workflow)
        for marker in (
            'test "${GITHUB_ACTOR}" = "safal207"',
            'test "${GITHUB_REF}" = "refs/heads/main"',
            "environment: sdk-registry-release",
            "REGISTRY_RELEASE_ARMED",
            "Require an absent registry version before mutation",
            "Reverify the exact npm input",
            "Reverify the exact NuGet input",
            "npm publish \\",
            "dotnet nuget push \\",
            "NuGet/login@8d196754b4036150537f80ac539e15c2f1028841",
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("mvn deploy", workflow)
        self.assertLess(workflow.index("preflight:"), workflow.index("publish-npm:"))
        self.assertLess(workflow.index("preflight:"), workflow.index("publish-nuget:"))

        refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", workflow)
        self.assertTrue(refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in refs))

        portability = (ROOT / ".github/workflows/sdk-portability.yml").read_text()
        self.assertIn("tools.tests.test_sdk_registry_release", portability)


if __name__ == "__main__":
    unittest.main()
