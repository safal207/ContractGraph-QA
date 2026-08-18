import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from contractgraph_qa.astra_evidence import (
    AstraEvidenceError,
    build_astra_evidence_pack,
    verify_astra_evidence_pack,
)


class AstraEvidenceTests(unittest.TestCase):
    def _input(self):
        return {
            "analyses": {
                "queue": {
                    "start": "s",
                    "target": "bad",
                    "nodes": ["s", "slow", "fast", "bad"],
                    "edges": [
                        {"from": "s", "to": "slow", "transition_id": "a-slow", "tps": 0.1},
                        {"from": "s", "to": "fast", "transition_id": "z-fast", "tps": 1.0},
                        {"from": "slow", "to": "bad", "transition_id": "b-bad", "tps": 0.1},
                        {"from": "fast", "to": "bad", "transition_id": "y-bad", "tps": 1.0},
                    ],
                },
                "transition": {
                    "transitions": [{
                        "id": "duplicate-settlement",
                        "stimulus": 1.0,
                        "state_complexity": 1.0,
                        "future_pressure": 1.0,
                        "witness_gap": 1.0,
                        "divergence": 1.0,
                    }]
                },
            }
        }

    def test_pack_is_deterministic_and_verifies_by_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            source.write_text(json.dumps(self._input()), encoding="utf-8")
            a = root / "a.zip"
            b = root / "b.zip"
            first = build_astra_evidence_pack(source, a)
            second = build_astra_evidence_pack(source, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(first["sha256"], second["sha256"])
            verified = verify_astra_evidence_pack(a)
            self.assertEqual(verified["status"], "verified")
            self.assertEqual(verified["analyses"], ["queue", "transition"])

    def test_rehashed_tampered_results_still_fail_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.json"
            source.write_text(json.dumps(self._input()), encoding="utf-8")
            original = root / "original.zip"
            build_astra_evidence_pack(source, original)
            with zipfile.ZipFile(original, "r") as archive:
                blobs = {name: archive.read(name) for name in archive.namelist()}
            results = json.loads(blobs["results.json"])
            results["results"]["transition"]["verdict"] = "FORGED"
            # A readable/tampered pack must not verify; exact failure coordinate is implementation-defined.
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_STORED) as archive:
                for name in ["input.json", "results.json", "summary.md", "manifest.json"]:
                    data = blobs[name]
                    if name == "results.json":
                        data = (json.dumps(results, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data)
            with self.assertRaises(AstraEvidenceError):
                verify_astra_evidence_pack(tampered)

    def test_unknown_analysis_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            source.write_text(json.dumps({"analyses": {"magic": {}}}), encoding="utf-8")
            with self.assertRaises(AstraEvidenceError):
                build_astra_evidence_pack(source, Path(tmp) / "out.zip")


if __name__ == "__main__":
    unittest.main()
