from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.change_gate import run_change_gate


BASE_MODEL = {
    "assumptions": [
        {
            "id": "terminal-transition-blocked",
            "description": "Terminal transition remains blocked.",
        }
    ],
    "capabilities": [
        {
            "id": "progress-state-machine",
            "description": "Advance reviewed states.",
            "forbidden": False,
        },
        {
            "id": "terminal-state-reachable",
            "description": "Reach forbidden terminal state.",
            "forbidden": True,
        },
    ],
    "transitions": [
        {
            "id": "cross-terminal-bound",
            "source": "progress-state-machine",
            "target": "terminal-state-reachable",
            "requiresViolations": ["terminal-transition-blocked"],
            "invariantId": "adapter-terminal-state",
            "boundary": "terminal-state-boundary",
            "impact": "terminal invariant becomes reachable",
        }
    ],
    "initialCapabilities": ["progress-state-machine"],
    "targetCapabilities": ["terminal-state-reachable"],
    "violatedAssumptions": [],
    "maxDepth": 2,
}


def encoded(model: dict[str, object]) -> bytes:
    return json.dumps(model, sort_keys=True).encode("utf-8")


class FakeRepository:
    def __init__(self, base_files: dict[str, bytes], head_files: dict[str, bytes]) -> None:
        self.base_files = base_files
        self.head_files = head_files

    def resolve_commit(self, ref: str) -> str:
        if ref == "HEAD":
            return "b" * 40
        return "a" * 40

    def read_at_commit(self, commit_sha: str, path: str) -> bytes:
        if path not in self.base_files:
            raise FileNotFoundError(path)
        return self.base_files[path]

    def read_worktree(self, path: str) -> bytes:
        if path not in self.head_files:
            raise FileNotFoundError(path)
        return self.head_files[path]


class ChangeGateTests(unittest.TestCase):
    def run_gate(
        self,
        base_model: dict[str, object] | None,
        head_model: dict[str, object] | None,
        *,
        base_config: str | None = None,
        head_config: str | None = None,
    ) -> dict[str, object]:
        default_config = (
            'schemaVersion = 1\n\n'
            '[[models]]\n'
            'id = "adapter"\n'
            'path = "scenarios/model.json"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "causal-security-gate.toml"
            config.write_text(head_config or default_config, encoding="utf-8")
            base_files: dict[str, bytes] = {}
            if base_config is not None:
                base_files["causal-security-gate.toml"] = base_config.encode("utf-8")
            if base_model is not None:
                base_files["scenarios/model.json"] = encoded(base_model)
            head_files = {}
            if head_model is not None:
                head_files["scenarios/model.json"] = encoded(head_model)
            return run_change_gate(
                config,
                "origin/main",
                repo_root=root,
                repository=FakeRepository(base_files, head_files),
            )

    def test_identical_model_passes_deterministically(self) -> None:
        first = self.run_gate(BASE_MODEL, BASE_MODEL)
        second = self.run_gate(BASE_MODEL, BASE_MODEL)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "pass")
        self.assertEqual(first["blockingModels"], [])
        self.assertFalse(first["baselineConfigPresent"])

    def test_new_forbidden_reachability_blocks(self) -> None:
        head = dict(BASE_MODEL)
        head["violatedAssumptions"] = ["terminal-transition-blocked"]
        result = self.run_gate(BASE_MODEL, head)
        self.assertEqual(result["status"], "blocked")
        model = result["models"][0]
        self.assertEqual(model["gateReasons"], ["new_forbidden_reachability"])
        self.assertEqual(
            model["delta"]["introducedForbiddenPaths"]["terminal-state-reachable"]["targetCapability"],
            "terminal-state-reachable",
        )

    def test_real_risk_reduction_does_not_block(self) -> None:
        base = dict(BASE_MODEL)
        base["violatedAssumptions"] = ["terminal-transition-blocked"]
        result = self.run_gate(base, BASE_MODEL)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["models"][0]["delta"]["status"], "risk_reduced")

    def test_deleted_head_model_fails_closed(self) -> None:
        result = self.run_gate(BASE_MODEL, None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["models"][0]["gateReasons"], ["head_model_missing"])

    def test_missing_base_model_fails_closed(self) -> None:
        result = self.run_gate(None, BASE_MODEL)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["models"][0]["gateReasons"], ["base_model_missing"])

    def test_forbidden_reclassification_fails_closed(self) -> None:
        head = json.loads(json.dumps(BASE_MODEL))
        for capability in head["capabilities"]:
            if capability["id"] == "terminal-state-reachable":
                capability["forbidden"] = False
        result = self.run_gate(BASE_MODEL, head)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["models"][0]["gateReasons"], ["forbidden_definition_changed"])

    def test_removing_configured_model_fails_closed(self) -> None:
        base_config = (
            'schemaVersion = 1\n\n'
            '[[models]]\n'
            'id = "adapter"\n'
            'path = "scenarios/model.json"\n'
        )
        head_config = (
            'schemaVersion = 1\n\n'
            '[[models]]\n'
            'id = "other"\n'
            'path = "scenarios/model.json"\n'
        )
        result = self.run_gate(
            BASE_MODEL,
            BASE_MODEL,
            base_config=base_config,
            head_config=head_config,
        )
        self.assertEqual(result["status"], "blocked")
        by_id = {item["id"]: item for item in result["models"]}
        self.assertEqual(by_id["adapter"]["gateReasons"], ["configured_model_removed"])


if __name__ == "__main__":
    unittest.main()
