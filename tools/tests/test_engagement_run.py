from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contractgraph_qa.engagement import verify_engagement_bundle
from contractgraph_qa.engagement_run import (
    EngagementCaptureConfig,
    EngagementRunConfig,
    EngagementRunError,
    load_engagement_run_config,
    run_engagement_pipeline,
)


class EngagementRunRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.manifest = cls.root / "manifests/examples/engagement-fixture.json"
        cls.golden_result = cls.root / "results/examples/CGQA-E-001.engagement-result.json"

    def test_example_config_loads(self) -> None:
        config = load_engagement_run_config(self.root / "cgqa.engagement.example.toml")
        self.assertEqual(config.capture.profile, "capture")
        self.assertEqual(config.capture.test, "test_CaptureMultiInvariantEngagementResult")
        self.assertEqual(config.manifest, self.manifest.resolve())
        self.assertEqual(config.bundle.suffix, ".zip")

    def test_pipeline_builds_verified_bundle_from_fresh_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            result = temp / "generated" / "engagement-result.json"
            output = temp / "dist"
            bundle = output / "engagement.zip"
            config = EngagementRunConfig(
                source=temp / "cgqa.toml",
                working_directory=self.root,
                manifest=self.manifest,
                result=result,
                output_directory=output,
                bundle=bundle,
                capture=EngagementCaptureConfig(
                    profile="capture",
                    test="test_CaptureMultiInvariantEngagementResult",
                    verbosity=3,
                ),
            )

            def fake_capture(runtime_config: EngagementRunConfig, fingerprint: str) -> None:
                self.assertTrue(fingerprint)
                runtime_config.result.parent.mkdir(parents=True, exist_ok=True)
                runtime_config.result.write_bytes(self.golden_result.read_bytes())

            with patch(
                "contractgraph_qa.engagement_run._run_direct_capture",
                side_effect=fake_capture,
            ):
                first = run_engagement_pipeline(config)
                first_bytes = bundle.read_bytes()
                second = run_engagement_pipeline(config)
                second_bytes = bundle.read_bytes()

            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first["bundleSha256"], second["bundleSha256"])
            self.assertEqual(
                first["coverage"],
                {
                    "declaredInvariants": 3,
                    "checkedInvariants": 3,
                    "violated": 1,
                    "notFoundWithinBound": 1,
                    "inconclusive": 1,
                },
            )
            verified = verify_engagement_bundle(bundle)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["engagementId"], "CGQA-E-001")

    def test_config_rejects_unexpected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nworkingDirectory = '.'\nmanifest = 'm.json'\nresult = 'r.json'\noutputDirectory = 'out'\nbundle = 'out/e.zip'\nunexpected = true\n[capture]\ntest = 'test_X'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EngagementRunError, "unexpected fields"):
                load_engagement_run_config(path)

    def test_config_rejects_unsafe_capture_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nworkingDirectory = '.'\nmanifest = 'm.json'\nresult = 'r.json'\noutputDirectory = 'out'\nbundle = 'out/e.zip'\n[capture]\ntest = 'x;rm'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EngagementRunError, "unsafe characters"):
                load_engagement_run_config(path)

    def test_config_rejects_output_equal_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.toml"
            path.write_text(
                "schemaVersion = 1\nworkingDirectory = '.'\nmanifest = 'm.json'\nresult = 'r.json'\noutputDirectory = '.'\nbundle = 'e.zip'\n[capture]\ntest = 'test_X'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EngagementRunError, "must not equal workingDirectory"):
                load_engagement_run_config(path)


if __name__ == "__main__":
    unittest.main()
