import hashlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROOF = ROOT / "proofs" / "attenu-guard-v0.12.0-independent"
DRIVER = PROOF / "replay_reference_releases.py"
STATIC_CHECKER = PROOF / "check_reference_replay_provenance.py"
SUPPLEMENTAL_TEST = PROOF / "test_containment_regressions.py"
PYTHON_SCRIPTS = [
    PROOF / "independent_bundle_verifier.py",
    PROOF / "check_report_provenance.py",
    SUPPLEMENTAL_TEST,
    PROOF / "reference_python_probe.py",
    DRIVER,
    STATIC_CHECKER,
]
TYPESCRIPT_PROBE = PROOF / "reference_ts_probe.cjs"


def _load_driver():
    spec = importlib.util.spec_from_file_location("attenu_reference_replay", DRIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load replay driver: {DRIVER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _wheel_bytes(marker: str) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture/value.txt", marker)
    return payload.getvalue()


class AttenuReferenceReleaseProofTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.driver = _load_driver()

    def test_all_load_bearing_python_scripts_compile(self):
        for path in PYTHON_SCRIPTS:
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                compile(source, str(path), "exec")

    @unittest.skipUnless(shutil.which("node"), "Node.js is not available")
    def test_typescript_probe_parses(self):
        completed = subprocess.run(
            ["node", "--check", str(TYPESCRIPT_PROBE)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_static_reference_replay_evidence_is_pinned(self):
        completed = subprocess.run(
            [sys.executable, str(STATIC_CHECKER), "--static-only"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("observations=24/24", completed.stdout)
        self.assertIn("defect_transitions=8/8", completed.stdout)

    def test_supplemental_containment_regressions_execute(self):
        completed = subprocess.run(
            [sys.executable, str(SUPPLEMENTAL_TEST), "-q"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("OK", completed.stderr)

    def test_verified_artifact_snapshot_survives_path_swap(self):
        trusted = _wheel_bytes("trusted")
        swapped = _wheel_bytes("swapped")
        identity = {
            "filename": "fixture.whl",
            "package": "fixture",
            "version": "1.0.0",
            "sha256": hashlib.sha256(trusted).hexdigest(),
            "bytes": len(trusted),
            "format": "wheel",
        }

        with tempfile.TemporaryDirectory(prefix="attenu-snapshot-regression-") as temporary:
            root = Path(temporary)
            supplied = root / "fixture.whl"
            destination = root / "extracted"
            destination.mkdir()
            supplied.write_bytes(trusted)

            report, frozen_bytes = self.driver._verified_artifact(supplied, identity)
            supplied.write_bytes(swapped)
            self.driver._extract_wheel(frozen_bytes, destination)

            self.assertEqual(
                (destination / "fixture" / "value.txt").read_text(encoding="utf-8"),
                "trusted",
            )
            self.assertEqual(report["sha256"], hashlib.sha256(frozen_bytes).hexdigest())
            self.assertNotEqual(
                report["sha256"],
                hashlib.sha256(supplied.read_bytes()).hexdigest(),
            )
            self.assertEqual(report["execution_source"], "same verified in-memory bytes")


if __name__ == "__main__":
    unittest.main()
