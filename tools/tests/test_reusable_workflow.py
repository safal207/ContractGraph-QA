import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "credential-boundary-reusable.yml"
)


class ReusableWorkflowContractTests(unittest.TestCase):
    def test_requires_explicit_scanner_revision(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("scanner-ref:", workflow)
        self.assertIn("description: Immutable ContractGraph-QA commit", workflow)
        self.assertIn("required: true", workflow)
        self.assertIn("ref: ${{ inputs.scanner-ref }}", workflow)
        self.assertNotIn("github.workflow_sha", workflow)


if __name__ == "__main__":
    unittest.main()
