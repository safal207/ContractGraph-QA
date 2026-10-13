#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SYSTEM_CASE = "AEGISORA-PROVIDER-BINDING-001"
UPSTREAM_COMMIT = "2bac618215671f6f0ac8ebddf169830d4fc0f9b3"


def fail(message: str) -> None:
    raise SystemExit(f"{SYSTEM_CASE} FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.report.read_bytes()
    report = json.loads(raw)

    require(report.get("system_case") == SYSTEM_CASE, "wrong system_case")
    require(report.get("status") == "OBSERVED", "subject probe did not produce OBSERVED report")
    require(
        report.get("upstream", {}).get("repository") == "aegisora-ai/aegisora",
        "wrong upstream repository",
    )
    require(
        report.get("upstream", {}).get("commit") == UPSTREAM_COMMIT,
        "wrong upstream commit",
    )

    boundary = report.get("boundary", {})
    require(boundary.get("approved_provider") == "openai", "approved provider drift")
    require(boundary.get("rebound_provider") == "anthropic", "rebound provider drift")
    require(boundary.get("action") == "provider.generate", "action drift")

    phases = report.get("phases", {})
    escalation = phases.get("escalation", {})
    rebind = phases.get("provider_rebind", {})
    exact = phases.get("exact_resume", {})
    replay = phases.get("replay", {})

    require(escalation.get("decision") == "ESCALATE", "initial request did not ESCALATE")
    require(escalation.get("approval_status") == "pending", "initial approval not pending")
    require(escalation.get("openai_calls") == 0, "ESCALATE called approved provider")
    require(escalation.get("anthropic_calls") == 0, "ESCALATE called alternate provider")

    require(rebind.get("decision") == "BLOCK", "provider rebind did not BLOCK")
    require(
        "binding mismatch" in str(rebind.get("error", "")).lower(),
        "provider rebind was not rejected by binding mismatch",
    )
    require(
        rebind.get("approval_status") == "approved",
        "failed rebind consumed or mutated valid approval",
    )
    require(rebind.get("openai_calls") == 0, "rebind called approved provider")
    require(rebind.get("anthropic_calls") == 0, "rebind reached alternate provider")

    require(exact.get("decision") == "ALLOW", "exact approved resume did not ALLOW")
    require(exact.get("approval_status") == "consumed", "exact resume did not consume approval")
    require(exact.get("output") == "openai:executed", "exact resume output drift")
    require(exact.get("openai_calls") == 1, "exact resume did not call openai exactly once")
    require(exact.get("anthropic_calls") == 0, "exact resume called alternate provider")

    require(replay.get("decision") == "BLOCK", "consumed approval replay did not BLOCK")
    require(replay.get("approval_status") == "consumed", "replay changed consumed status")
    require(replay.get("openai_calls") == 1, "replay produced duplicate openai effect")
    require(replay.get("anthropic_calls") == 0, "replay called alternate provider")

    invariants = report.get("observed_invariant", {})
    require(
        invariants.get("provider_rebinding_rejected_before_side_effect") is True,
        "provider rebinding invariant not observed",
    )
    require(
        invariants.get("exact_bound_provider_executes_once") is True,
        "exact-provider execution invariant not observed",
    )
    require(
        invariants.get("consumed_approval_replay_blocked") is True,
        "replay invariant not observed",
    )

    digest = hashlib.sha256(raw).hexdigest()
    verified = {
        "system_case": SYSTEM_CASE,
        "status": "PASS",
        "upstream_commit": UPSTREAM_COMMIT,
        "subject_report_sha256": digest,
        "verified": [
            "approval created for provider:openai before any provider side effect",
            "same approvalId rebound to provider:anthropic is BLOCKED",
            "rebinding produces zero openai and zero anthropic provider calls",
            "failed rebind leaves approval usable for the exact approved provider",
            "exact provider resume executes openai exactly once and consumes approval",
            "replay of consumed approval is BLOCKED without a second provider effect",
        ],
        "claim_ceiling":
            "Provider/tool identity binding only. No recipient identity, settlement/payment binding, distributed durability, or production-provider claim.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
