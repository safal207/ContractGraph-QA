from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.demo import run_demo
from contractgraph_qa.product import ProductError, verify_evidence_bundle


class SelfServeDemoTest(unittest.TestCase):
    def test_demo_builds_verified_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "demo"
            summary = run_demo(destination)

            self.assertTrue(summary["ok"])
            self.assertTrue(summary["demo"])
            self.assertEqual(summary["findingId"], "CGQA-005")
            bundle = Path(str(summary["bundle"]))
            self.assertTrue(bundle.is_file())
            self.assertTrue(verify_evidence_bundle(bundle)["ok"])
            self.assertTrue((destination / "CGQA-005.finding.json").is_file())
            self.assertTrue((destination / "CGQA-005.md").is_file())

    def test_demo_refuses_non_empty_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "demo"
            destination.mkdir()
            (destination / "keep.txt").write_text("do not overwrite", encoding="utf-8")

            with self.assertRaisesRegex(ProductError, "not empty"):
                run_demo(destination)
            self.assertEqual(
                (destination / "keep.txt").read_text(encoding="utf-8"),
                "do not overwrite",
            )


if __name__ == "__main__":
    unittest.main()
