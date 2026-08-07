from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from render_finding import load_finding, render_markdown, validate_finding  # noqa: E402


class FindingReportRendererTest(unittest.TestCase):
    def setUp(self) -> None:
        self.finding_path = ROOT / "reports" / "examples" / "CGQA-001.finding.json"
        self.report_path = ROOT / "reports" / "examples" / "CGQA-001.md"
        self.finding = load_finding(self.finding_path)

    def test_sample_matches_checked_in_report(self) -> None:
        rendered = render_markdown(self.finding)
        expected = self.report_path.read_text(encoding="utf-8")
        self.assertEqual(rendered, expected)

    def test_rendering_is_deterministic(self) -> None:
        first = render_markdown(self.finding)
        second = render_markdown(copy.deepcopy(self.finding))
        self.assertEqual(first, second)

    def test_empty_failing_path_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["minimalFailingPath"] = []
        with self.assertRaisesRegex(ValueError, "must be non-empty"):
            validate_finding(invalid)

    def test_non_contiguous_steps_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["minimalFailingPath"][1]["step"] = 3
        with self.assertRaisesRegex(ValueError, "contiguous and 1-based"):
            validate_finding(invalid)


if __name__ == "__main__":
    unittest.main()
