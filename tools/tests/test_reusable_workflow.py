from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "credential-boundary-reusable.yml"
)


def test_reusable_boundary_requires_explicit_scanner_revision():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "scanner-ref:" in workflow
    assert "description: Immutable ContractGraph-QA commit" in workflow
    assert "required: true" in workflow
    assert "ref: ${{ inputs.scanner-ref }}" in workflow
    assert "github.workflow_sha" not in workflow
