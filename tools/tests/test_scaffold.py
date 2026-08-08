from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.engagement_run import load_engagement_run_config
from contractgraph_qa.finding import validate_manifest
from contractgraph_qa.scaffold import ScaffoldError, init_engagement


class ScaffoldTest(unittest.TestCase):
    def _inside_project(self, root: Path, callback) -> None:
        previous = Path.cwd()
        os.chdir(root)
        try:
            callback()
        finally:
            os.chdir(previous)

    def test_init_creates_structurally_valid_fail_closed_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def run() -> None:
                summary = init_engagement("acme-escrow")
                destination = root / "engagements" / "acme-escrow"
                self.assertEqual(Path(summary["directory"]), destination)
                self.assertFalse(summary["executionReady"])
                self.assertEqual(
                    summary["files"],
                    [
                        ".gitignore",
                        "README.md",
                        "capture/ClientEngagementCapture.t.sol.example",
                        "cgqa.toml",
                        "manifest.json",
                    ],
                )

                manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
                validate_manifest(manifest)
                self.assertEqual(manifest["adapterId"], "acme-escrow-adapter")
                self.assertIn("TODO", manifest["scope"]["authorization"])

                config = load_engagement_run_config(destination / "cgqa.toml")
                self.assertEqual(config.working_directory, root)
                self.assertTrue(config.result.is_relative_to(root))
                self.assertEqual(config.capture.test, "test_ClientEngagementCapture")

                template = (
                    destination / "capture" / "ClientEngagementCapture.t.sol.example"
                ).read_text(encoding="utf-8")
                self.assertIn("CGQA scaffold not configured", template)
                self.assertFalse((destination / "capture" / "ClientEngagementCapture.t.sol").exists())

            self._inside_project(root, run)

    def test_existing_destination_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def run() -> None:
                init_engagement("client-a")
                with self.assertRaisesRegex(ScaffoldError, "already exists"):
                    init_engagement("client-a")

            self._inside_project(root, run)

    def test_invalid_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def run() -> None:
                with self.assertRaisesRegex(ScaffoldError, "engagement name"):
                    init_engagement("../escape")

            self._inside_project(root, run)

    def test_destination_outside_project_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            root = base / "project"
            root.mkdir()
            outside = base / "outside"

            def run() -> None:
                with self.assertRaisesRegex(ScaffoldError, "inside the current project root"):
                    init_engagement("client-a", outside)

            self._inside_project(root, run)


if __name__ == "__main__":
    unittest.main()
