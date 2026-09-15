#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

PUBLICATION_COMMIT = "606893ebb353df5dab3ac68738051eb5fbb7286e"
EVIDENCE_URL = (
    "https://raw.githubusercontent.com/mstevens843/crashpoint/"
    + PUBLICATION_COMMIT
    + "/evidence/crewai_retry.json"
)
EXPECTED_SHA256 = "0d2eb2cf3c835b022298d52e807f7d0328b023d5c4d88a669af5c1965f6b56d1"
EXPECTED_BYTES = 581573
EXPECTED_RECEIPT = "cp1_a7376a114c8eeb06eb7042039a8557b00630fde0cf946788d8be9a2cdd22541d"
EXPECTED_CRASHPOINT_COMMIT = "a08ef36f435b68343befa1c39681c1b4691302af"
EXPECTED_CREWAI_COMMIT = "a8d330de00812e52356f32d32c715b86392bfd41"
EXPECTED_CREWAI_VERSION = "1.15.21"

EXPECTED = {
    "clean": {"n": 30, "effects": 1, "attempts": 1, "oracle": "EXACTLY_ONCE"},
    "pre_effect": {"n": 30, "effects": 1, "attempts": 2, "oracle": "EXACTLY_ONCE"},
    "post_effect": {"n": 30, "effects": 2, "attempts": 2, "oracle": "DUPLICATED"},
}

EXPECTED_EVENT_PATTERNS = {
    "clean": [
        ("tool_enter", 1, None),
        ("effect_ack", None, None),
        ("tool_return", None, None),
    ],
    "pre_effect": [
        ("tool_enter", 1, None),
        ("injected_failure", None, "before_effect"),
        ("tool_enter", 2, None),
        ("effect_ack", None, None),
        ("tool_return", None, None),
    ],
    "post_effect": [
        ("tool_enter", 1, None),
        ("effect_ack", None, None),
        ("injected_failure", None, "after_effect_before_tool_return"),
        ("tool_enter", 2, None),
        ("effect_ack", None, None),
        ("tool_return", None, None),
    ],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_evidence(path_arg: str | None) -> tuple[Path, bool]:
    if path_arg:
        return Path(path_arg), False

    tmp = tempfile.NamedTemporaryFile(prefix="crewai_retry_", suffix=".json", delete=False)
    tmp.close()
    urllib.request.urlretrieve(EVIDENCE_URL, tmp.name)
    return Path(tmp.name), True


def normalized_event_pattern(trial: dict) -> list[tuple[str, int | None, str | None]]:
    out = []
    for event in trial["events"]:
        if event["event"] in {"tool_enter", "effect_ack", "injected_failure", "tool_return"}:
            out.append((event["event"], event.get("run_attempt"), event.get("point")))
    return out


def fail(message: str) -> None:
    raise AssertionError(message)


def verify(path: Path) -> dict:
    if not path.exists():
        fail(f"missing evidence file: {path}")
    if path.stat().st_size != EXPECTED_BYTES:
        fail(f"unexpected evidence byte count: {path.stat().st_size}")
    actual_hash = sha256(path)
    if actual_hash != EXPECTED_SHA256:
        fail(f"evidence SHA-256 mismatch: {actual_hash}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("receipt") != EXPECTED_RECEIPT:
        fail("receipt mismatch")
    if data.get("runtime") != "crewai":
        fail("runtime mismatch")
    if data.get("k_per_case") != 30:
        fail("k_per_case mismatch")
    if data.get("prediction_registered_before_execution") is not True:
        fail("record does not assert pre-registration")

    trials = data.get("trials")
    if not isinstance(trials, list) or len(trials) != 90:
        fail(f"expected 90 trials, got {len(trials) if isinstance(trials, list) else type(trials)}")

    by_case: dict[str, list[dict]] = defaultdict(list)
    for trial in trials:
        case = trial.get("case")
        if case not in EXPECTED:
            fail(f"unknown case: {case}")
        by_case[case].append(trial)

        if trial.get("crashpoint_commit") != EXPECTED_CRASHPOINT_COMMIT:
            fail(f"{trial.get('logical_action_id')}: crashpoint commit mismatch")
        if trial.get("crewai_source_commit") != EXPECTED_CREWAI_COMMIT:
            fail(f"{trial.get('logical_action_id')}: CrewAI commit mismatch")
        if trial.get("crewai_version") != EXPECTED_CREWAI_VERSION:
            fail(f"{trial.get('logical_action_id')}: CrewAI version mismatch")
        if trial.get("observation_complete") is not True:
            fail(f"{trial.get('logical_action_id')}: incomplete observation")
        if trial.get("passed") is not True:
            fail(f"{trial.get('logical_action_id')}: producer trial flag is not PASS")
        if trial.get("same_process") is not True:
            fail(f"{trial.get('logical_action_id')}: expected same_process=true")
        if trial.get("fresh_process") is not False:
            fail(f"{trial.get('logical_action_id')}: fresh_process scope changed")
        if trial.get("external_retrigger") is not False:
            fail(f"{trial.get('logical_action_id')}: external_retrigger scope changed")
        if trial["runtime_reported_result"].get("agent_retries") != 0:
            fail(f"{trial.get('logical_action_id')}: agent-level retry appeared")

        exp = EXPECTED[case]
        if trial.get("effect_count") != exp["effects"]:
            fail(f"{trial.get('logical_action_id')}: effect_count mismatch")
        if trial["observed_result"].get("tool_attempts") != exp["attempts"]:
            fail(f"{trial.get('logical_action_id')}: tool_attempts mismatch")
        if trial.get("oracle_classification") != exp["oracle"]:
            fail(f"{trial.get('logical_action_id')}: oracle mismatch")

        pattern = normalized_event_pattern(trial)
        if pattern != EXPECTED_EVENT_PATTERNS[case]:
            fail(f"{trial.get('logical_action_id')}: unexpected event order: {pattern}")

    for case, exp in EXPECTED.items():
        if len(by_case[case]) != exp["n"]:
            fail(f"{case}: expected {exp['n']} trials, got {len(by_case[case])}")

    recomputed = {}
    for case in ("clean", "pre_effect", "post_effect"):
        rows = by_case[case]
        recomputed[case] = {
            "trials": len(rows),
            "effect_counts": dict(Counter(str(row["effect_count"]) for row in rows)),
            "tool_attempts": dict(Counter(str(row["observed_result"]["tool_attempts"]) for row in rows)),
            "oracle_classifications": dict(Counter(row["oracle_classification"] for row in rows)),
        }

    return {
        "schema": "contractgraph.external-proof-admission-verification.v0.1",
        "result": "90/90 AGREE_WITH_BOUNDED_RECORDED_CLAIM",
        "publication_commit": PUBLICATION_COMMIT,
        "evidence_sha256": actual_hash,
        "evidence_bytes": path.stat().st_size,
        "recomputed": recomputed,
        "scope": {
            "same_process": True,
            "fresh_process": False,
            "external_retrigger": False,
            "agent_retries": 0,
        },
        "claim_ceiling": (
            "Independent byte/invariant verification of the recorded receipts only; "
            "not an independent rerun of CrewAI or an attestation of the original execution environment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        help="Local crewai_retry.json. If omitted, download the immutable publication-commit copy.",
    )
    parser.add_argument("--write-report", help="Optional output path for the JSON verification report.")
    args = parser.parse_args()

    path, temporary = load_evidence(args.evidence)
    try:
        report = verify(path)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.write_report:
            Path(args.write_report).write_text(encoded, encoding="utf-8")
        sys.stdout.write(encoded)
        return 0
    finally:
        if temporary:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
