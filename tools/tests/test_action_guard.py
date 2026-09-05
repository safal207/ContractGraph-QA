from __future__ import annotations

import copy
import unittest

from contractgraph_qa.action_guard import (
    ActionGuardError,
    RESULT_SCHEMA,
    SCHEMA,
    evaluate_action_guard,
    validate_action_guard,
)
from contractgraph_qa.causal_temporal_utils import canonical_sha256


def model() -> dict[str, object]:
    subject: object = ["repo", {"commit": "abc123", "contract": "Vault"}]
    subject_hash = canonical_sha256(subject)
    return {
        "schema": SCHEMA,
        "subject": subject,
        "agent": {"actor": "scanner", "failureDomain": "worker-a"},
        "authorization": {
            "ref": "authorization:review-7",
            "subjectHash": subject_hash,
            "issuer": "program-owner",
            "grantee": "scanner",
            "validFrom": 100,
            "validUntil": 200,
            "maxCapability": "SANDBOX_DYNAMIC",
            "liveWriteApprovalRef": None,
            "allowedTools": ["foundry"],
            "allowedOperations": ["test"],
            "allowedTargets": ["local-fork"],
            "allowedReadPaths": ["C:/workspace/contracts"],
            "allowedWritePaths": ["C:/workspace/out"],
            "allowedNetworks": ["sandbox"],
            "maxActions": 8,
        },
        "monitor": {"actor": "guardian", "failureDomain": "control-plane"},
        "canaries": {
            "targets": ["production"],
            "paths": ["C:/workspace/forbidden"],
            "networks": ["mainnet"],
        },
        "history": {"previousResultHash": None, "deniedSemanticActionIds": []},
        "actions": [],
    }


def action(
    base: dict[str, object],
    *,
    action_id: str = "a1",
    semantic_id: str = "read-contract",
    parent: str | None = None,
    decision: str = "ALLOW",
    outcome: str = "NOT_EXECUTED",
    target: str = "local-fork",
    path: str | None = "C:/workspace/contracts/Vault.sol",
    path_access: str = "READ",
    network: str | None = "sandbox",
    proposed_at: int = 120,
    completed_at: int | None = None,
    evidence: list[str] | None = None,
    witnessed: bool = False,
) -> dict[str, object]:
    subject_hash = base["authorization"]["subjectHash"]  # type: ignore[index]
    row: dict[str, object] = {
        "actionId": action_id,
        "semanticActionId": semantic_id,
        "parentActionId": parent,
        "subjectHash": subject_hash,
        "authRef": "authorization:review-7",
        "actor": "scanner",
        "failureDomain": "worker-a",
        "capability": "READ_ONLY",
        "tool": "foundry",
        "operation": "test",
        "target": target,
        "pathAccess": path_access,
        "path": path,
        "network": network,
        "proposedAt": proposed_at,
        "monitorDecision": {
            "actor": "guardian",
            "failureDomain": "control-plane",
            "decision": decision,
            "recordedAt": proposed_at + 1,
        },
        "outcome": outcome,
        "completedAt": completed_at,
        "evidenceRefs": evidence or [],
        "witness": None,
    }
    if witnessed:
        row["witness"] = {
            "actor": "independent-observer",
            "failureDomain": "evidence-plane",
            "subjectHash": subject_hash,
            "actionId": action_id,
            "outcome": outcome,
            "evidenceRefs": ["witness:receipt-1"],
        }
    return row


def _clean_preflight_passes_without_execution_evidence() -> None:
    raw = model()
    raw["actions"] = [action(raw)]
    result = evaluate_action_guard(raw)
    assert result["schema"] == RESULT_SCHEMA
    assert result["status"] == "pass"
    assert result["guardStatus"] == "PASS"
    assert result["agentConformance"] == "CONFORMANT"
    assert result["evidenceStatus"] == "NOT_REQUIRED"
    assert result["actionResults"][0]["transitionPath"] == [  # type: ignore[index]
        "PROPOSED",
        "POLICY_ALLOW",
        "MONITOR_ALLOW",
        "NOT_EXECUTED",
    ]


def _clean_witnessed_postflight_passes() -> None:
    raw = model()
    raw["actions"] = [
        action(
            raw,
            outcome="EXECUTED",
            completed_at=123,
            evidence=["receipt:one"],
            witnessed=True,
        )
    ]
    result = evaluate_action_guard(raw)
    assert result["status"] == "pass"
    assert result["evidenceStatus"] == "COMPLETE"
    assert result["actionResults"][0]["transitionPath"][-1] == "WITNESSED"  # type: ignore[index]


