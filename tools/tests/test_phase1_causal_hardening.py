from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.ancestral_validity import (  # noqa: E402
    AncestralValidityError,
    run_ancestral_validity,
)
from contractgraph_qa.orientation_center import evaluate_orientation_center  # noqa: E402
from contractgraph_qa.transition_geometry import (  # noqa: E402
    TransitionGeometryError,
    run_transition_geometry_model,
)


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _endpoint(subject_hash: str, *, history: object | None = None) -> dict[str, object]:
    return {
        "subjectHash": subject_hash,
        "state": {"active": False, "balance": 0},
        "effects": {"payout": 0},
        "history": {} if history is None else history,
    }


class TransitionGeometryHardeningTest(unittest.TestCase):
    def test_foreign_endpoint_subject_fails_closed(self) -> None:
        subject = {"repo": "example/repo", "commit": "abc"}
        subject_hash = _sha(subject)
        endpoint = _endpoint(subject_hash)
        foreign = copy.deepcopy(endpoint)
        foreign["subjectHash"] = "f" * 64
        model = {
            "schema": "cgqa/transition-geometry/v0.1",
            "subject": subject,
            "operators": {"a": "settle", "b": "cancel"},
            "origin": endpoint,
            "aThenB": endpoint,
            "bThenA": foreign,
        }
        with self.assertRaises(TransitionGeometryError):
            run_transition_geometry_model(model)

    def test_flat_loop_is_explicitly_covered(self) -> None:
        subject = {"repo": "example/repo", "commit": "abc"}
        subject_hash = _sha(subject)
        endpoint = _endpoint(subject_hash)
        model = {
            "schema": "cgqa/transition-geometry/v0.1",
            "subject": subject,
            "operators": {"a": "pause", "b": "resume"},
            "origin": copy.deepcopy(endpoint),
            "aThenB": copy.deepcopy(endpoint),
            "bThenA": copy.deepcopy(endpoint),
            "loop": {"operators": ["pause", "resume"], "returned": copy.deepcopy(endpoint)},
        }
        result = run_transition_geometry_model(model)
        self.assertEqual(result["pair"]["classification"], "CLOSED")
        self.assertEqual(result["loop"]["classification"], "FLAT_LOOP")
        self.assertEqual(result["subjectBinding"], "EXPLICIT_ENDPOINT_BINDING")
        self.assertFalse(result["securityVerdictAuthorized"])


class AncestralValidityHardeningTest(unittest.TestCase):
    def test_rejected_reentry_exposes_first_invalidity_and_descendants(self) -> None:
        trace = json.loads(
            (ROOT / "scenarios" / "ancestry-rejected-branch-reentry.json").read_text()
        )
        result = run_ancestral_validity(trace)
        self.assertEqual(result["effectiveValidity"], "invalid")
        self.assertIsNotNone(result["firstInvalidity"])
        self.assertEqual(result["firstInvalidity"]["code"], "REJECTED_BRANCH_REUSE")
        self.assertIn(result["targetEventId"], result["affectedDescendants"])
        self.assertFalse(result["securityVerdictAuthorized"])

    def test_foreign_scope_ancestor_is_separate_failure(self) -> None:
        trace = {
            "schema": "cgqa/ancestral-validity/v0.1",
            "subject": {"commit": "abc"},
            "targetEventId": "target",
            "events": [
                {
                    "id": "root",
                    "kind": "ROOT",
                    "actor": "user",
                    "occurredAt": 1,
                    "scope": "other-workflow",
                },
                {
                    "id": "target",
                    "kind": "ACTION",
                    "actor": "agent",
                    "occurredAt": 2,
                    "scope": "current-workflow",
                    "parentId": "root",
                },
            ],
        }
        result = run_ancestral_validity(trace)
        codes = {row["code"] for row in result["findings"]}
        self.assertIn("FOREIGN_SCOPE_ANCESTOR", codes)

    def test_foreign_event_subject_fails_closed(self) -> None:
        subject = {"commit": "abc"}
        trace = {
            "schema": "cgqa/ancestral-validity/v0.1",
            "subject": subject,
            "targetEventId": "target",
            "events": [
                {
                    "id": "target",
                    "kind": "ACTION",
                    "actor": "agent",
                    "occurredAt": 1,
                    "subjectHash": "f" * 64,
                }
            ],
        }
        with self.assertRaises(AncestralValidityError):
            run_ancestral_validity(trace)


