from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.demo import run_demo
from contractgraph_qa.finding import canonical_json, export_finding, load_json_object
from contractgraph_qa.product import ProductError, verify_evidence_bundle
from contractgraph_qa.report import render_markdown


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

    def test_demo_writes_bundle_artifacts_as_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "demo"
            run_demo(destination)

            manifest = load_json_object(destination / "inputs" / "manifest.json", "manifest")
            result = load_json_object(destination / "inputs" / "result.json", "result")
            finding = export_finding(manifest, result)
            expected_finding = canonical_json(finding).encode("utf-8")
            expected_report = render_markdown(finding).encode("utf-8")

            self.assertEqual(
                (destination / "CGQA-005.finding.json").read_bytes(),
                expected_finding,
            )
            self.assertEqual((destination / "CGQA-005.md").read_bytes(), expected_report)

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
