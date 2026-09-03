from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

from contractgraph_qa.interop_conformance import (
    CLAIM_BOUNDARY,
    SUITE_SHA256,
    load_interop_conformance_suite,
    run_interop_conformance_suite,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "sdks/testdata/pass-report.json"
SDK_SOURCES = (
    ROOT / "sdks/typescript/src/index.js",
    ROOT / "sdks/go/validator.go",
    ROOT / "sdks/java/src/main/java/org/contractgraphqa/interop/InteropReportValidator.java",
    ROOT / "sdks/dotnet/src/ContractGraphQA.Interop/InteropReportValidator.cs",
)
LOCALES = ("en", "zh-CN", "hi", "es", "ar")
LOCAL_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


class SdkPortabilityTest(unittest.TestCase):
    def test_shared_pass_fixture_matches_the_native_reference(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        native = run_interop_conformance_suite()

        for field in (
            "schema",
            "suiteId",
            "suiteVersion",
            "suiteSha256",
            "status",
            "counts",
            "contractPins",
            "authority",
            "claimBoundary",
        ):
            self.assertEqual(fixture[field], native[field], field)

        native_results = {result["id"]: result for result in native["results"]}
        fixture_results = {result["id"]: result for result in fixture["results"]}
        self.assertEqual(set(fixture_results), set(native_results))
        for case_id, result in fixture_results.items():
            for field in (
                "id",
                "contract",
                "category",
                "status",
                "expectedSemantics",
                "observedSemantics",
                "inputSha256",
                "sideEffectExecuted",
            ):
                self.assertEqual(result[field], native_results[case_id][field], f"{case_id}.{field}")
            self.assertTrue(result["diagnostic"].strip())

    def test_every_sdk_source_contains_every_normative_pin(self) -> None:
        suite = load_interop_conformance_suite()
        required = {SUITE_SHA256, CLAIM_BOUNDARY}
        for contract in suite["contracts"]:
            required.update(
                {
                    contract["id"],
                    contract["artifactSchema"],
                    contract["artifactProfile"],
                    contract["ownerRepository"],
                    contract["producerCommit"],
                    contract["schemaSha256"],
                    contract["fixtureSha256"],
                }
            )
        for case in suite["cases"]:
            required.update(
                {
                    case["id"],
                    case["contract"],
                    case["category"],
                    case["expectedSemantics"],
                    case["expectedInputSha256"],
                }
            )

        for source in SDK_SOURCES:
            text = source.read_text(encoding="utf-8")
            missing = sorted(value for value in required if value not in text)
            self.assertEqual(missing, [], f"{source.relative_to(ROOT)} omits normative pins")

    def test_five_localized_guides_preserve_the_machine_boundary(self) -> None:
        guides = [ROOT / f"docs/i18n/{locale}/GETTING_STARTED.md" for locale in LOCALES]
        self.assertTrue(all(guide.is_file() for guide in guides))
        for guide in guides:
            text = guide.read_text(encoding="utf-8")
            for marker in ("14", "mayAuthorizeAction", "false", "PASS", "1 MiB"):
                self.assertIn(marker, text, f"{guide.relative_to(ROOT)} omits {marker}")
            for target in LOCAL_LINK.findall(text):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (guide.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(resolved.exists(), f"broken link in {guide.relative_to(ROOT)}: {target}")

    def test_package_metadata_is_parseable_and_ci_never_publishes(self) -> None:
        package = json.loads((ROOT / "sdks/typescript/package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "@contractgraph-qa/interop-report")
        self.assertEqual(package["version"], "0.1.0")
        ET.parse(ROOT / "sdks/java/pom.xml")
        for project in (ROOT / "sdks/dotnet").rglob("*.csproj"):
            ET.parse(project)
        self.assertIn(
            "module github.com/safal207/ContractGraph-QA/sdks/go",
            (ROOT / "sdks/go/go.mod").read_text(encoding="utf-8"),
        )

        workflow = (ROOT / ".github/workflows/sdk-portability.yml").read_text(encoding="utf-8")
        for forbidden in ("npm publish", "mvn deploy", "dotnet nuget push", "git push"):
            self.assertNotIn(forbidden, workflow)
        action_refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", workflow)
        self.assertTrue(action_refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs))

    def test_sdk_release_workflow_is_exact_subject_and_registry_bounded(self) -> None:
        workflow = (
            ROOT / ".github/workflows/release-sdk-v0.1.0.yml"
        ).read_text(encoding="utf-8")

        for marker in (
            "TARGET_SHA: de7c765243dc86226b8554757ef1f9419c194a4c",
            "VERSION: 0.1.0",
            "RELEASE_TAG: interop-sdk-v0.1.0",
            "GO_TAG: sdks/go/v0.1.0",
            "git merge-base --is-ancestor",
            "sha256sum -c SHA256SUMS",
            "actions/attest@",
            "gh release create",
            "GOPROXY=https://proxy.golang.org",
            "mayAuthorizeAction",
            "if: github.event_name == 'push'",
            "actions/download-artifact@",
        ):
            self.assertIn(marker, workflow)

        for forbidden in (
            "npm publish",
            "dotnet nuget push",
            "mvn deploy",
            "NPM_TOKEN",
            "NUGET_API_KEY",
            "MAVEN_PASSWORD",
        ):
            self.assertNotIn(forbidden, workflow)

        action_refs = re.findall(r"uses:\s*[^@\s]+@([^\s]+)", workflow)
        self.assertTrue(action_refs)
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs))

        build_block, publish_block = workflow.split("\n  publish:\n", 1)
        self.assertIn("permissions:\n  contents: read", build_block)
        self.assertIn("persist-credentials: false", build_block)
        for forbidden in ("contents: write", "git push", "gh release create", "actions/attest@"):
            self.assertNotIn(forbidden, build_block)
        for required in ("needs: build", "contents: write", "git push", "gh release create"):
            self.assertIn(required, publish_block)

        self.assertLess(
            workflow.index("Upload pre-publication evidence"),
            workflow.index("Create or verify exact tags"),
        )
        self.assertLess(
            workflow.index("Revalidate subject, destinations, and checksums"),
            workflow.index("Create or verify exact tags"),
        )


if __name__ == "__main__":
    unittest.main()
