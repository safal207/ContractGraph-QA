from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.ancestral_validity import run_ancestral_validity  # noqa: E402
from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main as cli_main  # noqa: E402
from contractgraph_qa.orientation_center import evaluate_orientation_center  # noqa: E402
from contractgraph_qa.transition_geometry import run_transition_geometry_model  # noqa: E402


class TransitionGeometryTest(unittest.TestCase):
    def test_settle_cancel_negative_control_detects_effect_torsion(self) -> None:
        model = json.loads((ROOT / "scenarios" / "geometry-settle-cancel.json").read_text())
        result = run_transition_geometry_model(model)
        self.assertEqual(result["status"], "hold")
        self.assertEqual(result["pair"]["classification"], "TORSION_DETECTED")
        self.assertTrue(result["pair"]["effectDelta"])
        self.assertEqual(result["loop"]["classification"], "HOLONOMY")

    def test_equal_endpoints_are_closed(self) -> None:
        endpoint = {
            "state": {"active": False},
            "effects": {"payout": 100},
            "history": {"generation": 2},
        }
        model = {
            "schema": "cgqa/transition-geometry/v0.1",
            "subject": {"commit": "abc"},
            "operators": {"a": "settle", "b": "cancel"},
            "origin": copy.deepcopy(endpoint),
            "aThenB": copy.deepcopy(endpoint),
            "bThenA": copy.deepcopy(endpoint),
        }
        result = run_transition_geometry_model(model)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["pair"]["classification"], "CLOSED")

    def test_same_semantics_different_history_is_not_torsion(self) -> None:
        model = {
            "schema": "cgqa/transition-geometry/v0.1",
            "subject": {"commit": "abc"},
            "operators": {"a": "pause", "b": "resume"},
            "origin": {"state": {}, "effects": {}, "history": {"generation": 1}},
            "aThenB": {"state": {"active": True}, "effects": {}, "history": {"path": ["a", "b"]}},
            "bThenA": {"state": {"active": True}, "effects": {}, "history": {"path": ["b", "a"]}},
        }
        result = run_transition_geometry_model(model)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["pair"]["classification"], "HISTORY_DIVERGENT")

    def test_loop_effect_drift_detects_curvature(self) -> None:
        model = {
            "schema": "cgqa/transition-geometry/v0.1",
            "subject": {"commit": "abc"},
            "operators": {"a": "fund", "b": "refund"},
            "origin": {"state": {"balance": 0}, "effects": {"fees": 0}, "history": {}},
            "aThenB": {"state": {}, "effects": {}, "history": {}},
            "bThenA": {"state": {}, "effects": {}, "history": {}},
            "loop": {
                "operators": ["fund", "refund"],
                "returned": {"state": {"balance": 0}, "effects": {"fees": 1}, "history": {}},
            },
        }
        result = run_transition_geometry_model(model)
        self.assertEqual(result["loop"]["classification"], "CURVATURE_DETECTED")
        self.assertEqual(result["status"], "hold")


class AncestralValidityTest(unittest.TestCase):
    def _base(self) -> dict[str, object]:
        return {
            "schema": "cgqa/ancestral-validity/v0.1",
            "subject": {"commit": "abc"},
            "targetEventId": "target",
            "events": [
                {
                    "id": "root",
                    "kind": "ROOT",
                    "actor": "user",
                    "occurredAt": 1,
                    "scope": "wf",
                    "localValid": True,
                },
                {
                    "id": "target",
                    "kind": "ACTION",
                    "actor": "agent",
                    "occurredAt": 3,
                    "scope": "wf",
                    "parentId": "root",
                    "localValid": True,
                },
            ],
        }

    def _codes(self, model: dict[str, object]) -> set[str]:
        return {row["code"] for row in run_ancestral_validity(model)["findings"]}

    def test_rejected_branch_reentry_fixture_fails(self) -> None:
        model = json.loads(
            (ROOT / "scenarios" / "ancestry-rejected-branch-reentry.json").read_text()
        )
        result = run_ancestral_validity(model)
        self.assertEqual(result["localValidity"], "valid")
        self.assertEqual(result["effectiveValidity"], "invalid")
        self.assertIn("REJECTED_BRANCH_REUSE", {row["code"] for row in result["findings"]})

    def test_stale_parent_negative_control(self) -> None:
        model = self._base()
        model["events"].insert(
            1,
            {
                "id": "approval",
                "kind": "APPROVAL",
                "actor": "reviewer",
                "occurredAt": 2,
                "expiresAt": 2,
                "scope": "wf",
                "parentId": "root",
                "localValid": True,
            },
        )
        model["events"][-1]["parentId"] = "approval"
        self.assertIn("STALE_PARENT", self._codes(model))

    def test_missing_authority_handoff_negative_control(self) -> None:
        model = self._base()
        model["events"][-1]["requiresHandoff"] = True
        self.assertIn("MISSING_AUTHORITY_HANDOFF", self._codes(model))

    def test_invalid_root_inheritance_negative_control(self) -> None:
        model = self._base()
        model["events"][0]["localValid"] = False
        self.assertIn("INVALID_ROOT_INHERITANCE", self._codes(model))

    def test_memory_without_evidence_origin_negative_control(self) -> None:
        model = self._base()
        model["events"].insert(
            1,
            {
                "id": "memory",
                "kind": "MEMORY",
                "actor": "agent",
                "occurredAt": 2,
                "scope": "wf",
                "parentId": "root",
                "localValid": True,
            },
        )
        model["events"][-1]["parentId"] = "memory"
        self.assertIn("MEMORY_WITHOUT_EVIDENCE_ORIGIN", self._codes(model))

    def test_remediation_without_fault_link_negative_control(self) -> None:
        model = self._base()
        model["events"][-1]["kind"] = "REMEDIATION"
        self.assertIn("REMEDIATION_WITHOUT_FAULT_LINK", self._codes(model))

    def test_clean_trace_passes(self) -> None:
        result = run_ancestral_validity(self._base())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["findings"], [])


