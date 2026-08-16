import json
import tempfile
import unittest
from pathlib import Path

from contractgraph_qa.recovery_package_completeness import (
    EVIDENCE_BOUNDARY,
    PARENT_SYSTEM_013_HEAD,
    PARENT_SYSTEM_013_RECEIPT_DIGEST,
    RecoveryPackageError,
    _make_live_wal_package,
    _mutate_case,
    run_case,
    run_matrix,
    validate_package,
)


class RecoveryPackageCompletenessTests(unittest.TestCase):
    def test_constants_are_pinned(self):
        self.assertEqual(PARENT_SYSTEM_013_HEAD, "896b8c6e4710c733e7ac82ac70e0287f3ffa017d")
        self.assertEqual(
            PARENT_SYSTEM_013_RECEIPT_DIGEST,
            "sha256:cd35a7a0157b5750986ea85c7482c6b62310d62cca9e3fd2db18831a2a746c20",
        )
        self.assertEqual(EVIDENCE_BOUNDARY, "RECOVERY_PACKAGE_COMPLETENESS_NOT_AUTHORITY")

    def _package(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name) / "package"
        _make_live_wal_package(root)
        return td, root

    def test_complete_package_allows_observation_but_holds_execution(self):
        td, root = self._package()
        try:
            receipt = validate_package(root)
            self.assertEqual(receipt["classification"], "COMPLETE_COHERENT")
            self.assertEqual(receipt["observationDecision"], "ALLOW_OBSERVATION")
            self.assertEqual(receipt["executionDecision"], "HOLD")
            self.assertTrue(receipt["packageComplete"])
            self.assertTrue(receipt["generationCoherent"])
            self.assertFalse(receipt["authorityClaimed"])
        finally:
            td.cleanup()

    def test_missing_required_wal_is_rejected(self):
        td, root = self._package()
        try:
            _mutate_case("missing_required_wal", root)
            receipt = validate_package(root)
            self.assertEqual(receipt["classification"], "MISSING_REQUIRED_COMPONENT")
            self.assertEqual(receipt["missingComponents"], ["authority.db-wal"])
            self.assertEqual(receipt["observationDecision"], "HOLD")
        finally:
            td.cleanup()

    def test_tampered_wal_digest_is_rejected_before_observation(self):
        td, root = self._package()
        try:
            _mutate_case("tampered_required_wal", root)
            receipt = validate_package(root)
            self.assertEqual(receipt["classification"], "DIGEST_MISMATCH")
            self.assertEqual(receipt["digestMismatches"], ["authority.db-wal"])
            self.assertEqual(receipt["observationDecision"], "HOLD")
            self.assertIsNone(receipt["commitMarkerGeneration"])
        finally:
            td.cleanup()

    def test_generation_incoherence_is_rejected(self):
        td, root = self._package()
        try:
            _mutate_case("generation_incoherent_manifest", root)
            receipt = validate_package(root)
            self.assertEqual(receipt["classification"], "GENERATION_INCOHERENT")
            self.assertEqual(receipt["packageGeneration"], 3)
            self.assertEqual(receipt["commitMarkerGeneration"], 2)
            self.assertEqual(receipt["projectionGeneration"], 2)
            self.assertEqual(receipt["observationDecision"], "HOLD")
        finally:
            td.cleanup()

    def test_parent_head_drift_rejected(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, parent_head="0" * 40)
        finally:
            td.cleanup()

    def test_parent_receipt_drift_rejected(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, parent_receipt_digest="sha256:" + "0" * 64)
        finally:
            td.cleanup()

    def test_evidence_boundary_promotion_rejected(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, evidence_boundary="RECOVERY_PACKAGE_PROVES_AUTHORITY")
        finally:
            td.cleanup()

    def test_package_completeness_cannot_claim_authority(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, authority_claimed=True)
        finally:
            td.cleanup()

    def test_package_verifier_cannot_transfer_authority(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, authority_transfer="EXECUTOR")
        finally:
            td.cleanup()

    def test_package_completeness_cannot_authorize_execution(self):
        td, root = self._package()
        try:
            with self.assertRaises(RecoveryPackageError):
                validate_package(root, execution_authorized=True)
        finally:
            td.cleanup()

    def test_manifest_required_component_set_cannot_drop_wal(self):
        td, root = self._package()
        try:
            path = root / "manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["requiredComponents"].remove("authority.db-wal")
            path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(RecoveryPackageError):
                validate_package(root)
        finally:
            td.cleanup()

    def test_semantic_receipt_is_stable_across_run_specific_wal_bytes(self):
        expected = "sha256:58ff962f91a4f57612b31ed4093d79db152e0dc818a4a81d9f3abaffc23ea408"
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            first = run_matrix(Path(td1))
            second = run_matrix(Path(td2))
            self.assertEqual(first["receiptDigest"], expected)
            self.assertEqual(second["receiptDigest"], expected)
            self.assertIn("evidenceSetDigest", first)
            self.assertIn("recordDigest", first)

    def test_live_cases_preserve_execution_hold(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            for case in (
                "complete_live_wal_package",
                "missing_required_wal",
                "tampered_required_wal",
                "generation_incoherent_manifest",
            ):
                receipt = run_case(case, out)
                self.assertEqual(receipt["executionDecision"], "HOLD")
                self.assertFalse(receipt["authorityClaimed"])


if __name__ == "__main__":
    unittest.main()
