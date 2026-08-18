#!/usr/bin/env python3
"""Capture fail-closed runtime identity for GONKA-ATMAN G-005.

Run only against a local/explicitly permitted Gonka testenv. Container identity is
necessary but not sufficient: PROVEN also requires an independent provenance file
binding the sealed source revision to the immutable running image digests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def inspect_container(name: str, component: str) -> dict[str, str]:
    container_id = run("docker", "inspect", "--format={{.Id}}", name)
    image_id = run("docker", "inspect", "--format={{.Image}}", name)
    image_ref = run("docker", "inspect", "--format={{.Config.Image}}", name)
    repo_digests_raw = run("docker", "image", "inspect", "--format={{json .RepoDigests}}", image_id)
    repo_digests = json.loads(repo_digests_raw or "[]")
    digests = sorted({str(x).split("@", 1)[1] for x in repo_digests if "@sha256:" in str(x)})
    if len(digests) != 1:
        raise RuntimeError(f"{component}: expected exactly one immutable RepoDigest, got {repo_digests}")
    return {
        "component": component,
        "container_id": container_id,
        "image_id": image_id,
        "image_ref": image_ref or image_id,
        "image_digest": digests[0],
    }


def load_provenance(path: str | None) -> dict | None:
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-revision", required=True)
    p.add_argument("--config-generation", required=True)
    p.add_argument("--devshardctl", required=True)
    p.add_argument("--versiond", required=True)
    p.add_argument("--devshardd", required=True)
    p.add_argument("--versiond-router")
    p.add_argument("--provenance-file")
    p.add_argument("--output", default="runtime_fingerprint.json")
    a = p.parse_args()

    mapping = [("devshardctl", a.devshardctl), ("versiond", a.versiond), ("devshardd", a.devshardd)]
    if a.versiond_router:
        mapping.append(("versiond-router", a.versiond_router))
    try:
        artifacts = [inspect_container(name, component) for component, name in mapping]
        provenance = load_provenance(a.provenance_file)
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"runtime fingerprint capture failed: {exc}", file=sys.stderr)
        return 2

    payload = {
        "schema_version": "gonka-atman-runtime-fingerprint-v0.2",
        "case_id": "G-005",
        "source_revision": a.source_revision,
        "runtime_artifacts": artifacts,
        "config_generation": a.config_generation,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provenance": provenance,
        "verdict": "UNPROVEN" if provenance is None else "PROVEN",
        "notes": "Runtime container/image identity captured from Docker. PROVEN is valid only after verifier confirms provenance source SHA and component image-digest bindings.",
    }
    with open(a.output, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2)
        fh.write("\n")
    print(a.output)
    if provenance is None:
        print("provenance file absent: emitted UNPROVEN runtime fingerprint", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
