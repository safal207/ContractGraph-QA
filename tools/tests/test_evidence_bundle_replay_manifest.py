from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.evidence_bundle_replay_manifest import EvidenceManifestError, verify_bundle


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "fixtures" / "p1-2"
FIXTURE_MANIFEST = FIXTURE_ROOT / "evidence-bundle-replay-manifest.v0.1.json"
FIXTURE_BUNDLE = FIXTURE_ROOT / "bundle"
BUNDLE_SUBJECT = "fcd5e88655eedd3e4e4d3944bb133a8e2c8b0d8e"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class EvidenceBundleReplayManifestTest(unittest.TestCase):
    def _copy_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        manifest = root / "manifest.json"
        bundle = root / "bundle"
        shutil.copy2(FIXTURE_MANIFEST, manifest)
        shutil.copytree(FIXTURE_BUNDLE, bundle)
        return temp, manifest, bundle

    def _verify(self, manifest: Path, bundle: Path) -> dict:
        return verify_bundle(
            manifest,
            bundle,
            checked_subject=BUNDLE_SUBJECT,
            expected_bundle_subject=BUNDLE_SUBJECT,
        )

    def test_fixture_passes_with_complete_membership_and_replay(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            result = self._verify(manifest, bundle)
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["subject_count"], 4)
        self.assertEqual(result["artifact_count"], 6)
        self.assertEqual(result["member_count"], 6)
        self.assertEqual(result["replay_step_count"], 6)
        self.assertTrue(result["replay_stable"])
        self.assertFalse(result["side_effects_executed"])
        self.assertEqual(result["authority"], {
            "execution_authorized": False,
            "external_effects_authorized": False,
            "mutation_authorized": False,
        })

    def test_replay_receipt_is_deterministic(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            first = self._verify(manifest, bundle)
            second = self._verify(manifest, bundle)
        self.assertEqual(first, second)

    def test_tampered_file_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "intent.json").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "(byte-size|SHA-256) mismatch"):
                self._verify(manifest, bundle)

    def test_unlisted_file_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "unlisted.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "unlisted=unlisted.json"):
                self._verify(manifest, bundle)

    def test_missing_declared_file_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            (bundle / "durable-record.json").unlink()
            with self.assertRaisesRegex(EvidenceManifestError, "missing or unreadable"):
                self._verify(manifest, bundle)

    def test_duplicate_path_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][1]["path"] = value["artifacts"][0]["path"]
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "duplicate artifact path"):
                self._verify(manifest, bundle)

    def test_duplicate_digest_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][1]["sha256"] = value["artifacts"][0]["sha256"]
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "duplicate artifact SHA-256"):
                self._verify(manifest, bundle)

    def test_path_traversal_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][0]["path"] = "../escape.json"
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "traversal"):
                self._verify(manifest, bundle)

    def test_source_revision_drift_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["artifacts"][0]["source_revision"] = BUNDLE_SUBJECT
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "does not match subject"):
                self._verify(manifest, bundle)

    def test_unknown_replay_artifact_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["replay"]["steps"][0]["input_artifact_ids"] = ["A-UNKNOWN"]
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "unknown artifact"):
                self._verify(manifest, bundle)

    def test_side_effect_flag_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["replay"]["steps"][2]["side_effect_executed"] = True
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "must not execute side effects"):
                self._verify(manifest, bundle)

    def test_authority_flag_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            value = _load(manifest)
            value["authority"]["mutation_authorized"] = True
            manifest.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(EvidenceManifestError, "authority.mutation_authorized"):
                self._verify(manifest, bundle)

    def test_wrong_bundle_subject_fails_closed(self) -> None:
        temp, manifest, bundle = self._copy_fixture()
        with temp:
            with self.assertRaisesRegex(EvidenceManifestError, "does not match expected bundle subject"):
                verify_bundle(
                    manifest,
                    bundle,
                    checked_subject=BUNDLE_SUBJECT,
                    expected_bundle_subject="b54173530c675083426137176cde0aed0b90853a",
                )


if __name__ == "__main__":
    unittest.main()
