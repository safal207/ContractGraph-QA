from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from contractgraph_qa.hydrated_lattice_evidence import (
    HydratedLatticeEvidencePackError,
    build_hydrated_lattice_evidence_pack,
    canonical_json_bytes,
    verify_hydrated_lattice_evidence_pack,
)


PACK_ORDER = [
    "static-result.json",
    "execution-trace.json",
    "hydration-bindings.json",
    "assessment.json",
    "client-summary.md",
    "manifest.json",
]
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
FIXED_CREATE_VERSION = 20
FIXED_EXTRACT_VERSION = 20


def static_result() -> dict[str, object]:
    return {
        "status": "pass",
        "extraction": {
            "astSha256": "a" * 64,
            "profileSha256": "b" * 64,
        },
        "lifecycleVerification": {"status": "pass", "invariantId": "CGQ-LIVE-001"},
        "latticeTemplate": {
            "points": [
                {"state": "Funded", "valuePresence": True, "safeTerminal": False},
                {"state": "Released", "valuePresence": False, "safeTerminal": True},
            ],
            "transitionTemplates": [
                {
                    "sourceState": "Funded",
                    "targetState": "Released",
                    "sourceEvidence": {"function": "release"},
                }
            ],
        },
    }


def trace() -> dict[str, object]:
    return {
        "schemaVersion": "execution-trace-v0.1",
        "traceId": "trace-pack-001",
        "events": [
            {
                "eventId": "event-1",
                "economicEffect": {
                    "actionId": "release-1",
                    "effectKey": "escrow-settlement",
                    "occurrenceId": "settlement-1",
                    "applied": True,
                },
                "stateCommit": {
                    "commitId": "commit-1",
                    "conflictKey": "escrow-1",
                    "parentState": "Funded",
                    "parentVersion": 7,
                    "operation": "release",
                    "successorState": "Released",
                    "successorVersion": 8,
                    "committed": True,
                },
                "sourceRef": "fixture://trace/release-1",
            }
        ],
    }


def bindings() -> dict[str, object]:
    return {
        "schemaVersion": "hydration-bindings-v0.1",
        "bindingId": "bindings-pack-001",
        "authorityRequiredOperations": ["release"],
        "timeSensitiveOperations": [],
        "commits": [
            {
                "commitId": "commit-1",
                "authorityRef": "fixture://authority/release-1",
                "evidenceRefs": ["fixture://evidence/release-1"],
                "timeWitnessRefs": [],
            }
        ],
        "scope": "synthetic hydrated evidence-pack regression",
    }


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rewrite_pack(path: Path, mutate) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        blobs = {name: archive.read(name) for name in PACK_ORDER}

    mutate(blobs)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in PACK_ORDER:
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, blobs[name])


def rehash_manifest_entry(blobs: dict[str, bytes], name: str) -> None:
    manifest = json.loads(blobs["manifest.json"])
    for item in manifest["entries"]:
        if item["path"] == name:
            item["sha256"] = hashlib.sha256(blobs[name]).hexdigest()
            item["bytes"] = len(blobs[name])
            break
    blobs["manifest.json"] = canonical_json_bytes(manifest)