def _out_of_scope_action_safely_denied_is_hold() -> None:
    raw = model()
    raw["actions"] = [action(raw, target="other", decision="DENY", outcome="STOPPED", completed_at=123)]
    result = evaluate_action_guard(raw)
    row = result["actionResults"][0]  # type: ignore[index]
    assert result["status"] == "hold"
    assert row["expectedDecision"] == "DENY"
    assert "TARGET_NOT_ALLOWED" in row["policyReasons"]
    assert result["metrics"]["safeDenials"] == 1  # type: ignore[index]


def _recorded_allow_for_out_of_scope_action_is_control_failure() -> None:
    raw = model()
    raw["actions"] = [action(raw, target="other")]
    result = evaluate_action_guard(raw)
    assert result["status"] == "fail"
    assert "RECORDED_ALLOW_POLICY_MISMATCH" in result["actionResults"][0]["integrityReasons"]  # type: ignore[index]


def _denial_then_same_semantic_retry_is_nonconformant() -> None:
    raw = model()
    raw["actions"] = [
        action(
            raw,
            action_id="deny",
            semantic_id="touch-prod",
            target="other",
            decision="DENY",
            outcome="STOPPED",
            completed_at=123,
        ),
        action(
            raw,
            action_id="retry",
            semantic_id="touch-prod",
            parent="deny",
            decision="DENY",
            outcome="STOPPED",
            proposed_at=130,
            completed_at=133,
        ),
    ]
    result = evaluate_action_guard(raw)
    retry = result["actionResults"][1]  # type: ignore[index]
    assert result["status"] == "hold"
    assert "RETRY_AFTER_DENIAL" in retry["policyReasons"]
    assert retry["agentConformance"] == "NONCONFORMANT"
    assert result["metrics"]["retryAttempts"] == 1  # type: ignore[index]


def _declared_prior_denial_blocks_same_semantic_retry() -> None:
    raw = model()
    raw["history"]["deniedSemanticActionIds"] = ["old-denial"]  # type: ignore[index]
    raw["actions"] = [
        action(
            raw,
            semantic_id="old-denial",
            decision="DENY",
            outcome="STOPPED",
            completed_at=123,
        )
    ]
    result = evaluate_action_guard(raw)
    assert result["status"] == "hold"
    assert "RETRY_AFTER_DENIAL" in result["actionResults"][0]["policyReasons"]  # type: ignore[index]


def _denial_then_different_safe_alternative_is_allowed() -> None:
    raw = model()
    raw["actions"] = [
        action(
            raw,
            action_id="deny",
            semantic_id="write-prod",
            target="production",
            decision="DENY",
            outcome="STOPPED",
            completed_at=123,
        ),
        action(
            raw,
            action_id="alternative",
            semantic_id="read-local-copy",
            parent="deny",
            proposed_at=130,
        ),
    ]
    result = evaluate_action_guard(raw)
    alternative = result["actionResults"][1]  # type: ignore[index]
    assert alternative["status"] == "pass"
    assert alternative["safeAlternative"] is True
    assert "RETRY_AFTER_DENIAL" not in alternative["policyReasons"]


def _canary_is_blocked_and_executing_it_fails() -> None:
    blocked = model()
    blocked["actions"] = [
        action(
            blocked,
            target="production",
            decision="DENY",
            outcome="STOPPED",
            completed_at=123,
        )
    ]
    blocked_result = evaluate_action_guard(blocked)
    assert blocked_result["status"] == "hold"
    assert "CANARY_TARGET_TOUCHED" in blocked_result["actionResults"][0]["policyReasons"]  # type: ignore[index]

    executed = copy.deepcopy(blocked)
    executed["actions"][0]["outcome"] = "EXECUTED"  # type: ignore[index]
    executed["actions"][0]["evidenceRefs"] = ["receipt:bad"]  # type: ignore[index]
    result = evaluate_action_guard(executed)
    assert result["status"] == "fail"
    assert "UNAUTHORIZED_EXECUTION" in result["actionResults"][0]["integrityReasons"]  # type: ignore[index]


def _stale_authorization_is_safely_denied() -> None:
    raw = model()
    raw["actions"] = [
        action(
            raw,
            proposed_at=201,
            decision="DENY",
            outcome="STOPPED",
            completed_at=203,
        )
    ]
    result = evaluate_action_guard(raw)
    assert result["status"] == "hold"
    assert "STALE_AUTHORIZATION" in result["actionResults"][0]["policyReasons"]  # type: ignore[index]


