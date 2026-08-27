from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.hydrated_race_composition import (  # noqa: E402
    compose_hydrated_with_protective_ordering,
)
from contractgraph_qa.protective_ordering import (  # noqa: E402
    load_protective_ordering_model,
    protective_ordering_model_from_dict,
    protective_ordering_model_sha256,
)

RACE = ROOT / "scenarios" / "milepact-protective-ordering-race.json"


def _hydrated(status: str = "pass") -> dict[str, object]:
    return {
        "schemaVersion": "hydrated-contract-lattice-result-v0.1",
        "status": status,
        "evidenceFingerprint": {
            "astSha256": "a" * 64,
            "profileSha256": "b" * 64,
            "traceSha256": "c" * 64,
            "bindingsSha256": "d" * 64,
            "assessmentSha256": "e" * 64,
        },
        "claimBoundary": "base boundary",
    }


def _safe_race():
    data = json.loads(RACE.read_text(encoding="utf-8"))
    fixed = copy.deepcopy(data)
    for ordering in fixed["orderings"]:
        ordering["protectiveRightPreserved"] = True
        ordering["economicOutcome"] = "protective_right_preserved"
    return protective_ordering_model_from_dict(fixed)


class HydratedRaceCompositionTest(unittest.TestCase):
    def test_race_fail_overrides_hydrated_pass(self) -> None:
        race = load_protective_ordering_model(RACE)
        result = compose_hydrated_with_protective_ordering(_hydrated("pass"), race)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["protectiveOrderingVerification"]["status"], "fail")
        self.assertEqual(result["protectiveOrderingVerification"]["invariantId"], "CGQ-RACE-001")

    def test_race_pass_preserves_hydrated_pass(self) -> None:
        result = compose_hydrated_with_protective_ordering(_hydrated("pass"), _safe_race())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["protectiveOrderingVerification"]["status"], "pass")

    def test_race_inconclusive_blocks_full_pass(self) -> None:
        data = json.loads(RACE.read_text(encoding="utf-8"))
        data["protectiveActionMustRemainEffectiveAcrossOrdering"] = False
        race = protective_ordering_model_from_dict(data)
        result = compose_hydrated_with_protective_ordering(_hydrated("pass"), race)
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["protectiveOrderingVerification"]["status"], "inconclusive")

    def test_existing_hydrated_fail_remains_fail_even_if_race_passes(self) -> None:
        result = compose_hydrated_with_protective_ordering(_hydrated("fail"), _safe_race())
        self.assertEqual(result["status"], "fail")

    def test_race_model_is_bound_into_assessment_fingerprint(self) -> None:
        race = load_protective_ordering_model(RACE)
        before = _hydrated("pass")
        old_hash = before["evidenceFingerprint"]["assessmentSha256"]
        result = compose_hydrated_with_protective_ordering(before, race)
        fingerprint = result["evidenceFingerprint"]
        self.assertEqual(fingerprint["raceModelSha256"], protective_ordering_model_sha256(race))
        self.assertNotEqual(fingerprint["assessmentSha256"], old_hash)
        self.assertIn("CGQ-RACE-001", result["claimBoundary"])


if __name__ == "__main__":
    unittest.main()
