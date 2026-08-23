from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.semantic_units_mutation_cli import EXIT_OK, main  # noqa: E402

SCENARIO = ROOT / "scenarios" / "decimal-scaler-semantic-units.json"


class SemanticUnitsMutationCliTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("forge"), "Forge is required for semantic mutation CLI")
    def test_repository_fixture_generates_machine_readable_plan(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="cgqa-semantic-units-") as temp_name:
            output_dir = Path(temp_name) / "out"
            with redirect_stdout(output):
                code = main(
                    [
                        "--config",
                        str(SCENARIO),
                        "--project-root",
                        str(ROOT),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            self.assertEqual(code, EXIT_OK)
            result = json.loads(output.getvalue())
            self.assertEqual(result["generation"]["status"], "pass")
            self.assertEqual(result["generation"]["generatedMutationCount"], 2)
            self.assertIsNone(result["execution"])
            self.assertTrue((output_dir / "semantic-units-generation-result.json").is_file())
            self.assertTrue((output_dir / "generated-mutation-plan.json").is_file())


if __name__ == "__main__":
    unittest.main()
