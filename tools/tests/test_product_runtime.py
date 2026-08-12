from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.product import (
    CaptureConfig,
    ProductConfig,
    ProductError,
    load_product_config,
    run_pipeline,
    validate_manifest_result,
    verify_evidence_bundle,
)


class ProductRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.manifest = cls.root / "manifests/examples/adapter-fixture.json"
        cls.result = cls.root / "results/examples/CGQA-005.result.json"
        cls.reachability_model = cls.root / "scenarios/adversarial-wallet-replay.json"

    def test_example_config_loads(self) -> None:
        config = load_product_config(self.root / "cgqa.example.toml")
        self.assertEqual(config.capture.profile, "capture")
        self.assertEqual(config.capture.test, "test_CaptureExplorerResult")
        self.assertTrue(config.capture.enabled)
        self.assertEqual(config.manifest, self.manifest.resolve())
        self.assertIsNone(config.reachability_model)

    def test_config_loads_optional_reachability_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config_path = temp / "cgqa.toml"
            config_path.write_text(
                "schemaVersion = 1\n"
                "manifest = 'manifest.json'\n"
                "result = 'result.json'\n"
                "finding = 'finding.json'\n"
                "report = 'report.md'\n"
                "bundle = 'evidence.zip'\n"
                "reachabilityModel = 'reachability.json'\n",
                encoding="utf-8",
            )
            config = load_product_config(config_path)
            self.assertEqual(config.reachability_model, (temp / "reachability.json").resolve())

    def test_manifest_result_validation(self) -> None:
        summary = validate_manifest_result(self.manifest, self.result)
        self.assertEqual(summary["findingId"], "CGQA-005")
        self.assertEqual(summary["pathLength"], 3)

    def test_pipeline_bundle_is_deterministic_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            manifest = temp / "manifest.json"
            result = temp / "result.json"
            manifest.write_bytes(self.manifest.read_bytes())
            result.write_bytes(self.result.read_bytes())

            config = ProductConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=manifest,
                result=result,
                finding=temp / "finding.json",
                report=temp / "report.md",
                bundle=temp / "evidence.zip",
                capture=CaptureConfig(
                    enabled=False,
                    profile="capture",
                    test="test_CaptureExplorerResult",
                    verbosity=3,
                ),
            )

            first = run_pipeline(config)
            first_bytes = config.bundle.read_bytes()
            second = run_pipeline(config)
            second_bytes = config.bundle.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["bundleSha256"], second["bundleSha256"])
            self.assertEqual(first["bundleVersion"], 1)
            verified = verify_evidence_bundle(config.bundle)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["findingId"], "CGQA-005")
            self.assertEqual(verified["bundleVersion"], 1)

    def test_pipeline_can_bind_reachability_into_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = ProductConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=self.manifest,
                result=self.result,
                finding=temp / "finding.json",
                report=temp / "report.md",
                bundle=temp / "evidence.zip",
                capture=CaptureConfig(
                    enabled=False,
                    profile="capture",
                    test="test_CaptureExplorerResult",
                    verbosity=3,
                ),
                reachability_model=self.reachability_model,
            )

            first = run_pipeline(config)
            first_bytes = config.bundle.read_bytes()
            second = run_pipeline(config)
            second_bytes = config.bundle.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["bundleVersion"], 2)
            self.assertEqual(first["reachabilityStatus"], "reachable")
            self.assertEqual(first["bundleSha256"], second["bundleSha256"])

            with zipfile.ZipFile(config.bundle, "r") as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "manifest.json",
                        "result.json",
                        "reachability-model.json",
                        "reachability.json",
                        "finding.json",
                        "report.md",
                        "bundle.json",
                    ],
                )
                finding = json.loads(archive.read("finding.json"))
                reachability = json.loads(archive.read("reachability.json"))

            bound = finding["evidence"]["reachability"]
            self.assertEqual(bound["artifact"], "reachability.json")
            self.assertEqual(bound["modelArtifact"], "reachability-model.json")
            self.assertEqual(bound["modelSha256"], reachability["modelSha256"])
            self.assertEqual(bound["path"]["targetCapability"], "overspend")

            verified = verify_evidence_bundle(config.bundle)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["bundleVersion"], 2)
            self.assertEqual(verified["reachabilityStatus"], "reachable")
            self.assertEqual(
                verified["reachabilityModelSha256"], first["reachabilityModelSha256"]
            )

    def test_bundle_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = ProductConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=self.manifest,
                result=self.result,
                finding=temp / "finding.json",
                report=temp / "report.md",
                bundle=temp / "evidence.zip",
                capture=CaptureConfig(
                    enabled=False,
                    profile="capture",
                    test="test_CaptureExplorerResult",
                    verbosity=3,
                ),
            )
            run_pipeline(config)

            with zipfile.ZipFile(config.bundle, "r") as source:
                entries = [(info, source.read(info.filename)) for info in source.infolist()]
            with zipfile.ZipFile(config.bundle, "w") as target:
                for info, data in entries:
                    if info.filename == "report.md":
                        data += b"\ntampered\n"
                    target.writestr(info, data)

            with self.assertRaisesRegex(ProductError, "hash mismatch: report.md"):
                verify_evidence_bundle(config.bundle)

    def test_reachability_bundle_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = ProductConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=self.manifest,
                result=self.result,
                finding=temp / "finding.json",
                report=temp / "report.md",
                bundle=temp / "evidence.zip",
                capture=CaptureConfig(
                    enabled=False,
                    profile="capture",
                    test="test_CaptureExplorerResult",
                    verbosity=3,
                ),
                reachability_model=self.reachability_model,
            )
            run_pipeline(config)

            with zipfile.ZipFile(config.bundle, "r") as source:
                entries = [(info, source.read(info.filename)) for info in source.infolist()]
            with zipfile.ZipFile(config.bundle, "w") as target:
                for info, data in entries:
                    if info.filename == "reachability.json":
                        data += b"\n"
                    target.writestr(info, data)

            with self.assertRaisesRegex(ProductError, "hash mismatch: reachability.json"):
                verify_evidence_bundle(config.bundle)

    def test_clean_preserves_result_when_capture_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            result = temp / "input.result.json"
            original = self.result.read_bytes()
            result.write_bytes(original)
            config = ProductConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=self.manifest,
                result=result,
                finding=temp / "finding.json",
                report=temp / "report.md",
                bundle=temp / "evidence.zip",
                capture=CaptureConfig(
                    enabled=False,
                    profile="capture",
                    test="test_CaptureExplorerResult",
                    verbosity=3,
                ),
            )
            run_pipeline(config, clean=True)
            self.assertEqual(result.read_bytes(), original)

    def test_config_rejects_unexpected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nmanifest = 'x'\nresult = 'y'\nfinding = 'z'\nreport = 'r'\nbundle = 'b.zip'\nunexpected = true\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProductError, "unexpected fields"):
                load_product_config(path)

    def test_config_rejects_unsafe_capture_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nmanifest = 'x'\nresult = 'y'\nfinding = 'z'\nreport = 'r'\nbundle = 'b.zip'\n[capture]\ntest = 'x;rm'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProductError, "unsafe characters"):
                load_product_config(path)

    def test_config_rejects_artifact_path_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nmanifest = 'same.json'\nresult = 'same.json'\nfinding = 'z.json'\nreport = 'r.md'\nbundle = 'b.zip'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ProductError, "artifact paths must be distinct"):
                load_product_config(path)


if __name__ == "__main__":
    unittest.main()
