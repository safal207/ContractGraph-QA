#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SYSTEM_CASE = "AEGISORA-EXECUTION-EVIDENCE-001"
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
    require(report.get("status") == "OBSERVED", "subject probe did not produce OBSERVED")
    require(
        report.get("upstream", {}).get("repository") == "aegisora-ai/aegisora",
        "wrong upstream repository",
    )
    require(
        report.get("upstream", {}).get("commit") == UPSTREAM_COMMIT,
        "wrong upstream commit",
    )
    require(
        report.get("usage_bridge", {}).get("configured") is True,
        "EnterpriseUsageRuntimeBridge was not configured",
    )

    cases = report.get("cases", {})
    blocked = cases.get("blocked_rebind", {})
    with_usage = cases.get("success_with_usage", {})
    without_usage = cases.get("success_without_usage", {})
    failed = cases.get("provider_failure", {})

    require(
        blocked.get("decision", {}).get("decision") == "BLOCK",
        "rebound provider did not BLOCK",
    )
    require(
        "binding mismatch" in str(blocked.get("error", "")).lower(),
        "rebound provider was not rejected by binding mismatch",
    )
    require(blocked.get("approved_provider_calls") == 0, "blocked rebind called approved provider")
    require(blocked.get("rebound_provider_calls") == 0, "blocked rebind called rebound provider")
    require(blocked.get("usage_events_after_case") == 0, "blocked rebind emitted usage event")

    decision = with_usage.get("decision", {})
    event = with_usage.get("usage_event", {})
    correlations = with_usage.get("correlation_match", {})

    require(decision.get("decision") == "ALLOW", "usage-bearing success was not ALLOW")
    require(with_usage.get("provider_calls") == 1, "usage-bearing provider did not execute once")
    require(event.get("event_type") == "provider.execution", "wrong post-execution event type")
    require(event.get("outcome") == "executed", "successful execution event outcome drift")
    require(event.get("provider_id") == "openai", "post-execution provider identity drift")
    require(event.get("model_id") == "test-model", "post-execution model identity drift")
    require(
        event.get("workspace_id") == "workspace-execution-evidence",
        "post-execution workspace identity drift",
    )
    require(event.get("usage", {}).get("totalTokens") == 8, "usage token propagation drift")
    require(
        with_usage.get("response_provider") == "spoofed-response-provider",
        "provider-response spoof control missing",
    )
    require(
        with_usage.get("response_model") == "spoofed-response-model",
        "model-response spoof control missing",
    )
    require(
        event.get("provider_id") != with_usage.get("response_provider"),
        "usage event trusted provider response identity",
    )
    require(
        event.get("model_id") != with_usage.get("response_model"),
        "usage event trusted provider response model identity",
    )
    for field in ("trace_id", "decision_id", "execution_id", "evidence_id"):
        require(correlations.get(field) is True, f"correlation mismatch for {field}")

    require(
        without_usage.get("decision", {}).get("decision") == "ALLOW",
        "no-usage success was not ALLOW",
    )
    require(without_usage.get("provider_calls") == 1, "no-usage provider did not execute")
    require(
        without_usage.get("usage_events_before") == without_usage.get("usage_events_after"),
        "success without usage emitted a post-execution usage event",
    )

    require(
        failed.get("decision", {}).get("decision") == "ALLOW",
        "throwing provider was not admitted by pre-execution gate",
    )
    require(failed.get("provider_calls") == 1, "throwing provider was not invoked")
    require(
        "synthetic-provider-failure" in str(failed.get("error", "")),
        "throwing provider failure did not propagate",
    )
    require(
        failed.get("usage_events_before") == failed.get("usage_events_after"),
        "provider failure emitted a failed post-execution usage event",
    )

    findings = report.get("findings", {})
    require(
        findings.get("usage_bearing_success_has_correlated_post_execution_event") is True,
        "usage-bearing correlation finding missing",
    )
    require(
        findings.get("canonical_provider_and_model_ignore_response_identity_spoof") is True,
        "canonical provider/model finding missing",
    )
    require(
        findings.get("success_without_usage_has_no_post_execution_usage_event") is True,
        "no-usage evidence-gap finding missing",
    )
    require(
        findings.get("provider_failure_has_no_failed_post_execution_usage_event") is True,
        "failure evidence-gap finding missing",
    )

    digest = hashlib.sha256(raw).hexdigest()
    verified = {
        "system_case": SYSTEM_CASE,
        "status": "PASS",
        "finding": "PARTIAL_POST_EXECUTION_COVERAGE",
        "upstream_commit": UPSTREAM_COMMIT,
        "subject_report_sha256": digest,
        "verified": [
            "usage-bearing successful provider execution emits one correlated provider.execution event",
            "post-execution event carries the same trace/decision/execution/evidence identities as the ALLOW decision",
            "post-execution provider/model identities come from the gateway, not spoofable ProviderResponse fields",
            "blocked provider rebinding emits no post-execution usage event",
            "successful provider execution without response.usage emits no post-execution usage event",
            "provider invocation that throws emits no outcome=failed post-execution usage event",
        ],
        "interpretation":
            "EnterpriseUsageRuntimeBridge can bind a usage-bearing successful provider execution back to the authorization decision, but it is not a general execution receipt for all provider outcomes in the tested gateway path.",
        "claim_ceiling":
            "One pinned Aegisora provider path with inert local providers; no production-provider, recipient, settlement, distributed-durability, or universal runtime claim.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verified, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verified, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
