#!/usr/bin/env python3
"""Valta Sprint 1 sandbox adapter scaffold for ContractGraph-QA v0.7.

Safety properties:
- sandbox/test scope only;
- API key is read only from VALTA_TEST_API_KEY and is never logged;
- network execution is disabled by default;
- spend events are hard-blocked until the exact spend request body is confirmed;
- concurrency is capped at two workers;
- the known /wallet/transfer test-key 403 is not treated as a finding target.

This file intentionally provides request planning and contract wiring first. It
must not guess undocumented spend payloads.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ENDPOINT_MAP = HERE / "endpoint_map.valta.sandbox.json"


class ValtaAdapterNotReady(RuntimeError):
    pass


class ValtaSandboxAdapter:
    def __init__(self, *, live: bool = False):
        self.config = json.loads(ENDPOINT_MAP.read_text(encoding="utf-8"))
        gate = self.config["execution_gate"]
        if live and not gate.get("live_execution_enabled"):
            raise ValtaAdapterNotReady("live execution is disabled by the v0.7 execution gate")
        self.live = live
        self.agent = self.config["agent"]
        self._state = {
            "state_id": "Q0_RESET",
            "values": {
                "resource_balance": 0,
                "consumed_budget": 0,
                "budget_limit": 0,
                "per_action_limit": 0,
                "transaction_count": 0,
                "evidence_count": 0,
                "accepted_count": 0,
                "rejected_count": 0,
            },
        }

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._state)

    def _require_key_name_only(self) -> str:
        key = os.environ.get("VALTA_TEST_API_KEY")
        if not key:
            raise ValtaAdapterNotReady("VALTA_TEST_API_KEY is required only when live execution is explicitly enabled")
        return key

    def _request_plan(self, name: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = self.config["confirmed_endpoints"][name]
        return {
            "method": endpoint["method"],
            "url": self.config["base_url"] + endpoint["path"],
            "headers": {"x-api-key": "<from VALTA_TEST_API_KEY>"},
            "json": body,
        }

    def plan_reset(self) -> dict[str, Any]:
        return self._request_plan("reset")

    def plan_fund(self, *, amount: float, idempotency_key: str) -> dict[str, Any]:
        return self._request_plan(
            "fund",
            {"agent": self.agent, "amount": amount, "idempotencyKey": idempotency_key},
        )

    def plan_policy(self, *, daily_limit: float, max_per_transaction: float) -> dict[str, Any]:
        return self._request_plan(
            "set_policy",
            {
                "agentId": self.agent,
                "dailyLimit": daily_limit,
                "maxPerTransaction": max_per_transaction,
            },
        )

    def plan_audit(self) -> dict[str, Any]:
        return self._request_plan("audit")

    def plan_transactions(self) -> dict[str, Any]:
        return self._request_plan("transactions")

    def plan_spend(self, *, event: str, amount: float) -> dict[str, Any]:
        if event not in {
            "action_valid",
            "action_reaches_limit",
            "action_invalid",
            "duplicate_retry",
            "concurrent_action",
        }:
            raise ValueError(f"not a spend event: {event}")
        if not self.config["execution_gate"].get("spend_payload_confirmed"):
            raise ValtaAdapterNotReady(
                "spend request body is not confirmed; refusing to guess payload for /spend"
            )
        raise ValtaAdapterNotReady("spend planner awaits confirmed body mapping")

    def apply(self, event: str) -> dict[str, Any]:
        """Contract entrypoint. v0.7 remains execution-gated by design."""
        if event == "fund":
            plan = self.plan_fund(amount=100, idempotency_key="cgqa-v07-fund-001")
        elif event == "set_policy":
            plan = self.plan_policy(daily_limit=60, max_per_transaction=40)
        else:
            plan = self.plan_spend(event=event, amount=20)

        if not self.live:
            raise ValtaAdapterNotReady(
                f"dry-run adapter produced a request plan for {event}; live target execution remains disabled: {plan['method']} {plan['url']}"
            )

        self._require_key_name_only()
        raise ValtaAdapterNotReady("network transport is intentionally not enabled in v0.7 scaffold")


def main() -> int:
    adapter = ValtaSandboxAdapter(live=False)
    output = {
        "reset": adapter.plan_reset(),
        "fund": adapter.plan_fund(amount=100, idempotency_key="cgqa-preview-fund-001"),
        "policy": adapter.plan_policy(daily_limit=60, max_per_transaction=40),
        "audit": adapter.plan_audit(),
        "transactions": adapter.plan_transactions(),
        "spend_ready": adapter.config["execution_gate"]["spend_payload_confirmed"],
        "live_execution_enabled": adapter.config["execution_gate"]["live_execution_enabled"],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
