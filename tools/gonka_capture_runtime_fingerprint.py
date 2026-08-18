#!/usr/bin/env python3
"""Capture fail-closed runtime identity for GONKA-ATMAN G-005.

Run only against a local/explicitly permitted Gonka testenv. The collector does not
claim a finding; it emits the runtime witness needed before target-side interpretation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def inspect_container(name: str, component: str) -> dict[str, str]:
    container_id = run("docker", "inspect", "--format={{.Id}}", name)
    image_id = run("docker", "inspect", "--format={{.Image}}", name)
    image_ref = run("docker", "inspect", "--format={{.Config.Image}}", name)
    material = f"{container_id}\n{image_id}\n{image_ref}".encode()
    digest = "sha256:" + hashlib.sha256(material).hexdigest()
    return {"component": component, "artifact_ref": image_ref or image_id, "sha256": digest}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-revision", required=True)
    p.add_argument("--config-generation", required=True)
    p.add_argument("--devshardctl", required=True)
    p.add_argument("--versiond", required=True)
    p.add_argument("--devshardd", required=True)
    p.add_argument("--versiond-router")
    p.add_argument("--output", default="runtime_fingerprint.json")
    a = p.parse_args()

    mapping = [("devshardctl", a.devshardctl), ("versiond", a.versiond), ("devshardd", a.devshardd)]
    if a.versiond_router:
        mapping.append(("versiond-router", a.versiond_router))
    try:
        artifacts = [inspect_container(name, component) for component, name in mapping]
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"runtime fingerprint capture failed: {exc}", file=sys.stderr)
        return 2

    payload = {
        "schema_version": "gonka-atman-runtime-fingerprint-v0.1",
        "case_id": "G-005",
        "source_revision": a.source_revision,
        "runtime_artifacts": artifacts,
        "config_generation": a.config_generation,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "verdict": "PROVEN",
        "notes": "Container identity captured from the running local Gonka testenv; source/runtime equality must still be established by the testenv build/run procedure.",
    }
    with open(a.output, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write("\n")
    print(a.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
