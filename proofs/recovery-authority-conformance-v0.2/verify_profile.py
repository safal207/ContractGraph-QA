from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROFILE = Path(__file__).with_name("profile.json")


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if p.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def source(src: dict[str, Any]) -> dict[str, Any]:
    ref = f"{src['merge_commit']}:{src['path']}"
    actual = git("rev-parse", ref)
    assert actual == src["blob_sha1"], (ref, actual, src["blob_sha1"])
    data = json.loads(git("show", ref))
    assert isinstance(data, dict)
    return data


def check_contract(r: dict[str, Any]) -> None:
    assert r["schema"] == "contractgraph.identity-authority-boundary.v0.1"
    assert r["result"] == "PASS"
    assert r["identity_continuity"] is True
    assert r["authority_non_continuity"] is True
    assert r["mutant_discrimination"]["detected_mutants"] == 2


def check_crewai(r: dict[str, Any]) -> None:
    assert r["schema"] == "contractgraph.crewai-identity-authority-adapter.v0.1"
    assert r["result"] == "PASS"
    assert r["runtime"] == {"name": "crewai", "version": "1.15.21"}
    g = r["guarded"]
    assert g["tool_attempts"] == 2
    assert g["effect_count"] == 1
    assert g["guard_decisions"] == ["dispatch", "return_prior"]
    assert g["permit_consumed"] is True


def check_langgraph_confirmed(r: dict[str, Any]) -> None:
    assert r["schema"] == "contractgraph.langgraph-b1-identity-authority.v0.1"
    assert r["all_pass"] is True
    assert r["runtime"] == {"langgraph": "1.2.11", "langgraph_checkpoint_sqlite": "3.1.1"}
    g = r["arms"]["guarded"]["after_recovery"]
    assert g["effect_count"] == 1
    assert g["decisions"] == ["dispatch", "return_prior"]
    assert len(set(g["action_ids"])) == 1
    assert g["permit"]["consume_count"] == 1


def check_langgraph_visibility(r: dict[str, Any]) -> None:
    assert r["schema"] == "contractgraph.langgraph-b1-receipt-visibility.v0.2"
    assert r["all_pass"] is True
    delayed = r["cases"]["delayed"]
    assert delayed["after_first_recovery"]["decisions"] == ["dispatch", "fail_closed_unknown"]
    assert delayed["after_first_recovery"]["effect_count"] == 1
    assert delayed["after_second_recovery"]["decisions"] == ["dispatch", "fail_closed_unknown", "return_prior"]
    assert delayed["after_second_recovery"]["effect_count"] == 1
    mismatch = r["cases"]["mismatch"]["after_first_recovery"]
    assert mismatch["decisions"] == ["dispatch", "fail_closed_mismatch"]
    assert mismatch["effect_count"] == 1


def check_autogen(r: dict[str, Any]) -> None:
    assert r["schema"] == "contractgraph.autogen-runtime-authority.v0.1"
    assert r["all_pass"] is True
    assert r["runtime"] == {"autogen_core": "0.7.5"}
    assert r["upstream"]["commit"] == "027ecf0a379bcc1d09956d46d12d44a3ad9cee14"
    assert r["upstream"]["state_boundary"] == "SingleThreadedAgentRuntime.save_state/load_state"

    c = r["cases"]["confirmed"]
    assert c["passed"] is True
    assert c["after_first_recovery"]["decisions"] == ["dispatch", "return_prior"]
    assert c["after_first_recovery"]["effect_count"] == 1

    u = r["cases"]["unknown"]
    assert u["passed"] is True
    assert u["after_first_recovery"]["decisions"] == ["dispatch", "fail_closed_unknown"]
    assert u["after_first_recovery"]["effect_count"] == 1
    assert u["after_second_recovery"]["decisions"] == ["dispatch", "fail_closed_unknown", "return_prior"]
    assert u["after_second_recovery"]["effect_count"] == 1

    m = r["cases"]["mismatch"]
    assert m["passed"] is True
    assert m["after_first_recovery"]["decisions"] == ["dispatch", "fail_closed_mismatch"]
    assert m["after_first_recovery"]["effect_count"] == 1

    n = r["cases"]["not_executed"]
    assert n["passed"] is True
    assert n["before_recovery"]["effect_count"] == 0
    assert n["before_recovery"]["outcome"] == "NOT_EXECUTED"
    assert n["after_first_recovery"]["decisions"] == ["dispatch", "fresh_authorization_required", "dispatch"]
    assert n["after_first_recovery"]["effect_count"] == 1
    permits = n["after_first_recovery"]["permits"]
    assert [x["generation"] for x in permits] == [1, 2]
    assert [x["consume_count"] for x in permits] == [1, 1]
    assert permits[0]["permit_id"] != permits[1]["permit_id"]

    for case in r["cases"].values():
        s = case["saved_agent_state"]
        assert set(s) == {"schema", "action_id", "intent_hash", "target"}
        assert case["subject"]["permit_persisted"] is False


