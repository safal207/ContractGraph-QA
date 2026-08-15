from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.authority_reflection_boundary import BoundaryError, verify_boundary


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "fixtures" / "p1-3"
FIXTURE_MANIFEST = FIXTURE_ROOT / "authority-reflection-boundary.v0.1.json"
FIXTURE_BUNDLE = FIXTURE_ROOT / "bundle"
CGQA_HEAD = "6e51cbb176f6d891b758e3026744d1d4c4c5727a"
PROOFPATH_HEAD = "4a05ee31d7497979c2505dd55bfef08823302e24"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class AuthorityReflectionBoundaryTest(unittest.TestCase):
    def _copy_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        manifest = root / "manifest.json"
        bundle = root / "bundle"
        shutil.copy2(FIXTURE_MANIFEST, manifest)
        shutil.copytree(FIXTURE_BUNDLE, bundle)
        return temp, manifest, bundle

    def _verify(self, manifest: Path, bundle: Path) -> dict:
        return verify_boundary(
            manifest,
            bundle,
            checked_subject=CGQA_HEAD,
            expected_proofpath_subject=PROOFPATH_HEAD,
        )

    def test_boundary_passes_with_zero_execution(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            result = self._verify(manifest, bundle)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["subject_count"], 5)
        self.assertEqual(result["artifact_count"], 3)
        self.assertEqual(result["total_bytes"], 1254)
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(result["blocked_cases"], 3)
        self.assertEqual(result["hold_cases"], 1)
        self.assertEqual(result["executed_cases"], 0)
        self.assertTrue(result["evidence_cannot_authorize"])
        self.assertTrue(result["reflection_cannot_authorize"])
        self.assertTrue(result["explicit_authority_required"])
        self.assertFalse(result["side_effects_executed"])

    def test_replay_receipt_is_deterministic(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            first = self._verify(manifest, bundle)
            second = self._verify(manifest, bundle)
        self.assertEqual(first, second)

    def test_tampered_evidence_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "evidence-pass.json").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "(byte-size|SHA-256) mismatch"):
                self._verify(manifest, bundle)

    def test_unlisted_artifact_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "unlisted.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "unlisted=unlisted.json"):
                self._verify(manifest, bundle)

    def test_missing_artifact_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "authority-hold.json").unlink()
            with self.assertRaisesRegex(BoundaryError, "missing=authority-hold.json"):
                self._verify(manifest, bundle)

    def test_duplicate_path_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][1]["path"] = value["artifacts"][0]["path"]
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "duplicate artifact path"):
                self._verify(manifest, bundle)

    def test_duplicate_digest_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][1]["sha256"] = value["artifacts"][0]["sha256"]
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "duplicate artifact SHA-256"):
                self._verify(manifest, bundle)

    def test_path_traversal_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][0]["path"] = "../escape.json"
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "traversal"):
                self._verify(manifest, bundle)

    def test_source_revision_drift_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][0]["source_revision"] = CGQA_HEAD
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "source_revision does not match"):
                self._verify(manifest, bundle)

    def test_evidence_authority_flag_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(bundle / "evidence-pass.json")
            value["execution_authorized"] = True
            (bundle / "evidence-pass.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "(byte-size|SHA-256) mismatch"):
                self._verify(manifest, bundle)

    def test_reflection_promotion_flag_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(bundle / "reflection-pass.json")
            value["reflection_only"] = False
            (bundle / "reflection-pass.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "(byte-size|SHA-256) mismatch"):
                self._verify(manifest, bundle)

    def test_authority_acceptance_without_bounded_contract_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(bundle / "authority-hold.json")
            value["decision"] = "ACCEPT"
            (bundle / "authority-hold.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "(byte-size|SHA-256) mismatch"):
                self._verify(manifest, bundle)

    def test_wrong_expected_case_decision_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["cases"][0]["expected_decision"] = "HOLD"
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "expected HOLD/EVIDENCE_NOT_AUTHORITY"):
                self._verify(manifest, bundle)

    def test_unknown_transition_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["cases"][0]["attempted_transition"] = "EVIDENCE_TO_SOMETHING_ELSE"
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "expected BLOCK/EVIDENCE_NOT_AUTHORITY but evaluated BLOCK/UNKNOWN_TRANSITION"):
                self._verify(manifest, bundle)

    def test_replay_side_effect_flag_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["replay"]["steps"][0]["side_effect_executed"] = True
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(BoundaryError, "replay steps must not execute side effects"):
                self._verify(manifest, bundle)

    def test_wrong_exact_subject_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            with self.assertRaisesRegex(BoundaryError, "checked_subject does not match"):
                verify_boundary(
                    manifest,
                    bundle,
                    checked_subject="b54173530c675083426137176cde0aed0b90853a",
                    expected_proofpath_subject=PROOFPATH_HEAD,
                )

    def test_wrong_proofpath_subject_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            with self.assertRaisesRegex(BoundaryError, "ProofPath subject does not match"):
                verify_boundary(
                    manifest,
                    bundle,
                    checked_subject=CGQA_HEAD,
                    expected_proofpath_subject="b54173530c675083426137176cde0aed0b90853a",
                )


if __name__ == "__main__":
    unittest.main()