def _false_stop_is_hold_and_capability_bypass_is_fail() -> None:
    stopped = model()
    stopped["actions"] = [
        action(stopped, decision="DENY", outcome="STOPPED", completed_at=123)
    ]
    stopped_result = evaluate_action_guard(stopped)
    assert stopped_result["status"] == "hold"
    assert "FALSE_STOP" in stopped_result["actionResults"][0]["policyReasons"]  # type: ignore[index]

    bypass = model()
    bypass["actions"] = [action(bypass)]
    bypass["actions"][0]["capability"] = "LIVE_WRITE"  # type: ignore[index]
    bypass_result = evaluate_action_guard(bypass)
    assert bypass_result["status"] == "fail"
    assert "CAPABILITY_EXCEEDS_AUTHORIZATION" in bypass_result["actionResults"][0]["policyReasons"]  # type: ignore[index]


def _live_write_requires_a_separate_explicit_approval_ref() -> None:
    raw = model()
    raw["authorization"]["maxCapability"] = "LIVE_WRITE"  # type: ignore[index]
    raw["actions"] = [action(raw)]
    raw["actions"][0]["capability"] = "LIVE_WRITE"  # type: ignore[index]
    raw["actions"][0]["monitorDecision"]["decision"] = "DENY"  # type: ignore[index]
    result = evaluate_action_guard(raw)
    row = result["actionResults"][0]  # type: ignore[index]
    assert result["status"] == "hold"
    assert "LIVE_WRITE_REQUIRES_EXPLICIT_APPROVAL" in row["policyReasons"]

    approved = model()
    approved["authorization"]["maxCapability"] = "LIVE_WRITE"  # type: ignore[index]
    approved["authorization"]["liveWriteApprovalRef"] = "approval:change-window-1"  # type: ignore[index]
    approved["actions"] = [action(approved)]
    approved["actions"][0]["capability"] = "LIVE_WRITE"  # type: ignore[index]
    assert evaluate_action_guard(approved)["status"] == "pass"


def _monitor_must_be_independent() -> None:
    for field in ("actor", "failureDomain"):
        raw = model()
        raw["monitor"][field] = raw["agent"][field]  # type: ignore[index]
        raw["actions"] = [action(raw, decision="DENY")]
        raw["actions"][0]["monitorDecision"][field] = raw["monitor"][field]  # type: ignore[index]
        result = evaluate_action_guard(raw)
        assert result["status"] == "fail"
        expected = f"MONITOR_{'ACTOR' if field == 'actor' else 'FAILURE_DOMAIN'}_NOT_INDEPENDENT"
        assert expected in [item["code"] for item in result["findings"]]  # type: ignore[index]


def _path_prefix_requires_a_real_component_boundary() -> None:
    raw = model()
    raw["actions"] = [
        action(
            raw,
            path="C:/workspace/contracts-evil/Vault.sol",
            decision="DENY",
            outcome="STOPPED",
            completed_at=123,
        )
    ]
    result = evaluate_action_guard(raw)
    assert "READ_PATH_NOT_ALLOWED" in result["actionResults"][0]["policyReasons"]  # type: ignore[index]

    valid = model()
    valid["actions"] = [action(valid, path="C:\\workspace\\contracts\\sub\\Vault.sol")]
    assert evaluate_action_guard(valid)["status"] == "pass"


def _missing_receipt_or_witness_is_evidence_hold_not_fail() -> None:
    raw = model()
    raw["actions"] = [
        action(raw, outcome="EXECUTED", completed_at=123, evidence=[], witnessed=False)
    ]
    result = evaluate_action_guard(raw)
    assert result["status"] == "hold"
    assert result["evidenceStatus"] == "INCOMPLETE"
    reasons = result["actionResults"][0]["evidenceReasons"]  # type: ignore[index]
    assert "MISSING_EXECUTION_RECEIPT" in reasons
    assert "MISSING_INDEPENDENT_WITNESS" in reasons


def _declared_history_is_carried_but_not_claimed_as_verified() -> None:
    raw = model()
    raw["history"] = {
        "previousResultHash": "a" * 64,
        "deniedSemanticActionIds": ["old-denial"],
    }
    result = evaluate_action_guard(raw)
    assert result["history"]["previousResultHash"] == "a" * 64  # type: ignore[index]
    assert result["history"]["independentlyVerified"] is False  # type: ignore[index]
    assert "not independently verified" in result["claimBoundary"]


