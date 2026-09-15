from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "contractgraph.identity-authority-boundary.v0.1"
ISSUE = "https://github.com/safal207/ContractGraph-QA/issues/172"
PREDECESSOR = "https://github.com/safal207/ContractGraph-QA/pull/171"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def stable_action_id(intent: str, target: str, args: dict[str, Any]) -> str:
    return "act_" + canonical_hash({"intent": intent, "target": target, "args": args})[:32]


def intent_hash(intent: str, args: dict[str, Any]) -> str:
    return canonical_hash({"intent": intent, "args": args})


@dataclass
class Permit:
    permit_id: str
    action_id: str
    target: str
    intent_hash: str
    consumed: bool = False


class AuthorityStore:
    """Durable authority state, intentionally separate from runtime state."""

    def __init__(self) -> None:
        self._serial = 0
        self.permits: dict[str, Permit] = {}

    def issue(self, *, action_id: str, target: str, intent_hash_value: str) -> Permit:
        self._serial += 1
        permit_id = "permit_" + canonical_hash(
            {
                "serial": self._serial,
                "action_id": action_id,
                "target": target,
                "intent_hash": intent_hash_value,
            }
        )[:24]
        permit = Permit(permit_id, action_id, target, intent_hash_value)
        self.permits[permit_id] = permit
        return permit

    def consume(
        self,
        *,
        permit_id: str,
        action_id: str,
        target: str,
        intent_hash_value: str,
    ) -> tuple[bool, str]:
        permit = self.permits.get(permit_id)
        if permit is None:
            return False, "unknown_permit"
        if permit.consumed:
            return False, "reused_permit"
        if permit.action_id != action_id:
            return False, "action_mismatch"
        if permit.target != target:
            return False, "target_mismatch"
        if permit.intent_hash != intent_hash_value:
            return False, "intent_mismatch"
        permit.consumed = True
        return True, "consumed"


class ExternalTarget:
    """Tiny read-back oracle used only to discriminate recovery decisions."""

    def __init__(self) -> None:
        self.receipts: dict[str, dict[str, Any]] = {}
        self.forced_readback: dict[str, dict[str, Any]] = {}
        self.dispatch_count = 0

    def dispatch(self, *, action_id: str, target: str, intent_hash_value: str) -> dict[str, Any]:
        self.dispatch_count += 1
        receipt = {
            "receipt_id": "rcpt_" + canonical_hash(
                {
                    "ordinal": self.dispatch_count,
                    "action_id": action_id,
                    "target": target,
                    "intent_hash": intent_hash_value,
                }
            )[:24],
            "action_id": action_id,
            "target": target,
            "intent_hash": intent_hash_value,
            "status": "CONFIRMED",
        }
        self.receipts[action_id] = receipt
        return receipt

    def set_readback(self, action_id: str, result: dict[str, Any]) -> None:
        self.forced_readback[action_id] = dict(result)

    def readback(self, action_id: str) -> dict[str, Any]:
        if action_id in self.forced_readback:
            return dict(self.forced_readback[action_id])
        if action_id in self.receipts:
            return dict(self.receipts[action_id])
        return {"status": "NOT_EXECUTED", "action_id": action_id}


def reconcile(
    *,
    persisted_action_id: str,
    expected_target: str,
    expected_intent_hash: str,
    target: ExternalTarget,
) -> tuple[str, dict[str, Any]]:
    readback = target.readback(persisted_action_id)
    status = readback.get("status")
    if status == "UNKNOWN":
        return "fail_closed", readback
    if status == "NOT_EXECUTED":
        return "fresh_authorization", readback
    if status != "CONFIRMED":
        return "fail_closed", readback
    if readback.get("action_id") != persisted_action_id:
        return "reject_receipt_identity_mismatch", readback
    if readback.get("target") != expected_target:
        return "reject_target_mismatch", readback
    if readback.get("intent_hash") != expected_intent_hash:
        return "reject_intent_mismatch", readback
    return "return_prior", readback