class OrientationCrossCapabilityHardeningTest(unittest.TestCase):
    def _subject(self) -> dict[str, str]:
        return {"repo": "example/repo", "commit": "abc"}

    def _orientation(
        self,
        *,
        ancestry: dict[str, object],
        geometry: list[dict[str, object]],
        supporting_subject_hash: str,
    ) -> dict[str, object]:
        return {
            "schema": "cgqa/orientation-center/v0.1",
            "subject": self._subject(),
            "state": {"status": "active"},
            "ancestry": ancestry,
            "geometryResults": geometry,
            "authorityNow": {"status": "VALID"},
            "supportingEvidence": [
                {
                    "id": "native-regression",
                    "status": "PASS",
                    "subjectHash": supporting_subject_hash,
                }
            ],
            "counterevidence": [],
            "verificationDebt": [],
            "independentWitnesses": [],
            "watchpoints": [],
            "requirements": {
                "requireSupportingEvidence": True,
                "requireIndependentWitness": False,
                "requireAncestry": True,
                "requireAuthority": True,
                "requireGeometry": True,
                "requireChildSubjectBinding": True,
            },
        }

    def test_geometry_torsion_keeps_orientation_indeterminate(self) -> None:
        subject_hash = _sha(self._subject())
        bundle = self._orientation(
            ancestry={
                "status": "PASS",
                "effectiveValidity": "valid_within_trace",
                "subjectHash": subject_hash,
            },
            geometry=[
                {
                    "id": "geometry-1",
                    "status": "hold",
                    "subjectHash": subject_hash,
                    "pair": {"classification": "TORSION_DETECTED"},
                    "loop": None,
                }
            ],
            supporting_subject_hash=subject_hash,
        )
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "INDETERMINATE")
        self.assertIn(
            "GEOMETRY_PATH_DEPENDENCE",
            {row["code"] for row in result["unresolved"]},
        )

    def test_foreign_geometry_receipt_is_unstable(self) -> None:
        subject_hash = _sha(self._subject())
        bundle = self._orientation(
            ancestry={
                "status": "PASS",
                "effectiveValidity": "valid_within_trace",
                "subjectHash": subject_hash,
            },
            geometry=[
                {
                    "id": "geometry-foreign",
                    "status": "pass",
                    "subjectHash": "f" * 64,
                    "pair": {"classification": "CLOSED"},
                    "loop": None,
                }
            ],
            supporting_subject_hash=subject_hash,
        )
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "UNSTABLE")
        self.assertIn(
            "GEOMETRY_SUBJECT_MISMATCH",
            {row["code"] for row in result["hardFindings"]},
        )

    def test_foreign_ancestry_receipt_is_unstable(self) -> None:
        subject_hash = _sha(self._subject())
        bundle = self._orientation(
            ancestry={
                "status": "PASS",
                "effectiveValidity": "valid_within_trace",
                "subjectHash": "f" * 64,
            },
            geometry=[
                {
                    "id": "geometry-1",
                    "status": "pass",
                    "subjectHash": subject_hash,
                    "pair": {"classification": "CLOSED"},
                    "loop": None,
                }
            ],
            supporting_subject_hash=subject_hash,
        )
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "UNSTABLE")
        self.assertIn(
            "ANCESTRY_SUBJECT_MISMATCH",
            {row["code"] for row in result["hardFindings"]},
        )

    def test_real_geometry_and_ancestry_receipts_can_balance(self) -> None:
        subject = self._subject()
        subject_hash = _sha(subject)
        endpoint = _endpoint(subject_hash)
        geometry_result = run_transition_geometry_model(
            {
                "schema": "cgqa/transition-geometry/v0.1",
                "subject": subject,
                "operators": {"a": "pause", "b": "resume"},
                "origin": copy.deepcopy(endpoint),
                "aThenB": copy.deepcopy(endpoint),
                "bThenA": copy.deepcopy(endpoint),
            }
        )
        ancestry_result = run_ancestral_validity(
            {
                "schema": "cgqa/ancestral-validity/v0.1",
                "subject": subject,
                "targetEventId": "target",
                "events": [
                    {
                        "id": "root",
                        "kind": "ROOT",
                        "actor": "user",
                        "occurredAt": 1,
                        "scope": "wf",
                        "subjectHash": subject_hash,
                    },
                    {
                        "id": "target",
                        "kind": "ACTION",
                        "actor": "agent",
                        "occurredAt": 2,
                        "scope": "wf",
                        "parentId": "root",
                        "subjectHash": subject_hash,
                    },
                ],
            }
        )
        geometry_receipt = {
            "id": "geometry-live",
            "status": geometry_result["status"],
            "subjectHash": geometry_result["subjectHash"],
            "pair": geometry_result["pair"],
            "loop": geometry_result["loop"],
        }
        ancestry_receipt = {
            "status": ancestry_result["status"],
            "effectiveValidity": ancestry_result["effectiveValidity"],
            "subjectHash": ancestry_result["subjectHash"],
        }
        bundle = self._orientation(
            ancestry=ancestry_receipt,
            geometry=[geometry_receipt],
            supporting_subject_hash=subject_hash,
        )
        result = evaluate_orientation_center(bundle)
        self.assertEqual(result["readiness"], "BALANCED")
        self.assertFalse(result["securityVerdictAuthorized"])
        self.assertEqual(result["contributingCapabilities"]["geometry"], ["CLOSED"])


if __name__ == "__main__":
    unittest.main()
