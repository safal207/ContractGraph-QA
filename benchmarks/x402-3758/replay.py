#!/usr/bin/env python3
"""Run the three-case test overlay against the exact public draft checkout."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import uuid

SUBJECT = "4d3f2387bd3f2db8007cca324ef8dea23264c248"
PACKET = Path(__file__).resolve().parent
TEST_PATH = "typescript/packages/extensions/test/buyer-composition.test.ts"


def command(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Refusing to overwrite retained evidence")
    head = command(["git", "rev-parse", "HEAD"], source)
    if head.returncode or head.stdout.strip() != SUBJECT:
        raise SystemExit("Source identity mismatch")
    if command(["git", "diff", "HEAD", "--quiet"], source).returncode:
        raise SystemExit("Tracked source is dirty")
    overlay = source / TEST_PATH
    if overlay.exists():
        raise SystemExit("Overlay path already exists; inspect before running")
    test_bytes = (PACKET / "buyer-composition.test.ts").read_bytes()
    build = command(["pnpm", "--filter", "@x402/core", "build"], source / "typescript")
    if build.returncode:
        raise SystemExit(build.stdout + build.stderr)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="x402-composition-") as temporary:
        temp = Path(temporary)
        env = dict(os.environ, CGQA_EVIDENCE_OUTPUT=str(temp / "observations.json"))
        overlay.write_bytes(test_bytes)
        try:
            run = command([
                "pnpm", "--filter", "@x402/extensions", "exec", "vitest", "run",
                "test/buyer-composition.test.ts", "--coverage.enabled=false",
                "--reporter=json", "--outputFile=" + str(temp / "vitest.json"),
            ], source / "typescript", env)
            if run.returncode:
                raise SystemExit(run.stdout + run.stderr)
            report = json.loads((temp / "vitest.json").read_text())
            if (report["numPassedTests"], report["numFailedTests"],
                    report["numPendingTests"]) != (3, 0, 0):
                raise SystemExit("Expected exactly three executed passing controls")
            observations = json.loads((temp / "observations.json").read_text())
        finally:
            if overlay.read_bytes() != test_bytes:
                raise SystemExit("Overlay changed during execution; inspect manually")
            overlay.unlink()
    if command(["git", "diff", "HEAD", "--quiet"], source).returncode:
        raise SystemExit("Tracked source changed during execution")
    data = {
        "packet_version": 1, "attempt_id": str(uuid.uuid4()),
        "source_repository": "johnInarti/x402", "source_commit": SUBJECT,
        "started_at": started,
        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "test_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "environment": {
            "node": command(["node", "--version"], source).stdout.strip(),
            "pnpm": command(["pnpm", "--version"], source).stdout.strip(),
            "python": platform.python_version(), "platform": platform.system(),
        },
        "tracked_source_unchanged": True, "core_rebuilt_from_source": True,
        "overlay": TEST_PATH, "native_assertions": {"passed": 3, "failed": 0, "skipped": 0},
        "observations": observations,
        "completion_state": "COMPLETE", "verdict": "PASS_WITHIN_BOUND",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
    print(f"PASS_WITHIN_BOUND: 3 native controls; evidence={output}")


if __name__ == "__main__":
    main()