def check_profile(p: dict[str, Any]) -> None:
    assert p["schema"] == "contractgraph.recovery-authority-conformance.v0.2"
    assert p["aggregate"]["kind"] == "vector"
    assert p["aggregate"]["scalar_verdict"] is None
    required = {
        "CONFIRMED": "return_prior",
        "UNKNOWN": "fail_closed_unknown",
        "MISMATCH": "fail_closed_mismatch",
        "NOT_EXECUTED": "fresh_authorization_required",
    }
    for row, decision in required.items():
        assert p["normative_rows"][row]["required_decision"] == decision

    crew = p["runtimes"]["crewai-1.15.21"]["rows"]
    assert crew["CONFIRMED"]["status"] == "PASS"
    assert crew["CONFIRMED"]["observed_decision"] == "return_prior"
    for row in ("UNKNOWN", "MISMATCH", "NOT_EXECUTED"):
        assert crew[row]["status"] == "UNTESTED" and "evidence" not in crew[row]

    lg = p["runtimes"]["langgraph-1.2.11-sqlite-3.1.1"]["rows"]
    assert lg["CONFIRMED"]["status"] == "PASS" and lg["CONFIRMED"]["observed_decision"] == "return_prior"
    assert lg["UNKNOWN"]["status"] == "PASS" and lg["UNKNOWN"]["observed_decision"] == "fail_closed_unknown"
    assert lg["MISMATCH"]["status"] == "PASS" and lg["MISMATCH"]["observed_decision"] == "fail_closed_mismatch"
    assert lg["NOT_EXECUTED"]["status"] == "UNTESTED" and "evidence" not in lg["NOT_EXECUTED"]

    ag = p["runtimes"]["autogen-core-0.7.5"]["rows"]
    for row, decision in required.items():
        assert ag[row] == {"status": "PASS", "evidence": "autogen_authority", "observed_decision": decision}

    allowed = {"PASS", "FAIL", "UNTESTED", "UNSUPPORTED"}
    for runtime in p["runtimes"].values():
        for row in runtime["rows"].values():
            assert row["status"] in allowed
            if row["status"] == "PASS":
                assert "evidence" in row


def main() -> int:
    p = json.loads(PROFILE.read_text())
    check_profile(p)
    reports = {name: source(src) for name, src in p["sources"].items()}
    check_contract(reports["contract"])
    check_crewai(reports["crewai_confirmed"])
    check_langgraph_confirmed(reports["langgraph_confirmed"])
    check_langgraph_visibility(reports["langgraph_visibility"])
    check_autogen(reports["autogen_authority"])

    counts = {"PASS": 0, "FAIL": 0, "UNTESTED": 0, "UNSUPPORTED": 0}
    for runtime in p["runtimes"].values():
        for row in runtime["rows"].values():
            counts[row["status"]] += 1
    expected = {"PASS": 8, "FAIL": 0, "UNTESTED": 4, "UNSUPPORTED": 0}
    assert counts == expected, (counts, expected)
    print(json.dumps({
        "schema": p["schema"],
        "profile_verified": True,
        "source_blobs_verified": len(reports),
        "runtime_rows": counts,
        "scalar_verdict": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
