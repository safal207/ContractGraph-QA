from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = Path(__file__).with_name("profile.json")


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def load_immutable_source(source: dict[str, Any]) -> dict[str, Any]:
    commit = str(source["merge_commit"])
    path = str(source["path"])
    expected_blob = str(source["blob_sha1"])
    object_ref = f"{commit}:{path}"

    actual_blob = git("rev-parse", object_ref)
    if actual_blob != expected_blob:
        raise AssertionError(
            f"blob mismatch for {object_ref}: expected={expected_blob} actual={actual_blob}"
        )

    raw = git("show", object_ref)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise AssertionError(f"source {object_ref} is not a JSON object")
    return parsed


def by_case(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = report.get("cases")
    if not isinstance(rows, list):
        raise AssertionError("framework-neutral report cases must be a list")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AssertionError("framework-neutral case is not an object")
        out[str(row["case"])] = row
    return out


def assert_contract(report: dict[str, Any]) -> None:
    assert report["schema"] == "contractgraph.identity-authority-boundary.v0.1"
    assert report["result"] == "PASS"
    assert report["passed_cases"] == 6
    assert report["total_cases"] == 6
    assert report["identity_continuity"] is True
    assert report["authority_non_continuity"] is True
    assert report["mutant_discrimination"]["detected_mutants"] == 2

    cases = by_case(report)
    assert cases["recovery-confirmed"]["decision"] == "return_prior"
    assert cases["recovery-confirmed"]["dispatch_count_delta"] == 0
    assert cases["recovery-unknown"]["decision"] == "fail_closed"
    assert cases["recovery-unknown"]["dispatch_count_delta"] == 0
    assert cases["recovery-not-executed"]["decision"] == "fresh_authorization"
    assert cases["recovery-not-executed"]["dispatch_count_delta"] == 1
    assert cases["replay-old-permit"]["decision"] == "reject_reused_permit"
    assert cases["replay-old-permit"]["dispatch_count_delta"] == 0
    assert cases["target-mismatch"]["decision"] == "reject_target_mismatch"
    assert cases["target-mismatch"]["dispatch_count_delta"] == 0


def assert_crewai(report: dict[str, Any]) -> None:
    assert report["schema"] == "contractgraph.crewai-identity-authority-adapter.v0.1"
    assert report["result"] == "PASS"
    assert report["runtime"] == {"name": "crewai", "version": "1.15.21"}
    assert report["same_action_identity_across_ab"] is True

    baseline = report["baseline"]
    guarded = report["guarded"]
    assert baseline["passed"] is True
    assert baseline["tool_attempts"] == 2
    assert baseline["effect_count"] == 2
    assert baseline["verdict"] == "DUPLICATED"

    assert guarded["passed"] is True
    assert guarded["tool_attempts"] == 2
    assert guarded["effect_count"] == 1
    assert guarded["guard_decisions"] == ["dispatch", "return_prior"]
    assert guarded["permit_consumed"] is True
    assert guarded["verdict"] == "RECONCILED_NO_DUPLICATE"


def assert_langgraph_confirmed(report: dict[str, Any]) -> None:
    assert report["schema"] == "contractgraph.langgraph-b1-identity-authority.v0.1"
    assert report["all_pass"] is True
    assert report["runtime"]["langgraph"] == "1.2.11"
    assert report["runtime"]["langgraph_checkpoint_sqlite"] == "3.1.1"

    baseline = report["arms"]["baseline"]
    guarded = report["arms"]["guarded"]
    assert baseline["passed"] is True
    assert baseline["after_recovery"]["effect_count"] == 2
    assert baseline["after_recovery"]["decisions"] == ["dispatch", "dispatch"]

    after = guarded["after_recovery"]
    assert guarded["passed"] is True
    assert after["node_entries"] == 2
    assert after["effect_count"] == 1
    assert after["decisions"] == ["dispatch", "return_prior"]
    assert len(set(after["action_ids"])) == 1
    assert after["permit"]["consumed"] is True
    assert after["permit"]["consume_count"] == 1
    assert guarded["verdict"] == "RECONCILED_NO_DUPLICATE"


def assert_langgraph_visibility(report: dict[str, Any]) -> None:
    assert report["schema"] == "contractgraph.langgraph-b1-receipt-visibility.v0.2"
    assert report["all_pass"] is True
    assert report["runtime"]["langgraph"] == "1.2.11"
    assert report["runtime"]["langgraph_checkpoint_sqlite"] == "3.1.1"

    confirmed = report["cases"]["confirmed"]
    confirmed_after = confirmed["after_first_recovery"]
    assert confirmed["passed"] is True
    assert confirmed_after["decisions"] == ["dispatch", "return_prior"]
    assert confirmed_after["effect_count"] == 1
    assert confirmed_after["permit"]["consume_count"] == 1

    delayed = report["cases"]["delayed"]
    delayed_first = delayed["after_first_recovery"]
    delayed_second = delayed["after_second_recovery"]
    assert delayed["passed"] is True
    assert delayed["first_recovery_status"] == "BLOCKED_UNKNOWN"
    assert delayed_first["decisions"] == ["dispatch", "fail_closed_unknown"]
    assert delayed_first["effect_count"] == 1
    assert delayed_first["permit"]["consume_count"] == 1
    assert delayed_first["receipt"]["visible"] is False
    assert delayed["second_recovery_status"] == "COMPLETED"
    assert delayed_second["decisions"] == [
        "dispatch",
        "fail_closed_unknown",
        "return_prior",
    ]
    assert delayed_second["effect_count"] == 1
    assert delayed_second["permit"]["consume_count"] == 1
    assert delayed_second["receipt"]["visible"] is True
    assert len(set(delayed_second["action_ids"])) == 1

    mismatch = report["cases"]["mismatch"]
    mismatch_after = mismatch["after_first_recovery"]
    assert mismatch["passed"] is True
    assert mismatch["first_recovery_status"] == "BLOCKED_MISMATCH"
    assert mismatch_after["decisions"] == ["dispatch", "fail_closed_mismatch"]
    assert mismatch_after["effect_count"] == 1
    assert mismatch_after["permit"]["consume_count"] == 1


def assert_profile(profile: dict[str, Any]) -> None:
    assert profile["schema"] == "contractgraph.recovery-authority-conformance.v0.1"
    assert profile["aggregate"]["kind"] == "vector"
    assert profile["aggregate"]["scalar_verdict"] is None

    expected_normative = {
        "CONFIRMED": "return_prior",
        "UNKNOWN": "fail_closed_unknown",
        "MISMATCH": "fail_closed_mismatch",
        "NOT_EXECUTED": "fresh_authorization_required",
    }
    for row, decision in expected_normative.items():
        assert profile["normative_rows"][row]["required_decision"] == decision

    crewai = profile["runtimes"]["crewai-1.15.21"]["rows"]
    assert crewai["CONFIRMED"] == {
        "evidence": "crewai_confirmed",
        "observed_decision": "return_prior",
        "status": "PASS",
    }
    for row in ("UNKNOWN", "MISMATCH", "NOT_EXECUTED"):
        assert crewai[row]["status"] == "UNTESTED"
        assert "evidence" not in crewai[row]

    langgraph = profile["runtimes"]["langgraph-1.2.11-sqlite-3.1.1"]["rows"]
    assert langgraph["CONFIRMED"] == {
        "evidence": "langgraph_confirmed",
        "observed_decision": "return_prior",
        "status": "PASS",
    }
    assert langgraph["UNKNOWN"] == {
        "evidence": "langgraph_visibility",
        "observed_decision": "fail_closed_unknown",
        "status": "PASS",
    }
    assert langgraph["MISMATCH"] == {
        "evidence": "langgraph_visibility",
        "observed_decision": "fail_closed_mismatch",
        "status": "PASS",
    }
    assert langgraph["NOT_EXECUTED"]["status"] == "UNTESTED"
    assert "evidence" not in langgraph["NOT_EXECUTED"]

    allowed = {"PASS", "FAIL", "UNTESTED", "UNSUPPORTED"}
    for runtime in profile["runtimes"].values():
        for row in runtime["rows"].values():
            assert row["status"] in allowed
            if row["status"] == "PASS":
                assert row["observed_decision"] in expected_normative.values()
                assert "evidence" in row


def main() -> int:
    profile = json.loads(PROFILE_PATH.read_text())
    assert isinstance(profile, dict)
    assert_profile(profile)

    sources = profile["sources"]
    contract = load_immutable_source(sources["contract"])
    crewai = load_immutable_source(sources["crewai_confirmed"])
    langgraph_confirmed = load_immutable_source(sources["langgraph_confirmed"])
    langgraph_visibility = load_immutable_source(sources["langgraph_visibility"])

    assert_contract(contract)
    assert_crewai(crewai)
    assert_langgraph_confirmed(langgraph_confirmed)
    assert_langgraph_visibility(langgraph_visibility)

    counts = {"PASS": 0, "FAIL": 0, "UNTESTED": 0, "UNSUPPORTED": 0}
    for runtime in profile["runtimes"].values():
        for row in runtime["rows"].values():
            counts[row["status"]] += 1

    result = {
        "schema": profile["schema"],
        "profile_verified": True,
        "source_blobs_verified": len(sources),
        "runtime_rows": counts,
        "scalar_verdict": None,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
