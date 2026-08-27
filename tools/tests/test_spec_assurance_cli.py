from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.spec_assurance_cli import EXIT_OK, main  # noqa: E402

SCENARIO = ROOT / "scenarios" / "spec-assurance-race-property.json"


class SpecAssuranceCliTest(unittest.TestCase):
    def test_repository_fixture_passes_and_emits_machine_readable_json(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["--model", str(SCENARIO)])
        self.assertEqual(code, EXIT_OK)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["assuranceInvariantId"], "CGQ-SPEC-001")
        self.assertEqual(result["propertyInvariantId"], "CGQ-RACE-001")


if __name__ == "__main__":
    unittest.main()
