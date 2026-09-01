from __future__ import annotations

import json
import unittest
from pathlib import Path

from contractgraph_qa.fcrp_v02 import FCRPV02Error, evaluate_fcrp_v02_case


ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = (
    ROOT
    / "benchmarks"
    / "fcrp-v0.2"
    / "FCRP-V02-SELF-LEARNING-001.json"
)
RULE_DIR = ROOT / ".cursor" / "rules"
PROJECTION_NAMES = (
    "scoped-verdict-evidence-routing.mdc",
    "temporal-transition-test-field.mdc",
    "repository-learning-loop.mdc",
)
SPINE_LINK = "[Causal Engagement Spine](causal-engagement-spine.mdc)"


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def validate_projection(text: str) -> None:
    if SPINE_LINK not in text:
        raise ValueError("projection must inherit the causal engagement spine")
    if "alwaysApply: true" not in text:
        raise ValueError("projection must always apply")
    if "spineRef" not in text:
        raise ValueError("projection must bind one canonical spineRef")
    if len(text.splitlines()) >= 50:
        raise ValueError("projection must remain under 50 lines")


class FCRPV02AgentLearningTest(unittest.TestCase):
    def test_self_case_passes_without_granting_future_mutation_authority(self) -> None:
        case = load_case()
        result = evaluate_fcrp_v02_case(case)

        self.assertEqual(result["caseId"], "FCRP-V02-SELF-LEARNING-001")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["firstMeaningfulDivergence"], "N1")
        self.assertEqual(result["causePoint"], "N1")
        self.assertEqual(result["refactorPoint"], "N3")
        self.assertEqual(result["navigationDirection"], "UP")
        self.assertEqual(result["primaryTimeDomain"], "CAUSAL_SEQUENCE")
        self.assertTrue(result["causalAdvanceRequired"])
        self.assertFalse(result["mutationAuthorized"])
        self.assertTrue(result["stopConditionsSatisfied"])
        self.assertEqual(result["decision"], case["expectedProtocolDecision"])

    def test_causal_advance_requires_repository_history_evidence(self) -> None:
        case = load_case()
        case["timeModel"]["causalAdvanceEvidenceRefs"] = []

        with self.assertRaisesRegex(FCRPV02Error, "causalAdvanceEvidenceRefs"):
            evaluate_fcrp_v02_case(case)

    def test_agent_protocol_links_parent_and_projections(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(".cursor/rules/causal-engagement-spine.mdc", agents)

        spine = (RULE_DIR / "causal-engagement-spine.mdc").read_text(
            encoding="utf-8"
        )
        self.assertLess(len(spine.splitlines()), 50)
        self.assertIn("Evidence != Authority", spine)
        self.assertIn("authorizationRef", spine)

        for name in PROJECTION_NAMES:
            self.assertIn(f".cursor/rules/{name}", agents)
            validate_projection((RULE_DIR / name).read_text(encoding="utf-8"))

    def test_negative_control_detects_detached_projection(self) -> None:
        text = (RULE_DIR / PROJECTION_NAMES[0]).read_text(encoding="utf-8")
        detached = text.replace(SPINE_LINK, "Detached Causal Policy")

        with self.assertRaisesRegex(ValueError, "inherit"):
            validate_projection(detached)


if __name__ == "__main__":
    unittest.main()
