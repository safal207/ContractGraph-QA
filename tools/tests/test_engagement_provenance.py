from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.engagement import write_engagement_bundle
from contractgraph_qa.engagement_provenance import (
    COVERAGE_SCOPE,
    EngagementProvenanceError,
    build_engagement_measurement_artifacts,
    create_engagement_provenance_bundle,
    verify_engagement_provenance_bundle,
)
from contractgraph_qa.finding import canonical_json, load_json_object

ROOT = Path(__file__).resolve().parents[2]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rewrite_bundle(path: Path, mutate) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        payloads = {name: archive.read(name) for name in names}
    mutate(payloads)
    bundle = json.loads(payloads["bundle.json"].decode("utf-8"))
    for name in names:
        if name == "bundle.json":
            continue
        bundle["artifacts"][name]["sha256"] = _sha256(payloads[name])
        bundle["artifacts"][name]["bytes"] = len(payloads[name])
    bundle["baseBundleSha256"] = _sha256(payloads["base-engagement.zip"])
    payloads["bundle.json"] = canonical_json(bundle).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in names:
            archive.writestr(name, payloads[name])


class EngagementProvenanceBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest_path = ROOT / "manifests/examples/engagement-fixture.json"
        cls.result_path = ROOT / "results/examples/CGQA-E-001.engagement-result.json"
        cls.manifest = load_json_object(cls.manifest_path, "manifest")
        cls.result = load_json_object(cls.result_path, "engagementResult")

    def _create(self, root: Path, name: str = "provenance.zip") -> tuple[Path, dict[str, object]]:
        base = root / "base.zip"
        write_engagement_bundle(
            self.manifest_path,
            self.result_path,
            root / "out",
            base,
        )
        target = root / name
        created = create_engagement_provenance_bundle(base, target)
        return target, created

    def test_round_trip_is_deterministic_and_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first, created = self._create(root, "first.zip")
            second, _ = self._create(root, "second.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            verified = verify_engagement_provenance_bundle(first)
            self.assertTrue(verified["ok"])
            self.assertEqual(verified["measurementProvenanceStatus"], "pass")
            self.assertEqual(verified["coverageScope"], COVERAGE_SCOPE)
            self.assertEqual(verified["coverage"]["declaredInvariants"], 3)
            self.assertEqual(verified["coverage"]["checkedInvariants"], 3)
            self.assertEqual(created["bundleSha256"], verified["bundleSha256"])

    def test_missing_check_is_partial_coverage_before_authority(self) -> None:
        incomplete = copy.deepcopy(self.result)
        incomplete["checks"].pop()
        measurement_input, source, provenance = build_engagement_measurement_artifacts(
            self.manifest,
            incomplete,
            manifest_bytes=self.manifest_path.read_bytes(),
            result_bytes=canonical_json(incomplete).encode("utf-8"),
        )
        self.assertEqual(source["declaredInvariantIds"], sorted(source["declaredInvariantIds"]))
        self.assertEqual(len(source["declaredInvariantIds"]), 3)
        self.assertEqual(len(source["observedInvariantIds"]), 2)
        self.assertEqual(measurement_input["measurements"][0]["eligibleUnits"], 3)
        self.assertEqual(measurement_input["measurements"][0]["observedUnits"], 2)
        self.assertEqual(provenance["status"], "blocked")
        self.assertEqual(provenance["measurements"][0]["gateReasons"], ["PARTIAL_COVERAGE"])

    def test_rehashed_source_tamper_is_rejected_semantically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path, _ = self._create(Path(temp_dir))

            def mutate(payloads: dict[str, bytes]) -> None:
                source = json.loads(payloads["measurement-source.json"].decode("utf-8"))
                source["observedInvariantIds"] = source["observedInvariantIds"][:-1]
                payloads["measurement-source.json"] = canonical_json(source).encode("utf-8")

            _rewrite_bundle(path, mutate)
            with self.assertRaisesRegex(
                EngagementProvenanceError, "measurement-source.json does not match"
            ):
                verify_engagement_provenance_bundle(path)

    def test_rehashed_provenance_tamper_is_rejected_by_recomputation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path, _ = self._create(Path(temp_dir))

            def mutate(payloads: dict[str, bytes]) -> None:
                provenance = json.loads(payloads["measurement-provenance.json"].decode("utf-8"))
                provenance["measurements"][0]["coverageFraction"] = 0.5
                payloads["measurement-provenance.json"] = canonical_json(provenance).encode("utf-8")

            _rewrite_bundle(path, mutate)
            with self.assertRaisesRegex(
                EngagementProvenanceError, "recomputed provenance verdict"
            ):
                verify_engagement_provenance_bundle(path)

    def test_rehashed_base_bundle_tamper_is_rejected_by_base_verifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path, _ = self._create(root)

            def mutate(payloads: dict[str, bytes]) -> None:
                nested = root / "nested.zip"
                nested.write_bytes(payloads["base-engagement.zip"])
                with zipfile.ZipFile(nested, "r") as archive:
                    names = archive.namelist()
                    nested_payloads = {name: archive.read(name) for name in names}
                engagement = json.loads(nested_payloads["engagement.json"].decode("utf-8"))
                engagement["coverage"]["checkedInvariants"] = 2
                nested_payloads["engagement.json"] = canonical_json(engagement).encode("utf-8")
                with zipfile.ZipFile(nested, "w", compression=zipfile.ZIP_STORED) as archive:
                    for name in names:
                        archive.writestr(name, nested_payloads[name])
                payloads["base-engagement.zip"] = nested.read_bytes()

            _rewrite_bundle(path, mutate)
            with self.assertRaisesRegex(
                EngagementProvenanceError, "embedded engagement bundle failed verification"
            ):
                verify_engagement_provenance_bundle(path)


if __name__ == "__main__":
    unittest.main()