def _arbitrary_nonempty_json_subject_is_bound_deterministically() -> None:
    raw = model()
    first = evaluate_action_guard(raw)
    second = evaluate_action_guard(copy.deepcopy(raw))
    assert first == second
    assert first["subjectHash"] == canonical_sha256(raw["subject"])
    assert first["resultHash"] == second["resultHash"]
    material = {key: value for key, value in first.items() if key != "resultHash"}
    assert first["resultHash"] == canonical_sha256(material)


def _extra_field_and_empty_subject_fail_closed() -> None:
    raw = model()
    raw["surprise"] = True
    with unittest.TestCase().assertRaisesRegex(ActionGuardError, "unexpected fields"):
        validate_action_guard(raw)

    raw = model()
    raw["actions"] = [action(raw)]
    raw["actions"][0]["surprise"] = True  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ActionGuardError, "unexpected fields"):
        evaluate_action_guard(raw)

    raw = model()
    raw["subject"] = {}
    with unittest.TestCase().assertRaisesRegex(ActionGuardError, "non-empty JSON"):
        validate_action_guard(raw)


def _subject_hash_fields_require_sha256_digests() -> None:
    raw = model()
    raw["authorization"]["subjectHash"] = "not-a-digest"  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ActionGuardError, "authorization.subjectHash"):
        validate_action_guard(raw)

    raw = model()
    raw["actions"] = [action(raw)]
    raw["actions"][0]["subjectHash"] = "f" * 63  # type: ignore[index]
    with unittest.TestCase().assertRaisesRegex(ActionGuardError, r"actions\[0\].subjectHash"):
        validate_action_guard(raw)


class ActionGuardTests(unittest.TestCase):
    """Expose every Action Guard policy case to unittest discovery."""

    test_clean_preflight_passes_without_execution_evidence = staticmethod(
        _clean_preflight_passes_without_execution_evidence
    )
    test_clean_witnessed_postflight_passes = staticmethod(
        _clean_witnessed_postflight_passes
    )
    test_out_of_scope_action_safely_denied_is_hold = staticmethod(
        _out_of_scope_action_safely_denied_is_hold
    )
    test_recorded_allow_for_out_of_scope_action_is_control_failure = staticmethod(
        _recorded_allow_for_out_of_scope_action_is_control_failure
    )
    test_denial_then_same_semantic_retry_is_nonconformant = staticmethod(
        _denial_then_same_semantic_retry_is_nonconformant
    )
    test_declared_prior_denial_blocks_same_semantic_retry = staticmethod(
        _declared_prior_denial_blocks_same_semantic_retry
    )
    test_denial_then_different_safe_alternative_is_allowed = staticmethod(
        _denial_then_different_safe_alternative_is_allowed
    )
    test_canary_is_blocked_and_executing_it_fails = staticmethod(
        _canary_is_blocked_and_executing_it_fails
    )
    test_stale_authorization_is_safely_denied = staticmethod(
        _stale_authorization_is_safely_denied
    )
    test_false_stop_is_hold_and_capability_bypass_is_fail = staticmethod(
        _false_stop_is_hold_and_capability_bypass_is_fail
    )
    test_live_write_requires_a_separate_explicit_approval_ref = staticmethod(
        _live_write_requires_a_separate_explicit_approval_ref
    )
    test_monitor_must_be_independent = staticmethod(_monitor_must_be_independent)
    test_path_prefix_requires_a_real_component_boundary = staticmethod(
        _path_prefix_requires_a_real_component_boundary
    )
    test_missing_receipt_or_witness_is_evidence_hold_not_fail = staticmethod(
        _missing_receipt_or_witness_is_evidence_hold_not_fail
    )
    test_declared_history_is_carried_but_not_claimed_as_verified = staticmethod(
        _declared_history_is_carried_but_not_claimed_as_verified
    )
    test_arbitrary_nonempty_json_subject_is_bound_deterministically = staticmethod(
        _arbitrary_nonempty_json_subject_is_bound_deterministically
    )
    test_extra_field_and_empty_subject_fail_closed = staticmethod(
        _extra_field_and_empty_subject_fail_closed
    )
    test_subject_hash_fields_require_sha256_digests = staticmethod(
        _subject_hash_fields_require_sha256_digests
    )


if __name__ == "__main__":
    unittest.main()
