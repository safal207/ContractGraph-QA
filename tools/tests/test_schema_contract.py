from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
ROOT = TOOLS_DIR.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from check_schema_contract import check_schema_contract  # noqa: E402
from contractgraph_qa.finding import load_json_object, validate_manifest  # noqa: E402


class SchemaContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_json_object(
            ROOT / "manifests" / "examples" / "adapter-fixture.json", "manifest"
        )

    def test_checked_in_schemas_match_runtime_contract(self) -> None:
        result = check_schema_contract()
        self.assertTrue(result["ok"])

    def test_uppercase_severity_is_rejected_by_runtime(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["invariants"][0]["severity"] = "HIGH"
        with self.assertRaisesRegex(ValueError, "invalid severity"):
            validate_manifest(invalid)

    def test_whitespace_only_text_is_rejected_by_runtime(self) -> None:
        invalid = copy.deepcopy(self.manifest)
        invalid["scope"]["authorization"] = "   "
        with self.assertRaisesRegex(ValueError, "must be a non-empty string"):
            validate_manifest(invalid)


if __name__ == "__main__":
    unittest.main()
