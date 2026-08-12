from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.cli import EXIT_OK, main as cli_main
from contractgraph_qa.control_bundle import (
    CONTROL_BUNDLE_FILES,
    create_control_evidence_bundle,
    verify_control_evidence_bundle,
)
from contractgraph_qa.postimpact import load_post_impact_model
from contractgraph_qa.product import CaptureConfig, ProductConfig, ProductError, run_pipeline


class ControlEvidenceBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.manifest = cls.root / "manifests/examples/adapter-fixture.json"
        cls.result = cls.root / "results/examples/CGQA-005.result.json"
        cls.reachability_model = cls.root / "scenarios/adversarial-adapter-fixture.json"
        cls.post_impact_model = cls.root / "scenarios/post-impact-adapter-fixture.json"

    def _base_config(self, temp: Path) -> ProductConfig:
        return ProductConfig(
            source=temp / "cgqa.toml",
            working_directory=self.root,
            manifest=self.manifest,
            result=self.result,
            finding=temp / "finding.json",
            report=temp / "report.md",
            bundle=temp / "base.evidence.zip",
            capture=CaptureConfig(
                enabled=False,
                profile="capture",
                test="test_CaptureExplorerResult",
                verbosity=3,
            ),
            reachability_model=self.reachability_model,
        )

    def test_control_bundle_is_deterministic_and_independently_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = self._base_config(temp)
            base = run_pipeline(config)
            self.assertEqual(base["bundleVersion"], 2)

            post_model = load_post_impact_model(self.post_impact_model)
            output = temp / "control.evidence.zip"
            first = create_control_evidence_bundle(config.bundle, post_model, output)
            first_bytes = output.read_bytes()
            second = create_control_evidence_bundle(config.bundle, post_model, output)
            second_bytes = output.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["bundleVersion"], 3)
            self.assertEqual(first["postImpactStatus"], "contained_and_verified")
            self.assertEqual(first["bundleSha256"], second["bundleSha256"])

            with zipfile.ZipFile(output, "r") as archive:
                self.assertEqual(tuple(archive.namelist()), CONTROL_BUNDLE_FILES)
                self.assertIn("post-impact-model.json", archive.namelist())
                self.assertIn("post-impact.json", archive.namelist())
                self.assertIn("base-bundle.json", archive.namelist())

            verified = verify_control_evidence_bundle(output)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["bundleVersion"], 3)
            self.assertEqual(verified["findingId"], "CGQA-005")
            self.assertEqual(verified["postImpactStatus"], "contained_and_verified")
            self.assertEqual(verified["boundTargetCapability"], "terminal-state-reachable")

    def test_cli_builds_and_verifies_control_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = self._base_config(temp)
            run_pipeline(config)
            output = temp / "control.evidence.zip"

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                build_code = cli_main(
                    [
                        "control-bundle-build",
                        "--base-bundle",
                        str(config.bundle),
                        "--post-impact-model",
                        str(self.post_impact_model),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(build_code, EXIT_OK)
            built = json.loads(stdout.getvalue())
            self.assertEqual(built["bundleVersion"], 3)
            self.assertEqual(built["postImpactStatus"], "contained_and_verified")
            self.assertTrue(output.is_file())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                verify_code = cli_main(["verify-control-bundle", str(output)])
            self.assertEqual(verify_code, EXIT_OK)
            verified = json.loads(stdout.getvalue())
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["bundleVersion"], 3)
            self.assertEqual(verified["boundTargetCapability"], "terminal-state-reachable")

    def test_post_impact_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = self._base_config(temp)
            run_pipeline(config)
            output = temp / "control.evidence.zip"
            create_control_evidence_bundle(
                config.bundle,
                load_post_impact_model(self.post_impact_model),
                output,
            )

            with zipfile.ZipFile(output, "r") as source:
                entries = [(info, source.read(info.filename)) for info in source.infolist()]
            with zipfile.ZipFile(output, "w") as target:
                for info, data in entries:
                    if info.filename == "post-impact.json":
                        data += b"\n"
                    target.writestr(info, data)

            with self.assertRaisesRegex(ProductError, "hash mismatch: post-impact.json"):
                verify_control_evidence_bundle(output)

    def test_control_bundle_requires_verified_reachability_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = self._base_config(temp)
            config = ProductConfig(
                source=config.source,
                working_directory=config.working_directory,
                manifest=config.manifest,
                result=config.result,
                finding=config.finding,
                report=config.report,
                bundle=config.bundle,
                capture=config.capture,
                reachability_model=None,
            )
            run_pipeline(config)

            with self.assertRaisesRegex(ProductError, "requires a reachability-aware bundle v2"):
                create_control_evidence_bundle(
                    config.bundle,
                    load_post_impact_model(self.post_impact_model),
                    temp / "control.evidence.zip",
                )


if __name__ == "__main__":
    unittest.main()
