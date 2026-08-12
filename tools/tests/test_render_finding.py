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

    def _with_reachability(self) -> dict:
        finding = copy.deepcopy(self.finding)
        manifest_sha = finding["evidence"].get("manifestSha256", "b" * 64)
        finding["evidence"]["manifestSha256"] = manifest_sha
        invariant_id = finding["invariant"]["id"]
        finding["evidence"]["reachability"] = {
            "artifact": "reachability.json",
            "modelArtifact": "reachability-model.json",
            "boundManifestSha256": manifest_sha,
            "boundInvariantId": invariant_id,
            "status": "reachable",
            "modelSha256": "a" * 64,
            "maxDepth": 4,
            "violatedAssumptions": ["stale-policy-state"],
            "targetCapabilities": ["forbidden-settlement"],
            "path": {
                "initialCapability": "request-settlement",
                "targetCapability": "forbidden-settlement",
                "violatedAssumptions": ["stale-policy-state"],
                "invariantIds": [invariant_id],
                "crossedBoundaries": ["approval-policy"],
                "impact": "unauthorized settlement becomes reachable",
                "transitions": [
                    {
                        "id": "authorize-with-stale-policy",
                        "source": "request-settlement",
                        "target": "forbidden-settlement",
                        "requiresViolations": ["stale-policy-state"],
                        "invariantId": invariant_id,
                        "boundary": "approval-policy",
                        "impact": "unauthorized settlement becomes reachable",
                    }
                ],
            },
        }
        return finding

    def test_sample_matches_checked_in_report(self) -> None:
        rendered = render_markdown(self.finding)
        expected = self.report_path.read_text(encoding="utf-8")
        self.assertEqual(rendered, expected)

    def test_rendering_is_deterministic(self) -> None:
        first = render_markdown(self.finding)
        second = render_markdown(copy.deepcopy(self.finding))
        self.assertEqual(first, second)

    def test_reachability_renders_causal_security_path(self) -> None:
        rendered = render_markdown(self._with_reachability())

        self.assertIn("## Causal security path", rendered)
        self.assertIn("`request-settlement` → `forbidden-settlement`", rendered)
        self.assertIn("`stale-policy-state`", rendered)
        self.assertIn("`approval-policy`", rendered)
        self.assertIn("`authorize-with-stale-policy`", rendered)
        self.assertIn("**Reachability artifact:** `reachability.json`", rendered)

    def test_reachability_binding_mismatch_is_rejected(self) -> None:
        invalid = self._with_reachability()
        invalid["evidence"]["reachability"]["boundInvariantId"] = "other-invariant"
        with self.assertRaisesRegex(ValueError, "must match finding invariant"):
            validate_finding(invalid)

    def test_reachability_non_contiguous_capability_path_is_rejected(self) -> None:
        invalid = self._with_reachability()
        invalid["evidence"]["reachability"]["path"]["transitions"][0]["source"] = "other-source"
        with self.assertRaisesRegex(ValueError, "must form a contiguous path"):
            validate_finding(invalid)

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

    def test_boolean_step_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["minimalFailingPath"][0]["step"] = True
        with self.assertRaisesRegex(ValueError, "step must be an integer"):
            validate_finding(invalid)

    def test_empty_step_evidence_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["minimalFailingPath"][0]["action"] = "   "
        with self.assertRaisesRegex(ValueError, "path step 1.action must be a non-empty string"):
            validate_finding(invalid)

    def test_empty_authorization_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["evidence"]["authorization"] = ""
        with self.assertRaisesRegex(ValueError, "evidence.authorization must be a non-empty string"):
            validate_finding(invalid)

    def test_invalid_explored_candidates_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.finding)
        invalid["evidence"]["exploredCandidates"] = -1
        with self.assertRaisesRegex(ValueError, "must be a non-negative integer"):
            validate_finding(invalid)


if __name__ == "__main__":
    unittest.main()
