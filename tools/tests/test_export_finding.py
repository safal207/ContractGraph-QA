from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from export_finding import export_finding, load_json_object  # noqa: E402


class ManifestFindingExporterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "manifests" / "examples" / "adapter-fixture.json"
        self.result_path = ROOT / "results" / "examples" / "CGQA-005.result.json"
        self.expected_path = ROOT / "reports" / "examples" / "CGQA-005.finding.json"
        self.manifest = load_json_object(self.manifest_path, "manifest")
        self.result = load_json_object(self.result_path, "result")

    def test_sample_matches_checked_in_finding(self) -> None:
        exported = export_finding(self.manifest, self.result)
        expected = load_json_object(self.expected_path, "finding")
        self.assertEqual(exported, expected)

    def test_export_is_deterministic(self) -> None:
        first = export_finding(self.manifest, self.result)
        second = export_finding(copy.deepcopy(self.manifest), copy.deepcopy(self.result))
        self.assertEqual(first, second)

    def test_unknown_action_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["path"][0]["actionId"] = "missing-action"
        with self.assertRaisesRegex(ValueError, "unknown action id"):
            export_finding(self.manifest, invalid)

    def test_unknown_invariant_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["invariantId"] = "missing-invariant"
        with self.assertRaisesRegex(ValueError, "unknown invariant id"):
            export_finding(self.manifest, invalid)

    def test_duplicate_action_id_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["actions"].append(copy.deepcopy(invalid["actions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate action id"):
            export_finding(invalid, self.result)

    def test_empty_authorization_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["scope"]["authorization"] = ""
        with self.assertRaisesRegex(ValueError, "manifest.scope.authorization"):
            export_finding(invalid, self.result)

    def test_missing_parameter_for_template_is_rejected(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["actions"][1]["display"] = "advance({parameter})"
        with self.assertRaisesRegex(ValueError, "parameter required"):
            export_finding(manifest, self.result)

    def test_unexpected_parameter_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["path"][0]["parameter"] = 1
        with self.assertRaisesRegex(ValueError, "action has no placeholder"):
            export_finding(self.manifest, invalid)

    def test_boolean_explored_candidates_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["exploredCandidates"] = True
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            export_finding(self.manifest, invalid)


if __name__ == "__main__":
    unittest.main()
