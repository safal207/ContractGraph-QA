from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contractgraph_qa.engagement import verify_engagement_bundle
from contractgraph_qa.engagement_run import (
    EngagementCaptureConfig,
    EngagementRunConfig,
    EngagementRunError,
    _run_direct_capture,
    load_engagement_run_config,
    run_engagement_pipeline,
)


class EngagementRunRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.manifest = cls.root / "manifests/examples/engagement-fixture.json"
        cls.golden_result = cls.root / "results/examples/CGQA-E-001.engagement-result.json"

    def _runtime_config(self, temp: Path) -> EngagementRunConfig:
        return EngagementRunConfig(
            source=temp / "cgqa.toml",
            working_directory=self.root,
            manifest=self.manifest,
            result=temp / "generated" / "engagement-result.json",
            output_directory=temp / "dist",
            bundle=temp / "dist" / "engagement.zip",
            capture=EngagementCaptureConfig(
                profile="capture",
                test="test_CaptureMultiInvariantEngagementResult",
                verbosity=3,
            ),
        )

    def test_example_config_loads(self) -> None:
        config = load_engagement_run_config(self.root / "cgqa.engagement.example.toml")
        self.assertEqual(config.capture.profile, "capture")
        self.assertEqual(config.capture.test, "test_CaptureMultiInvariantEngagementResult")
        self.assertEqual(config.manifest, self.manifest.resolve())
        self.assertEqual(config.bundle.suffix, ".zip")

    def test_pipeline_builds_verified_bundle_from_fresh_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            config = self._runtime_config(temp)

            def fake_capture(runtime_config: EngagementRunConfig, fingerprint: str) -> None:
                self.assertTrue(fingerprint)
                runtime_config.result.parent.mkdir(parents=True, exist_ok=True)
                runtime_config.result.write_bytes(self.golden_result.read_bytes())

            with patch(
                "contractgraph_qa.engagement_run._run_direct_capture",
                side_effect=fake_capture,
            ):
                first = run_engagement_pipeline(config)
                first_bytes = config.bundle.read_bytes()
                second = run_engagement_pipeline(config)
                second_bytes = config.bundle.read_bytes()

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
            verified = verify_engagement_bundle(config.bundle)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["engagementId"], "CGQA-E-001")

    def test_capture_cannot_reuse_stale_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = self._runtime_config(Path(temp_dir))
            config.result.parent.mkdir(parents=True, exist_ok=True)
            config.result.write_text("stale", encoding="utf-8")
            completed = subprocess.CompletedProcess(args=["forge"], returncode=0)

            with patch("contractgraph_qa.engagement_run.shutil.which", return_value="/usr/bin/forge"):
                with patch("contractgraph_qa.engagement_run.subprocess.run", return_value=completed):
                    with self.assertRaisesRegex(EngagementRunError, "fresh result"):
                        _run_direct_capture(config, "0" * 64)

            self.assertFalse(config.result.exists())

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
