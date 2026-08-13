from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision,
    evaluate_agent_payment_decision_file,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "benchmarks" / "agent-payment-recovery-v0.1" / "unified-decision" / "examples"


def test_initial_authorized_payment_is_allowed() -> None:
    result = evaluate_agent_payment_decision_file(EXAMPLES / "allow-initial.json")
    assert result["decision"] == "ALLOW"
    assert result["monetaryActionAllowed"] is True


def test_ambiguous_payment_requires_reconciliation() -> None:
    result = evaluate_agent_payment_decision_file(EXAMPLES / "reconcile-ambiguous.json")
    assert result["decision"] == "RECONCILE"
    assert result["monetaryActionAllowed"] is False
    assert "payment_finality" in result["blockers"]


def test_final_failure_with_unresolved_retry_authority_holds() -> None:
    result = evaluate_agent_payment_decision_file(EXAMPLES / "hold-retry-unresolved.json")
    assert result["decision"] == "HOLD"
    assert result["reason"] == "retry_authority_unresolved"


def test_committed_and_delivered_stops_same_logical_operation() -> None:
    result = evaluate_agent_payment_decision_file(EXAMPLES / "stop-delivered.json")
    assert result["decision"] == "STOP"
    assert result["reason"] == "logical_operation_already_satisfied"


def test_committed_but_not_delivered_requires_compensation() -> None:
    result = evaluate_agent_payment_decision_file(EXAMPLES / "compensate-not-delivered.json")
    assert result["decision"] == "COMPENSATE"
    assert result["monetaryActionAllowed"] is False


def test_documented_retry_can_be_allowed() -> None:
    payload = json.loads((EXAMPLES / "hold-retry-unresolved.json").read_text(encoding="utf-8"))
    payload = copy.deepcopy(payload)
    payload["payment"]["retryAuthorityStatus"] = "documented"
    payload["payment"]["retryAllowed"] = True
    result = evaluate_agent_payment_decision(payload)
    assert result["decision"] == "ALLOW"
    assert result["reason"] == "documented_retry_authority"


def test_unresolved_retry_authority_cannot_claim_retry_allowed() -> None:
    payload = json.loads((EXAMPLES / "hold-retry-unresolved.json").read_text(encoding="utf-8"))
    payload["payment"]["retryAllowed"] = True
    with pytest.raises(AgentPaymentDecisionError, match="unresolved retry authority"):
        evaluate_agent_payment_decision(payload)


def test_unknown_authority_holds_even_before_payment() -> None:
    payload = json.loads((EXAMPLES / "allow-initial.json").read_text(encoding="utf-8"))
    payload["authority"]["status"] = "unknown"
    result = evaluate_agent_payment_decision(payload)
    assert result["decision"] == "HOLD"
    assert result["reason"] == "authority_unresolved"
