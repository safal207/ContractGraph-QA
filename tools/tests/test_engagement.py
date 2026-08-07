from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.engagement import (
    EngagementError,
    build_engagement,
    verify_engagement_bundle,
    write_engagement_bundle,
)
from contractgraph_qa.finding import load_json_object

ROOT = Path(__file__).resolve().parents[2]


class EngagementEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "manifests" / "examples" / "engagement-fixture.json"
        self.result_path = ROOT / "results" / "examples" / "CGQA-E-001.engagement-result.json"
        self.manifest = load_json_object(self.manifest_path, "manifest")
        self.result = load_json_object(self.result_path, "engagementResult")

    def test_build_engagement_preserves_all_invariant_outcomes(self) -> None:
        engagement, findings = build_engagement(self.manifest, self.result)
        self.assertEqual(engagement["coverage"]["declaredInvariants"], 3)
        self.assertEqual(engagement["coverage"]["checkedInvariants"], 3)
        self.assertEqual(engagement["coverage"]["violated"], 1)
        self.assertEqual(engagement["coverage"]["notFoundWithinBound"], 1)
        self.assertEqual(engagement["coverage"]["inconclusive"], 1)
        self.assertEqual([finding["id"] for finding in findings], ["CGQA-E-001-F01"])
        self.assertEqual(len(findings[0]["minimalFailingPath"]), 3)

    def test_omitted_declared_invariant_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["checks"].pop()
        with self.assertRaisesRegex(EngagementError, "omitted declared invariants"):
            build_engagement(self.manifest, invalid)

    def test_unknown_invariant_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        unknown = copy.deepcopy(invalid["checks"][2])
        unknown["invariantId"] = "unknown-invariant"
        invalid["checks"].append(unknown)
        with self.assertRaisesRegex(EngagementError, "contains unknown invariants"):
            build_engagement(self.manifest, invalid)

    def test_duplicate_invariant_check_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["checks"][2]["invariantId"] = invalid["checks"][1]["invariantId"]
        with self.assertRaisesRegex(EngagementError, "duplicate engagement invariant check"):
            build_engagement(self.manifest, invalid)

    def test_clean_status_cannot_carry_a_failing_path(self) -> None:
        invalid = copy.deepcopy(self.result)
        violated = invalid["checks"][0]
        violated["status"] = "not_found_within_bound"
        violated.pop("findingId")
        with self.assertRaisesRegex(EngagementError, "must not declare a failing path"):
            build_engagement(self.manifest, invalid)

    def test_inconclusive_status_cannot_carry_finding_id(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["checks"][2]["findingId"] = "CGQA-BAD"
        with self.assertRaisesRegex(EngagementError, "must not declare findingId"):
            build_engagement(self.manifest, invalid)

    def test_unsafe_finding_id_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["checks"][0]["findingId"] = "../escape"
        with self.assertRaisesRegex(EngagementError, "unsafe artifact characters"):
            build_engagement(self.manifest, invalid)

    def test_manifest_provenance_mismatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.result)
        invalid["manifestSha256"] = "0" * 64
        with self.assertRaisesRegex(EngagementError, "manifestSha256 does not match"):
            build_engagement(self.manifest, invalid)

    def test_bundle_round_trip_is_semantically_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "out"
            bundle = root / "engagement.zip"
            generated = write_engagement_bundle(
                self.manifest_path,
                self.result_path,
                output,
                bundle,
            )
            self.assertTrue(generated["ok"])
            self.assertEqual(generated["findingIds"], ["CGQA-E-001-F01"])
            verified = verify_engagement_bundle(bundle)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["coverage"]["inconclusive"], 1)
            self.assertTrue((output / "engagement.json").is_file())
            self.assertTrue((output / "findings" / "CGQA-E-001-F01.finding.json").is_file())

    def test_tampered_engagement_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "engagement.zip"
            write_engagement_bundle(
                self.manifest_path,
                self.result_path,
                root / "out",
                bundle,
            )
            with zipfile.ZipFile(bundle, "r") as archive:
                names = archive.namelist()
                payloads = {name: archive.read(name) for name in names}
            engagement = json.loads(payloads["engagement.json"].decode("utf-8"))
            engagement["coverage"]["violated"] = 0
            payloads["engagement.json"] = (
                json.dumps(engagement, indent=2, ensure_ascii=False) + "\n"
            ).encode("utf-8")
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_STORED) as archive:
                for name in names:
                    archive.writestr(name, payloads[name])
            with self.assertRaisesRegex(EngagementError, "semantic chain"):
                verify_engagement_bundle(tampered)


if __name__ == "__main__":
    unittest.main()