class OrientationCenterTest(unittest.TestCase):
    def _balanced(self) -> dict[str, object]:
        return {
            "schema": "cgqa/orientation-center/v0.1",
            "subject": {"commit": "abc"},
            "state": {"status": "active"},
            "ancestry": {"status": "VALID_WITHIN_TRACE"},
            "authorityNow": {"status": "VALID"},
            "supportingEvidence": [{"id": "native-test", "status": "PASS"}],
            "counterevidence": [],
            "verificationDebt": [],
            "independentWitnesses": [],
            "watchpoints": [],
            "requirements": {
                "requireSupportingEvidence": True,
                "requireIndependentWitness": False,
                "requireAncestry": True,
                "requireAuthority": True,
            },
        }

    def test_unresolved_verification_debt_is_indeterminate(self) -> None:
        bundle = json.loads(
            (ROOT / "scenarios" / "orientation-unresolved-debt.json").read_text()
        )
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "INDETERMINATE")
        self.assertIn("VERIFICATION_DEBT_UNRESOLVED", {row["code"] for row in result["unresolved"]})

    def test_balanced_is_readiness_not_security_claim(self) -> None:
        result = evaluate_orientation_center(self._balanced())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["readiness"], "BALANCED")
        self.assertIn("not a truth", result["claimBoundary"])

    def test_confirmed_counterevidence_is_unstable(self) -> None:
        bundle = self._balanced()
        bundle["counterevidence"] = [{"id": "counter-1", "status": "CONFIRMED"}]
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "UNSTABLE")

    def test_required_witness_missing_is_indeterminate(self) -> None:
        bundle = self._balanced()
        bundle["requirements"]["requireIndependentWitness"] = True
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "INDETERMINATE")


class DeepCapabilityCliTest(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, dict[str, object]]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(argv)
        return code, json.loads(stdout.getvalue())

    def test_geometry_cli_surfaces_hold(self) -> None:
        code, payload = self._run(
            ["geometry", "--model", str(ROOT / "scenarios" / "geometry-settle-cancel.json")]
        )
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["pair"]["classification"], "TORSION_DETECTED")

    def test_ancestry_cli_surfaces_effective_invalidity(self) -> None:
        code, payload = self._run(
            [
                "ancestry",
                "--trace",
                str(ROOT / "scenarios" / "ancestry-rejected-branch-reentry.json"),
            ]
        )
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["effectiveValidity"], "invalid")

    def test_orient_cli_surfaces_unresolved_debt(self) -> None:
        code, payload = self._run(
            ["orient", "--bundle", str(ROOT / "scenarios" / "orientation-unresolved-debt.json")]
        )
        self.assertEqual(code, EXIT_VALIDATION)
        self.assertEqual(payload["readiness"], "INDETERMINATE")

    def test_clean_geometry_cli_returns_ok(self) -> None:
        temp = ROOT / "results" / "generated" / "geometry-clean-test.json"
        temp.parent.mkdir(parents=True, exist_ok=True)
        endpoint = {"state": {}, "effects": {}, "history": {}}
        temp.write_text(
            json.dumps(
                {
                    "schema": "cgqa/transition-geometry/v0.1",
                    "subject": {"commit": "abc"},
                    "operators": {"a": "a", "b": "b"},
                    "origin": endpoint,
                    "aThenB": endpoint,
                    "bThenA": endpoint,
                }
            ),
            encoding="utf-8",
        )
        try:
            code, payload = self._run(["geometry", "--model", str(temp)])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(payload["status"], "pass")
        finally:
            temp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