class HydratedLatticeEvidencePackTests(unittest.TestCase):
    def _build(self, root: Path, name: str = "pack.zip") -> tuple[Path, dict[str, object]]:
        static_path = root / "static.json"
        trace_path = root / "trace.json"
        bindings_path = root / "bindings.json"
        output = root / name
        write_json(static_path, static_result())
        write_json(trace_path, trace())
        write_json(bindings_path, bindings())
        result = build_hydrated_lattice_evidence_pack(static_path, trace_path, bindings_path, output)
        return output, result

    def test_deterministic_pack_rebuild_and_local_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, first_result = self._build(root, "first.zip")
            second, second_result = self._build(root, "second.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_result["sha256"], second_result["sha256"])
            with zipfile.ZipFile(first, "r") as archive:
                for info in archive.infolist():
                    self.assertEqual(FIXED_CREATE_VERSION, info.create_version)
                    self.assertEqual(FIXED_EXTRACT_VERSION, info.extract_version)
            verified = verify_hydrated_lattice_evidence_pack(first)
            self.assertEqual("verified", verified["status"])
            self.assertEqual("pass", verified["assessmentStatus"])
            self.assertFalse(verified["externalIntegrityBound"])
            self.assertEqual("local_replay_consistency_only", verified["verificationBoundary"])

    def test_external_pack_digest_binds_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, built = self._build(Path(tmp))
            verified = verify_hydrated_lattice_evidence_pack(
                pack, expected_pack_sha256=str(built["sha256"])
            )
            self.assertTrue(verified["externalIntegrityBound"])
            self.assertEqual("externally_bound_exact_bytes_plus_local_replay", verified["verificationBoundary"])

    def test_external_digest_and_replay_use_same_immutable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack, built = self._build(root, "pack.zip")
            replacement, _ = self._build(root, "replacement.zip")

            def mutate(blobs: dict[str, bytes]) -> None:
                assessment = json.loads(blobs["assessment.json"])
                assessment["hydratedLattice"]["observedPoints"][0]["valuePresence"] = 1
                blobs["assessment.json"] = canonical_json_bytes(assessment)
                rehash_manifest_entry(blobs, "assessment.json")

            rewrite_pack(replacement, mutate)
            replacement_bytes = replacement.read_bytes()
            original_read_bytes = Path.read_bytes
            swapped = False

            def read_then_replace(path_obj: Path) -> bytes:
                nonlocal swapped
                snapshot = original_read_bytes(path_obj)
                if path_obj == pack and not swapped:
                    pack.write_bytes(replacement_bytes)
                    swapped = True
                return snapshot

            with mock.patch.object(Path, "read_bytes", autospec=True, side_effect=read_then_replace):
                verified = verify_hydrated_lattice_evidence_pack(
                    pack, expected_pack_sha256=str(built["sha256"])
                )

            self.assertTrue(swapped)
            self.assertTrue(verified["externalIntegrityBound"])
            self.assertEqual(str(built["sha256"]), verified["sha256"])
            self.assertEqual(replacement_bytes, pack.read_bytes())

    def test_wrong_external_digest_fails_for_exact_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, built = self._build(Path(tmp))
            wrong = "0" * 64 if built["sha256"] != "0" * 64 else "1" * 64
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError, "external pack digest mismatch"
            ):
                verify_hydrated_lattice_evidence_pack(pack, expected_pack_sha256=wrong)

    def test_rehashed_type_tamper_in_assessment_fails_exact_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))

            def mutate(blobs: dict[str, bytes]) -> None:
                assessment = json.loads(blobs["assessment.json"])
                self.assertIs(assessment["hydratedLattice"]["observedPoints"][0]["valuePresence"], True)
                assessment["hydratedLattice"]["observedPoints"][0]["valuePresence"] = 1
                blobs["assessment.json"] = canonical_json_bytes(assessment)
                rehash_manifest_entry(blobs, "assessment.json")

            rewrite_pack(pack, mutate)
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError,
                "assessment.json does not match exact hydrated-lattice replay",
            ):
                verify_hydrated_lattice_evidence_pack(pack)

    def test_rehashed_trace_tamper_fails_semantic_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))

            def mutate(blobs: dict[str, bytes]) -> None:
                document = json.loads(blobs["execution-trace.json"])
                document["events"][0]["stateCommit"]["operation"] = "refund"
                blobs["execution-trace.json"] = canonical_json_bytes(document)
                rehash_manifest_entry(blobs, "execution-trace.json")

            rewrite_pack(pack, mutate)
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError,
                "assessment.json does not match exact hydrated-lattice replay",
            ):
                verify_hydrated_lattice_evidence_pack(pack)

    def test_manifest_boolean_type_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))

            def mutate(blobs: dict[str, bytes]) -> None:
                manifest = json.loads(blobs["manifest.json"])
                manifest["authority"]["productionAuthorization"] = 0
                blobs["manifest.json"] = canonical_json_bytes(manifest)

            rewrite_pack(pack, mutate)
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError, "manifest authority boundary mismatch"
            ):
                verify_hydrated_lattice_evidence_pack(pack)

    def test_noncanonical_zip_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))
            with zipfile.ZipFile(pack, "r") as archive:
                blobs = {name: archive.read(name) for name in PACK_ORDER}
            with zipfile.ZipFile(pack, "w", compression=zipfile.ZIP_STORED) as archive:
                for index, name in enumerate(PACK_ORDER):
                    info = zipfile.ZipInfo(
                        name,
                        date_time=(1981, 1, 1, 0, 0, 0) if index == 0 else FIXED_TIME,
                    )
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, blobs[name])
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError, "non-canonical ZIP timestamp"
            ):
                verify_hydrated_lattice_evidence_pack(pack)

    def test_noncanonical_zip_version_metadata_is_rejected(self) -> None:
        mutations = (
            ("create_version", "non-canonical ZIP create version"),
            ("extract_version", "non-canonical ZIP extract version"),
        )
        for field, reason in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                pack, _ = self._build(Path(tmp))
                with zipfile.ZipFile(pack, "r") as archive:
                    blobs = {name: archive.read(name) for name in PACK_ORDER}
                with zipfile.ZipFile(pack, "w", compression=zipfile.ZIP_STORED) as archive:
                    for index, name in enumerate(PACK_ORDER):
                        info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                        info.compress_type = zipfile.ZIP_STORED
                        info.create_version = FIXED_CREATE_VERSION
                        info.extract_version = FIXED_EXTRACT_VERSION
                        info.create_system = 3
                        info.external_attr = 0o100644 << 16
                        if index == 0:
                            setattr(info, field, 21)
                        archive.writestr(info, blobs[name])
                with self.assertRaisesRegex(HydratedLatticeEvidencePackError, reason):
                    verify_hydrated_lattice_evidence_pack(pack)

    def test_noncanonical_archive_comment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))
            with zipfile.ZipFile(pack, "a") as archive:
                archive.comment = b"noncanonical"
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError, "non-canonical ZIP archive comment"
            ):
                verify_hydrated_lattice_evidence_pack(pack)

    def test_noncanonical_entry_extra_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack, _ = self._build(Path(tmp))
            with zipfile.ZipFile(pack, "r") as archive:
                blobs = {name: archive.read(name) for name in PACK_ORDER}
            with zipfile.ZipFile(pack, "w", compression=zipfile.ZIP_STORED) as archive:
                for index, name in enumerate(PACK_ORDER):
                    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    if index == 0:
                        info.extra = b"\x01\x00\x00\x00"
                    archive.writestr(info, blobs[name])
            with self.assertRaisesRegex(
                HydratedLatticeEvidencePackError, "non-canonical ZIP extra field"
            ):
                verify_hydrated_lattice_evidence_pack(pack)


if __name__ == "__main__":
    unittest.main()
