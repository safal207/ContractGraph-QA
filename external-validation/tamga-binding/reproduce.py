#!/usr/bin/env python3
"""Reproduce a bounded historical Tamga fixture-verifier comparison.

Default: fetch six pinned upstream files, verify their Git blob identities,
then run eight verifier invocations against temporary local fixtures.
No installation, provider interaction, or payment is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from urllib.request import urlopen

BASE = "7a4bc537cb1a974bae89bfc96f9be55bc05d0b4b"
FIXED = "c62d4a822d7e3546931197905e137d0eb6fb490e"
FILES = {
    "before_verify": (BASE, "tools/verify_pairing_fixture.py", "8195c659d38d7e94d71c8606a40ca54ba1f92a5e"),
    "after_verify": (FIXED, "tools/verify_pairing_fixture.py", "bd72f616b9431322534c1b803cf23c58c09aa83b"),
    "keccak": (FIXED, "tools/keccak256.py", "e4c6724b3df72f12b93ba756b6bf2f105d2d4a3a"),
    "fixture": (FIXED, "docs/pairing/pairing-fixture.json", "675142be41feef6847be069b62bdf9c7174ca1e8"),
    "delivery": (FIXED, "docs/pairing/delivery.stdout", "e561bdbf79a19065b7a0652fb2d67e3c5494f728"),
    "input": (FIXED, "docs/pairing/input.json", "788df9a7f66f742d3efe4ac04602c0457cee3e04"),
}


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def record_hash(charge):
    record = {k: v for k, v in charge.items() if k not in ("h", "node_sig")}
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256((charge["prev"] + encoded).encode("utf-8")).hexdigest()


def expected_payload(charge, delivery, wanted_ok, wanted_where):
    if wanted_ok:
        return {"ok": True, "receiptHash": record_hash(charge),
                "stdout_sha256": hashlib.sha256(delivery).hexdigest(),
                "checks": ["labeling", "membership", "delivery_sha256",
                           "delivery_keccak256", "input_sha256"]}
    errors = {
        "membership": "recomputed h != receiptHash or charge.h",
        "input_commitment": "sha256(input.json) != fixture commitment or charge.input_sha256",
    }
    return {"ok": False, "where": wanted_where, "error": errors[wanted_where]}


def matches_expected_result(outcome, expected_output, returncode, stderr):
    return (isinstance(outcome, dict)
            and outcome.get("ok") is expected_output["ok"]
            and outcome == expected_output
            and returncode == (0 if expected_output["ok"] else 1)
            and stderr == "")


def load_source_packet(path):
    if path is None:
        return None
    packet = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict) or not isinstance(packet.get("contents"), dict):
        raise ValueError("--source-packet must contain a contents object")
    contents = packet["contents"]
    for key in FILES:
        if not isinstance(contents.get(key), str):
            raise ValueError(f"--source-packet contents[{key!r}] must be a string")
    return contents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-packet", type=Path, help="offline packet with a contents mapping")
    parser.add_argument("--output", type=Path, default=Path("results.json"))
    args = parser.parse_args()
    source_contents = load_source_packet(args.source_packet)
    sources, identities = {}, []
    for key, (revision, path, expected) in FILES.items():
        url = f"https://raw.githubusercontent.com/goun7/tamga-protocol/{revision}/{path}"
        if source_contents is not None:
            data = source_contents[key].encode("utf-8")
        else:
            with urlopen(url, timeout=30) as response:
                data = response.read()
        actual = git_blob(data)
        if actual != expected:
            raise RuntimeError(f"source identity mismatch: {key}: {actual} != {expected}")
        sources[key] = data
        identities.append({"key": key, "revision": revision, "path": path,
                           "git_blob_sha1": actual, "sha256": hashlib.sha256(data).hexdigest(),
                           "bytes": len(data)})

    scenarios = [
        ("untouched", {"before": (True, None), "after": (True, None)}),
        ("stale_record_hash", {"before": (True, None), "after": (False, "membership")}),
        ("stale_input_binding", {"before": (True, None), "after": (False, "input_commitment")}),
        ("consistent_rewrite", {"before": (True, None), "after": (True, None)}),
    ]
    runs = []
    with tempfile.TemporaryDirectory(prefix="tamga-binding-") as temporary:
        root = Path(temporary)
        for version in ("before", "after"):
            tools = root / version / "tools"
            tools.mkdir(parents=True)
            (tools / "verify_pairing_fixture.py").write_bytes(sources[version + "_verify"])
            (tools / "keccak256.py").write_bytes(sources["keccak"])
        for name, expected in scenarios:
            directory = root / "fixtures" / name
            directory.mkdir(parents=True)
            fixture = json.loads(sources["fixture"])
            charge = fixture["tamga_observed"]["charge_record"]["value"]
            input_bytes = sources["input"]
            if name == "stale_record_hash":
                charge["fee_sim"] = 9.9e-9
                fixture["tamga_observed"]["receiptHash"]["value"] = record_hash(charge)
            elif name in ("stale_input_binding", "consistent_rewrite"):
                input_bytes = b'{"demo": "tampered", "v": 2}\n'
                commitment = hashlib.sha256(input_bytes).hexdigest()
                fixture["input_commitment"]["input_sha256"]["value"] = commitment
                if name == "consistent_rewrite":
                    charge["input_sha256"] = commitment
                    charge["h"] = record_hash(charge)
                    fixture["tamga_observed"]["receiptHash"]["value"] = charge["h"]
            # Preserve the exact untouched fixture bytes; mutate only selected cases.
            fixture_bytes = sources["fixture"] if name == "untouched" else json.dumps(fixture).encode()
            (directory / "pairing-fixture.json").write_bytes(fixture_bytes)
            (directory / "input.json").write_bytes(input_bytes)
            (directory / "delivery.stdout").write_bytes(sources["delivery"])
            for version in ("before", "after"):
                command = [sys.executable, "-I", "-S", "-B",
                           str(root / version / "tools" / "verify_pairing_fixture.py"), str(directory)]
                process = subprocess.run(command, capture_output=True, text=True, timeout=10,
                                         env={"PATH": os.defpath, "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"})
                outcome = json.loads(process.stdout)
                wanted_ok, wanted_where = expected[version]
                expected_output = expected_payload(charge, sources["delivery"], wanted_ok, wanted_where)
                matches = matches_expected_result(outcome, expected_output, process.returncode, process.stderr)
                runs.append({"scenario": name, "version": version,
                             "revision": BASE if version == "before" else FIXED,
                             "exit_code": process.returncode, "output": outcome,
                             "stderr": process.stderr, "expected_ok": wanted_ok,
                             "expected_where": wanted_where, "expected_output": expected_output,
                             "matches_expected": matches})
                print(f"{name:22} {version:6} ok={outcome.get('ok')} where={outcome.get('where')} matched={matches}")
    reproducer_bytes = Path(__file__).read_bytes()
    report = {"repository": "goun7/tamga-protocol", "base_sha": BASE, "fixed_sha": FIXED,
              "python": platform.python_version(), "scope": "historical fixture-verifier comparison",
              "cgqa_engine": "NOT_RUN", "upstream_full_suite": "NOT_RUN",
              "reproducer": {"git_blob_sha1": git_blob(reproducer_bytes),
                             "sha256": hashlib.sha256(reproducer_bytes).hexdigest(),
                             "bytes": len(reproducer_bytes)},
              "sources": identities, "runs": runs,
              "summary": {"invocations": len(runs), "matched": sum(r["matches_expected"] for r in runs)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Matched {report['summary']['matched']}/{len(runs)} expected outcomes.")
    return 0 if all(r["matches_expected"] for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
