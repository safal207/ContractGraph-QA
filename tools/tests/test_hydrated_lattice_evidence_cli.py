from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from contractgraph_qa.hydrated_lattice_evidence_cli import main


def _fixtures(root: Path) -> tuple[Path, Path, Path]:
    static = {
        "status": "pass",
        "extraction": {"astSha256": "a" * 64, "profileSha256": "b" * 64},
        "lifecycleVerification": {"status": "pass"},
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
    trace = {
        "schemaVersion": "execution-trace-v0.1",
        "traceId": "cli-trace",
        "events": [
            {
                "eventId": "event-1",
                "economicEffect": {
                    "actionId": "release-1",
                    "effectKey": "settlement",
                    "occurrenceId": "occ-1",
                    "applied": True,
                },
                "stateCommit": {
                    "commitId": "commit-1",
                    "conflictKey": "escrow-1",
                    "parentState": "Funded",
                    "parentVersion": 1,
                    "operation": "release",
                    "successorState": "Released",
                    "successorVersion": 2,
                    "committed": True,
                },
                "sourceRef": "fixture://cli",
            }
        ],
    }
    bindings = {
        "schemaVersion": "hydration-bindings-v0.1",
        "bindingId": "cli-bindings",
        "authorityRequiredOperations": ["release"],
        "timeSensitiveOperations": [],
        "commits": [
            {
                "commitId": "commit-1",
                "authorityRef": "fixture://authority",
                "evidenceRefs": [],
                "timeWitnessRefs": [],
            }
        ],
    }
    paths = (root / "static.json", root / "trace.json", root / "bindings.json")
    for path, payload in zip(paths, (static, trace, bindings), strict=True):
        path.write_text(json.dumps(payload), encoding="utf-8")
    return paths


class HydratedLatticeEvidenceCliTests(unittest.TestCase):
    def test_build_and_verify_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static, trace, bindings = _fixtures(root)
            pack = root / "pack.zip"
            output = io.StringIO()
            with redirect_stdout(output):
                build_code = main(
                    [
                        "build",
                        "--static-result",
                        str(static),
                        "--trace",
                        str(trace),
                        "--bindings",
                        str(bindings),
                        "--output",
                        str(pack),
                    ]
                )
            self.assertEqual(0, build_code)
            built = json.loads(output.getvalue())
            self.assertEqual("pass", built["status"])
            self.assertTrue(pack.exists())

            output = io.StringIO()
            with redirect_stdout(output):
                verify_code = main(
                    [
                        "verify",
                        "--pack",
                        str(pack),
                        "--expected-sha256",
                        built["sha256"],
                    ]
                )
            self.assertEqual(0, verify_code)
            verified = json.loads(output.getvalue())
            self.assertTrue(verified["externalIntegrityBound"])
            self.assertEqual("pass", verified["assessmentStatus"])

    def test_verify_cli_fails_closed_on_wrong_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            static, trace, bindings = _fixtures(root)
            pack = root / "pack.zip"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    main(
                        [
                            "build",
                            "--static-result",
                            str(static),
                            "--trace",
                            str(trace),
                            "--bindings",
                            str(bindings),
                            "--output",
                            str(pack),
                        ]
                    ),
                )
            error = io.StringIO()
            with redirect_stderr(error):
                code = main(
                    ["verify", "--pack", str(pack), "--expected-sha256", "0" * 64]
                )
            self.assertNotEqual(0, code)
            self.assertIn("external pack digest mismatch", error.getvalue())


if __name__ == "__main__":
    unittest.main()