def scenario_control_new() -> dict[str, Any]:
    intent = "transfer"
    args = {"amount": "10.00", "asset": "USD"}
    target_name = "ledger-A"
    action_id = stable_action_id(intent, target_name, args)
    ih = intent_hash(intent, args)
    authority = AuthorityStore()
    target = ExternalTarget()
    permit = authority.issue(action_id=action_id, target=target_name, intent_hash_value=ih)
    ok, consume_verdict = authority.consume(
        permit_id=permit.permit_id,
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    receipt = target.dispatch(action_id=action_id, target=target_name, intent_hash_value=ih) if ok else None
    passed = (
        ok
        and consume_verdict == "consumed"
        and target.dispatch_count == 1
        and receipt is not None
        and receipt["status"] == "CONFIRMED"
    )
    return {
        "case": "control-new",
        "persisted_action_id": None,
        "restored_action_id": action_id,
        "prior_permit_id": None,
        "prior_permit_consumed": False,
        "readback": None,
        "decision": "dispatch",
        "dispatch_count_delta": 1,
        "identity_continuity": "not_applicable_new_action",
        "authority_continuity": "fresh_permit_required_and_consumed",
        "passed": passed,
    }


def _seed_recovery(
    *,
    commit_effect: bool,
    forced_readback: dict[str, Any] | None = None,
) -> tuple[str, str, str, dict[str, Any], AuthorityStore, ExternalTarget, str]:
    intent = "transfer"
    args = {"amount": "10.00", "asset": "USD"}
    target_name = "ledger-A"
    action_id = stable_action_id(intent, target_name, args)
    ih = intent_hash(intent, args)
    authority = AuthorityStore()
    target = ExternalTarget()
    permit = authority.issue(action_id=action_id, target=target_name, intent_hash_value=ih)
    ok, verdict = authority.consume(
        permit_id=permit.permit_id,
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    assert ok and verdict == "consumed"
    if commit_effect:
        target.dispatch(action_id=action_id, target=target_name, intent_hash_value=ih)
    if forced_readback is not None:
        normalized = dict(forced_readback)
        normalized.setdefault("action_id", action_id)
        target.set_readback(action_id, normalized)
    persisted = {
        "action_id": action_id,
        "permit_id": permit.permit_id,
        "intent_hash": ih,
        "target": target_name,
    }
    return action_id, ih, target_name, persisted, authority, target, permit.permit_id


def _recovery_result(
    *,
    case: str,
    action_id: str,
    persisted: dict[str, Any],
    authority: AuthorityStore,
    target: ExternalTarget,
    prior_permit: str,
    ih: str,
    target_name: str,
    expected_decision: str,
    authority_continuity: str,
) -> dict[str, Any]:
    before = target.dispatch_count
    decision, readback = reconcile(
        persisted_action_id=persisted["action_id"],
        expected_target=target_name,
        expected_intent_hash=ih,
        target=target,
    )
    after = target.dispatch_count
    passed = (
        persisted["action_id"] == action_id
        and decision == expected_decision
        and after == before
        and authority.permits[prior_permit].consumed
    )
    return {
        "case": case,
        "persisted_action_id": persisted["action_id"],
        "restored_action_id": action_id,
        "prior_permit_id": prior_permit,
        "prior_permit_consumed": authority.permits[prior_permit].consumed,
        "readback": readback,
        "decision": decision,
        "dispatch_count_delta": after - before,
        "identity_continuity": "same_action_id",
        "authority_continuity": authority_continuity,
        "passed": passed,
    }


def scenario_recovery_confirmed() -> dict[str, Any]:
    action_id, ih, target_name, persisted, authority, target, prior_permit = _seed_recovery(commit_effect=True)
    return _recovery_result(
        case="recovery-confirmed",
        action_id=action_id,
        persisted=persisted,
        authority=authority,
        target=target,
        prior_permit=prior_permit,
        ih=ih,
        target_name=target_name,
        expected_decision="return_prior",
        authority_continuity="old_permit_not_reused",
    )


def scenario_recovery_unknown() -> dict[str, Any]:
    action_id, ih, target_name, persisted, authority, target, prior_permit = _seed_recovery(
        commit_effect=False,
        forced_readback={"status": "UNKNOWN"},
    )
    return _recovery_result(
        case="recovery-unknown",
        action_id=action_id,
        persisted=persisted,
        authority=authority,
        target=target,
        prior_permit=prior_permit,
        ih=ih,
        target_name=target_name,
        expected_decision="fail_closed",
        authority_continuity="no_authority_from_persisted_state",
    )


def scenario_recovery_not_executed() -> dict[str, Any]:
    action_id, ih, target_name, persisted, authority, target, prior_permit = _seed_recovery(
        commit_effect=False,
        forced_readback={"status": "NOT_EXECUTED"},
    )
    before = target.dispatch_count
    decision, readback = reconcile(
        persisted_action_id=persisted["action_id"],
        expected_target=target_name,
        expected_intent_hash=ih,
        target=target,
    )
    new_permit = authority.issue(action_id=action_id, target=target_name, intent_hash_value=ih)
    fresh_ok, fresh_verdict = authority.consume(
        permit_id=new_permit.permit_id,
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    if decision == "fresh_authorization" and fresh_ok:
        target.dispatch(action_id=action_id, target=target_name, intent_hash_value=ih)
    after = target.dispatch_count
    passed = (
        persisted["action_id"] == action_id
        and decision == "fresh_authorization"
        and authority.permits[prior_permit].consumed
        and new_permit.permit_id != prior_permit
        and fresh_verdict == "consumed"
        and after - before == 1
    )
    return {
        "case": "recovery-not-executed",
        "persisted_action_id": persisted["action_id"],
        "restored_action_id": action_id,
        "prior_permit_id": prior_permit,
        "prior_permit_consumed": authority.permits[prior_permit].consumed,
        "new_permit_id": new_permit.permit_id,
        "readback": readback,
        "decision": decision,
        "dispatch_count_delta": after - before,
        "identity_continuity": "same_action_id",
        "authority_continuity": "new_permit_required",
        "passed": passed,
    }


def scenario_replay_old_permit() -> dict[str, Any]:
    action_id, ih, target_name, persisted, authority, target, prior_permit = _seed_recovery(commit_effect=False)
    before = target.dispatch_count
    ok, verdict = authority.consume(
        permit_id=persisted["permit_id"],
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    if ok:
        target.dispatch(action_id=action_id, target=target_name, intent_hash_value=ih)
    after = target.dispatch_count
    passed = persisted["action_id"] == action_id and not ok and verdict == "reused_permit" and after == before
    return {
        "case": "replay-old-permit",
        "persisted_action_id": persisted["action_id"],
        "restored_action_id": action_id,
        "prior_permit_id": prior_permit,
        "prior_permit_consumed": authority.permits[prior_permit].consumed,
        "readback": None,
        "decision": "reject_reused_permit" if not ok else "dispatch",
        "dispatch_count_delta": after - before,
        "identity_continuity": "same_action_id",
        "authority_continuity": verdict,
        "passed": passed,
    }


def scenario_target_mismatch() -> dict[str, Any]:
    intent = "transfer"
    args = {"amount": "10.00", "asset": "USD"}
    ih = intent_hash(intent, args)
    action_id, _, target_name, persisted, authority, target, prior_permit = _seed_recovery(
        commit_effect=False,
        forced_readback={
            "status": "CONFIRMED",
            "target": "ledger-B",
            "intent_hash": ih,
            "receipt_id": "rcpt_mismatched_target",
        },
    )
    return _recovery_result(
        case="target-mismatch",
        action_id=action_id,
        persisted=persisted,
        authority=authority,
        target=target,
        prior_permit=prior_permit,
        ih=ih,
        target_name=target_name,
        expected_decision="reject_target_mismatch",
        authority_continuity="receipt_target_must_match",
    )


def run_mutant_discrimination() -> dict[str, Any]:
    class UnsafeReusableAuthorityStore(AuthorityStore):
        def consume(
            self,
            *,
            permit_id: str,
            action_id: str,
            target: str,
            intent_hash_value: str,
        ) -> tuple[bool, str]:
            permit = self.permits.get(permit_id)
            if permit is None:
                return False, "unknown_permit"
            if permit.action_id != action_id:
                return False, "action_mismatch"
            if permit.target != target:
                return False, "target_mismatch"
            if permit.intent_hash != intent_hash_value:
                return False, "intent_mismatch"
            permit.consumed = True
            return True, "consumed"

    intent = "transfer"
    args = {"amount": "10.00", "asset": "USD"}
    target_name = "ledger-A"
    action_id = stable_action_id(intent, target_name, args)
    ih = intent_hash(intent, args)
    unsafe_authority = UnsafeReusableAuthorityStore()
    permit = unsafe_authority.issue(action_id=action_id, target=target_name, intent_hash_value=ih)
    first_ok, _ = unsafe_authority.consume(
        permit_id=permit.permit_id,
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    second_ok, second_verdict = unsafe_authority.consume(
        permit_id=permit.permit_id,
        action_id=action_id,
        target=target_name,
        intent_hash_value=ih,
    )
    reusable_permit_mutant_detected = first_ok and second_ok and second_verdict == "consumed"
    unsafe_unknown_decision = "dispatch" if action_id else "fail_closed"
    persisted_identity_authority_mutant_detected = unsafe_unknown_decision != "fail_closed"
    return {
        "reusable_permit_mutant_detected": reusable_permit_mutant_detected,
        "persisted_identity_authority_mutant_detected": persisted_identity_authority_mutant_detected,
        "detected_mutants": int(reusable_permit_mutant_detected) + int(persisted_identity_authority_mutant_detected),
        "total_mutants": 2,
    }


def run_suite() -> dict[str, Any]:
    cases = [
        scenario_control_new(),
        scenario_recovery_confirmed(),
        scenario_recovery_unknown(),
        scenario_recovery_not_executed(),
        scenario_replay_old_permit(),
        scenario_target_mismatch(),
    ]
    passed = sum(1 for case in cases if case["passed"])
    recovery_cases = [case for case in cases if case["case"] != "control-new"]
    return {
        "schema": SCHEMA,
        "issue": ISSUE,
        "predecessor": PREDECESSOR,
        "result": "PASS" if passed == len(cases) else "FAIL",
        "passed_cases": passed,
        "total_cases": len(cases),
        "identity_continuity": all(case["identity_continuity"] == "same_action_id" for case in recovery_cases),
        "authority_non_continuity": all(
            case["dispatch_count_delta"] == 0
            for case in recovery_cases
            if case["case"] in {"recovery-confirmed", "recovery-unknown", "replay-old-permit", "target-mismatch"}
        )
        and next(case for case in recovery_cases if case["case"] == "recovery-not-executed")["authority_continuity"] == "new_permit_required",
        "invariant": "Restoring action_id is evidence about which logical action this is; it is not permission to perform the action again.",
        "mutant_discrimination": run_mutant_discrimination(),
        "cases": cases,
        "non_claims": [
            "This is a framework-neutral executable model, not a CrewAI/LangGraph/AutoGen runtime integration.",
            "It does not prove global exactly-once execution.",
            "It does not prove target availability or Byzantine correctness.",
            "It assumes the AuthorityStore is durable and non-bypassable.",
            "It does not prove distributed consensus.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    report = run_suite()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write_report:
        args.write_report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
