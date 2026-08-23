from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.fault_mutation_generator_cli import EXIT_OK, main  # noqa: E402

SCENARIO = ROOT / "scenarios" / "escrow-auto-fault-generator.json"


class FaultMutationGeneratorCliTest(unittest.TestCase):
    def test_repository_fixture_generates_machine_readable_plan(self) -> None:
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="cgqa-fault-generator-") as temp_name:
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
            generation = result["generation"]
            self.assertEqual(generation["status"], "pass")
            self.assertEqual(generation["generatedMutationCount"], 14)
            self.assertTrue((output_dir / "fault-generation-result.json").is_file())
            self.assertTrue((output_dir / "generated-mutation-plan.json").is_file())


if __name__ == "__main__":
    unittest.main()
