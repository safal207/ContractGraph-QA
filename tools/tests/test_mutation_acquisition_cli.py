from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.mutation_acquisition_cli import EXIT_OK, main  # noqa: E402

PLAN = ROOT / "scenarios" / "escrow-foundry-mutation-plan.json"


class MutationAcquisitionCliTest(unittest.TestCase):
    def test_cli_wires_plan_project_and_output_to_runner(self) -> None:
        fake_result = {
            "status": "pass",
            "acquisitionId": "escrow-foundry-mutation-v0.1",
            "specAssurance": {"status": "pass"},
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="cgqa-mutation-cli-") as temp_name:
            evidence = Path(temp_name) / "evidence"
            with (
                patch("contractgraph_qa.mutation_acquisition_cli.shutil.which", return_value="/usr/bin/forge"),
                patch(
                    "contractgraph_qa.mutation_acquisition_cli.run_mutation_acquisition",
                    return_value=fake_result,
                ) as runner,
                redirect_stdout(output),
            ):
                code = main(
                    [
                        "--plan",
                        str(PLAN),
                        "--project-root",
                        str(ROOT),
                        "--output-dir",
                        str(evidence),
                    ]
                )
        self.assertEqual(code, EXIT_OK)
        result = json.loads(output.getvalue())
        self.assertEqual(result["acquisitionId"], "escrow-foundry-mutation-v0.1")
        runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()
