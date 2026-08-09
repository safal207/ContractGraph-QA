#!/usr/bin/env python3
"""In-memory adapters for the Temporal Transition Field v0.4 demo/tests.

These adapters perform no network activity. `SyntheticBuggyAdapter` deliberately
models one concurrency bug so the path-to-finding engine has a deterministic
forbidden state to discover. `SyntheticSafeAdapter` resolves that race safely.
"""
from __future__ import annotations

import copy
from typing import Any


class SyntheticBudgetAdapter:
    def __init__(self, allow_concurrent_overspend: bool = False):
        self.allow_concurrent_overspend = allow_concurrent_overspend
        self.reset()

    def reset(self) -> None:
        self.state_id = "Q0_RESET"
        self.values = {
            "resource_balance": 0,
            "consumed_budget": 0,
            "budget_limit": 0,
            "per_action_limit": 0,
            "transaction_count": 0,
            "evidence_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
        }
        self._audit_seq = 0
        self._tx_seq = 0

    def snapshot(self) -> dict[str, Any]:
        return {"state_id": self.state_id, "values": copy.deepcopy(self.values)}

    def _audit_ref(self) -> str:
        self._audit_seq += 1
        self.values["evidence_count"] += 1
        return f"audit-{self._audit_seq:03d}"

    def _tx_ref(self) -> str:
        self._tx_seq += 1
        self.values["transaction_count"] += 1
        return f"tx-{self._tx_seq:03d}"

    def _result(
        self,
        *,
        event: str,
        outcome: str,
        committed: bool,
        financial_mutation_count: int,
        durable_mutation_count: int,
        audit_refs: list[str] | None = None,
        transaction_refs: list[str] | None = None,
        parameters: dict[str, Any] | None = None,
        reason: str | None = None,
        concurrency_group: str | None = None,
    ) -> dict[str, Any]:
        return {
            "request": {
                "action": event,
                "logical_operation_id": f"synthetic-{event}",
                "parameters": parameters or {},
                "concurrency_group": concurrency_group,
            },
            "decision": {"outcome": outcome, "status_code": "synthetic", "reason": reason},
            "mutation": {
                "committed": committed,
                "financial_mutation_count": financial_mutation_count,
                "durable_mutation_count": durable_mutation_count,
                "details": {},
            },
            "evidence": {
                "transaction_refs": transaction_refs or [],
                "audit_refs": audit_refs or [],
                "response_hash": None,
                "artifacts": [],
            },
        }

    def apply(self, event: str) -> dict[str, Any]:
        if event == "fund":
            self.values["resource_balance"] = 100
            self.state_id = "Q1_FUNDED"
            audit = self._audit_ref()
            return self._result(
                event=event,
                outcome="accepted",
                committed=True,
                financial_mutation_count=1,
                durable_mutation_count=1,
                audit_refs=[audit],
                parameters={"amount": 100},
            )

        if event == "set_policy":
            self.values["budget_limit"] = 40
            self.values["per_action_limit"] = 40
            self.state_id = "Q2_READY"
            audit = self._audit_ref()
            return self._result(
                event=event,
                outcome="accepted",
                committed=True,
                financial_mutation_count=0,
                durable_mutation_count=1,
                audit_refs=[audit],
                parameters={"budget_limit": 40, "per_action_limit": 40},
            )

        if event == "action_valid":
            amount = 20
            self.values["resource_balance"] -= amount
            self.values["consumed_budget"] += amount
            self.values["accepted_count"] += 1
            tx, audit = self._tx_ref(), self._audit_ref()
            self.state_id = "Q3_COMMITTED"
            return self._result(
                event=event,
                outcome="accepted",
                committed=True,
                financial_mutation_count=1,
                durable_mutation_count=1,
                transaction_refs=[tx],
                audit_refs=[audit],
                parameters={"amount": amount},
            )

        if event == "action_reaches_limit":
            amount = self.values["budget_limit"] - self.values["consumed_budget"]
            self.values["resource_balance"] -= amount
            self.values["consumed_budget"] += amount
            self.values["accepted_count"] += 1
            tx, audit = self._tx_ref(), self._audit_ref()
            self.state_id = "Q4_LIMIT_FULL"
            return self._result(
                event=event,
                outcome="accepted",
                committed=True,
                financial_mutation_count=1,
                durable_mutation_count=1,
                transaction_refs=[tx],
                audit_refs=[audit],
                parameters={"amount": amount},
            )

        if event == "action_invalid":
            self.values["rejected_count"] += 1
            self.state_id = "Q5_REJECTED"
            return self._result(
                event=event,
                outcome="rejected",
                committed=False,
                financial_mutation_count=0,
                durable_mutation_count=0,
                parameters={"amount": 50},
                reason="Synthetic policy rejection.",
            )

        if event == "duplicate_retry":
            amount = 10
            self.values["resource_balance"] -= amount
            self.values["consumed_budget"] += amount
            self.values["accepted_count"] += 1
            tx, audit = self._tx_ref(), self._audit_ref()
            self.state_id = "Q6_REPLAY_CHECK"
            return self._result(
                event=event,
                outcome="accepted",
                committed=True,
                financial_mutation_count=1,
                durable_mutation_count=1,
                transaction_refs=[tx],
                audit_refs=[audit],
                parameters={"amount": amount, "attempts": 2},
                reason="Retry suppressed; one financial mutation committed.",
            )

        if event == "concurrent_action":
            each = 30
            if self.allow_concurrent_overspend:
                committed_total = each * 2
                self.values["resource_balance"] -= committed_total
                self.values["consumed_budget"] += committed_total
                self.values["accepted_count"] += 2
                txs = [self._tx_ref(), self._tx_ref()]
                audits = [self._audit_ref(), self._audit_ref()]
                mutation_count = 2
                outcome = "accepted"
                reason = "Synthetic bug: both concurrent actions committed."
            else:
                committed_total = each
                self.values["resource_balance"] -= committed_total
                self.values["consumed_budget"] += committed_total
                self.values["accepted_count"] += 1
                self.values["rejected_count"] += 1
                txs = [self._tx_ref()]
                audits = [self._audit_ref()]
                mutation_count = 1
                outcome = "partial"
                reason = "Synthetic safe resolution: one commit, one rejection."
            self.state_id = "Q7_RACE"
            return self._result(
                event=event,
                outcome=outcome,
                committed=True,
                financial_mutation_count=mutation_count,
                durable_mutation_count=mutation_count,
                transaction_refs=txs,
                audit_refs=audits,
                parameters={"amounts": [each, each]},
                reason=reason,
                concurrency_group="synthetic-race-001",
            )

        raise ValueError(f"Unsupported synthetic event: {event}")


class SyntheticBuggyAdapter(SyntheticBudgetAdapter):
    def __init__(self):
        super().__init__(allow_concurrent_overspend=True)


class SyntheticSafeAdapter(SyntheticBudgetAdapter):
    def __init__(self):
        super().__init__(allow_concurrent_overspend=False)
