#!/usr/bin/env python3
"""Apply native CGQA identity and durable-reopen capabilities to this proof.

This checks local evidence identity. It never turns a host-generated report
into an independent observer, production verdict, or publication authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

PROOF = Path(__file__).resolve().parent
REPOSITORY = PROOF.parents[1]
sys.path.insert(0, str(REPOSITORY))

from contractgraph_qa.causal_temporal_utils import canonical_sha256
from contractgraph_qa.proof_integrity import evaluate_subject_freeze, verify_durable_manifest


def main() -> int:
    # Re-run the separately authored gate before trusting source-pins metadata.
    subprocess.run(["node", str(PROOF / "run-proof.mjs"), "--check", str(PROOF / "report.json")],
                   check=True, capture_output=True, text=True)
    pins = json.loads((PROOF / "source-pins.json").read_text())
    report = json.loads((PROOF / "report.json").read_text())
    before = {
        "repository": pins["repository"],
        "commit": pins["commit"],
        "artifacts": [
            {"path": "vectors/" + row["file"], "sha256": row["sha256"]}
            for row in pins["vectors"]
        ] + [
            {"path": row["file"], "sha256": row["sha256"]}
            for row in report["implementation"]
        ],
    }
    after = copy.deepcopy(before)
    for row in after["artifacts"]:
        row["sha256"] = hashlib.sha256((PROOF / row["path"]).read_bytes()).hexdigest()
    frozen = evaluate_subject_freeze({
        "schema": "cgqa/subject-freeze/v0.1", "subjectBefore": before, "subjectAfter": after,
    })
    changed = copy.deepcopy(after)
    changed["artifacts"][0]["sha256"] = "0" * 64
    negative = evaluate_subject_freeze({
        "schema": "cgqa/subject-freeze/v0.1", "subjectBefore": before, "subjectAfter": changed,
    })
    if frozen["status"] != "pass" or negative["classification"] != "STALE_SUBJECT":
        raise RuntimeError("Native exact-subject gate or its negative control failed")

    result = {
        "subject_freeze": frozen,
        "subject_negative_control": negative["classification"],
        "native_module_sha256": hashlib.sha256(
            (REPOSITORY / "contractgraph_qa/proof_integrity.py").read_bytes()).hexdigest(),
        "durable_reopen": {"status": "not_run", "reason": "artifact manifest not yet created"},
    }
    manifest_file = PROOF / "artifacts.json"
    if manifest_file.exists():
        subprocess.run(["node", str(PROOF / "check-artifacts.mjs")],
                       check=True, capture_output=True, text=True)
        retained = json.loads(manifest_file.read_text())
        # Translate retained expectations, never rebuild expectations from the
        # filesystem that is being tested.
        native = {
            "schema": "cgqa/durable-evidence-manifest/v0.1",
            "entries": [
                {"path": row["path"], "size": row["bytes"], "sha256": row["sha256"]}
                for row in retained["artifacts"]
            ],
        }
        native["manifestHash"] = canonical_sha256(native)
        result["durable_reopen"] = verify_durable_manifest(REPOSITORY, native)
        if result["durable_reopen"]["status"] != "pass":
            raise RuntimeError("Native durable-reopen check failed")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
