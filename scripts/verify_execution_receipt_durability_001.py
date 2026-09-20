#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

SYSTEM_CASE = "EXECUTION-RECEIPT-DURABILITY-001"
SCHEMA = "contractgraph.execution-receipt-durability.v0.1"

EXPECTED = {
    "effect_then_crash": {
        "attempts": 1,
        "effects": 1,
        "records": 2,
        "sequence": [
            ("PENDING", "NOT_READ_BACK", "INDETERMINATE", "IN_FLIGHT"),
            ("RECONCILIATION", "FULL", "ONE_EFFECT_MATCHING", "FINALIZE_EXISTING"),
        ],
        "recovery": "FINALIZE_EXISTING_NO_REDISPATCH",
    },
    "crash_before_effect": {
        "attempts": 1,
        "effects": 0,
        "records": 2,
        "sequence": [
            ("PENDING", "NOT_READ_BACK", "INDETERMINATE", "IN_FLIGHT"),
            (
                "RECONCILIATION",
                "FULL",
                "NO_EFFECT",
                "FRESH_AUTHORIZATION_REQUIRED",
            ),
        ],
        "recovery": "NO_REDISPATCH_FRESH_AUTHORIZATION_REQUIRED",
    },
    "unavailable_readback": {
        "attempts": 1,
        "effects": 1,
        "records": 3,
        "sequence": [
            ("PENDING", "NOT_READ_BACK", "INDETERMINATE", "IN_FLIGHT"),
            ("RECONCILIATION", "UNAVAILABLE", "INDETERMINATE", "REVALIDATE"),
            ("RECONCILIATION", "FULL", "ONE_EFFECT_MATCHING", "FINALIZE_EXISTING"),
        ],
        "recovery": "FINALIZE_EXISTING_NO_REDISPATCH",
    },
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"{SYSTEM_CASE} VERIFY FAIL: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def integrity_check(path: Path) -> None:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        row = conn.execute("pragma integrity_check").fetchone()
    require(row is not None and row[0] == "ok", f"SQLite integrity_check failed: {path}")


def read_receipt_rows(path: Path, action_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "select * from records where action_id = ? order by ordinal",
            (action_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "schema": SCHEMA,
                "ordinal": int(row["ordinal"]),
                "action_id": str(row["action_id"]),
                "case_name": str(row["case_name"]),
                "record_kind": str(row["record_kind"]),
                "target": str(row["target"]),
                "payload_digest": str(row["payload_digest"]),
                "trace_id": str(row["trace_id"]),
                "decision_id": str(row["decision_id"]),
                "execution_id": str(row["execution_id"]),
                "evidence_id": str(row["evidence_id"]),
                "observation_availability": str(row["observation_availability"]),
                "external_outcome": str(row["external_outcome"]),
                "externally_verified": bool(row["externally_verified"]),
                "effect_count": None if row["effect_count"] is None else int(row["effect_count"]),
                "continuity": str(row["continuity"]),
                "recovery_decision": str(row["recovery_decision"]),
                "previous_record_sha256": (
                    None
                    if row["previous_record_sha256"] is None
                    else str(row["previous_record_sha256"])
                ),
                "record_sha256": str(row["record_sha256"]),
            }
        )
    return out


def verify_record_chain(records: list[dict[str, Any]]) -> None:
    previous = None
    for expected_ordinal, record in enumerate(records, start=1):
        require(record["ordinal"] == expected_ordinal, "record ordinal gap")
        require(
            record["previous_record_sha256"] == previous,
            "record hash-chain predecessor mismatch",
        )
        supplied = record["record_sha256"]
        body = dict(record)
        body.pop("record_sha256", None)
        actual = sha256_json(body)
        require(supplied == actual, "record SHA-256 mismatch")
        previous = supplied


def read_verifications(path: Path, action_id: str) -> list[dict[str, Any]]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select verification_kind, verified, observed_record_sha256
            from verifications where action_id = ? order by seq
            """,
            (action_id,),
        ).fetchall()
    return [
        {
            "kind": str(row["verification_kind"]),
            "verified": bool(row["verified"]),
            "observed_record_sha256": str(row["observed_record_sha256"]),
        }
        for row in rows
    ]


def read_receiver(path: Path, action_id: str) -> dict[str, Any]:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        attempts = conn.execute(
            "select target, payload_digest from attempts where action_id = ? order by seq",
            (action_id,),
        ).fetchall()
        effects = conn.execute(
            """
            select target, payload_digest, result
            from effects where action_id = ? order by seq
            """,
            (action_id,),
        ).fetchall()
        checks = conn.execute(
            """
            select verification_kind, verified, observed_effect_count
            from verifications where action_id = ? order by seq
            """,
            (action_id,),
        ).fetchall()
    return {
        "attempts": [
            {
                "target": str(row["target"]),
                "payload_digest": str(row["payload_digest"]),
            }
            for row in attempts
        ],
        "effects": [
            {
                "target": str(row["target"]),
                "payload_digest": str(row["payload_digest"]),
                "result": str(row["result"]),
            }
            for row in effects
        ],
        "verifications": [
            {
                "kind": str(row["verification_kind"]),
                "verified": bool(row["verified"]),
                "observed_effect_count": int(row["observed_effect_count"]),
            }
            for row in checks
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.report.read_bytes()
    report = json.loads(raw)

    require(report.get("schema") == SCHEMA, "wrong report schema")
    require(report.get("system_case") == SYSTEM_CASE, "wrong system_case")
    require(report.get("status") == "PASS", "durability harness did not PASS")
    require(
        report.get("barrier") == "durable_pending_then_real_process_sigkill_before_terminal",
        "wrong crash barrier",
    )
    require(
        report.get("source_runtime", {}).get("repository") == "aegisora-ai/aegisora",
        "wrong source runtime",
    )
    require(
        report.get("source_runtime", {}).get("commit")
        == "2bac618215671f6f0ac8ebddf169830d4fc0f9b3",
        "wrong source runtime commit",
    )

    verified_cases: dict[str, Any] = {}

    for case_name, expected in EXPECTED.items():
        case = report.get("cases", {}).get(case_name)
        require(isinstance(case, dict), f"missing case {case_name}")
        require(case.get("passed") is True, f"case did not pass: {case_name}")
        require(
            case.get("subject_returncode") == -9,
            f"{case_name}: subject did not terminate through SIGKILL",
        )

        action_id = str(case.get("action_id"))
        case_dir = args.work_dir / case_name
        receipt_db = case_dir / "receipt.sqlite"
        receiver_db = case_dir / "receiver.sqlite"

        require(receipt_db.exists(), f"{case_name}: receipt DB missing")
        require(receiver_db.exists(), f"{case_name}: receiver DB missing")
        integrity_check(receipt_db)
        integrity_check(receiver_db)

        records = read_receipt_rows(receipt_db, action_id)
        verify_record_chain(records)
        require(
            len(records) == expected["records"],
            f"{case_name}: receipt/reconciliation record count drift",
        )

        for record, expected_row in zip(records, expected["sequence"], strict=True):
            kind, availability, outcome, continuity = expected_row
            require(record["record_kind"] == kind, f"{case_name}: record kind drift")
            require(
                record["observation_availability"] == availability,
                f"{case_name}: availability drift",
            )
            require(
                record["external_outcome"] == outcome,
                f"{case_name}: external outcome drift",
            )
            require(record["continuity"] == continuity, f"{case_name}: continuity drift")

        pending = records[0]
        require(pending["externally_verified"] is False, f"{case_name}: PENDING verified itself")
        require(pending["effect_count"] is None, f"{case_name}: PENDING fabricated effect count")

        verifications = read_verifications(receipt_db, action_id)
        require(len(verifications) == 1, f"{case_name}: expected one fresh PENDING verification")
        require(
            verifications[0]["kind"] == "FRESH_PROCESS_PENDING_READ"
            and verifications[0]["verified"] is True,
            f"{case_name}: fresh PENDING verification missing",
        )
        require(
            verifications[0]["observed_record_sha256"] == pending["record_sha256"],
            f"{case_name}: fresh PENDING verifier saw different record",
        )

        receiver = read_receiver(receiver_db, action_id)
        require(
            len(receiver["attempts"]) == expected["attempts"],
            f"{case_name}: provider attempt count drift",
        )
        require(
            len(receiver["effects"]) == expected["effects"],
            f"{case_name}: external effect count drift",
        )

        for attempt in receiver["attempts"]:
            require(attempt["target"] == case["target"], f"{case_name}: attempt target drift")
            require(
                attempt["payload_digest"] == case["payload_digest"],
                f"{case_name}: attempt payload drift",
            )
        for effect in receiver["effects"]:
            require(effect["target"] == case["target"], f"{case_name}: effect target drift")
            require(
                effect["payload_digest"] == case["payload_digest"],
                f"{case_name}: effect payload drift",
            )
            require(effect["result"] == "effect-ok", f"{case_name}: effect result drift")

        if case_name == "crash_before_effect":
            require(
                len(receiver["verifications"]) == 0,
                "crash_before_effect should have no effect verification",
            )
            final = records[-1]
            require(final["externally_verified"] is True, "NO_EFFECT readback not verified")
            require(final["effect_count"] == 0, "NO_EFFECT count drift")
            require(
                final["recovery_decision"] == expected["recovery"],
                "NO_EFFECT recovery decision drift",
            )

        elif case_name == "effect_then_crash":
            require(
                len(receiver["verifications"]) == 1
                and receiver["verifications"][0]["verified"] is True
                and receiver["verifications"][0]["observed_effect_count"] == 1,
                "effect_then_crash missing fresh effect verification",
            )
            final = records[-1]
            require(final["externally_verified"] is True, "effect readback not verified")
            require(final["effect_count"] == 1, "confirmed effect count drift")
            require(
                final["recovery_decision"] == expected["recovery"],
                "confirmed-effect recovery decision drift",
            )

        else:
            require(
                len(receiver["verifications"]) == 1
                and receiver["verifications"][0]["verified"] is True,
                "unavailable fixture effect was not independently confirmed before kill",
            )
            first_recovery = records[1]
            require(
                first_recovery["externally_verified"] is False
                and first_recovery["effect_count"] is None,
                "UNAVAILABLE recovery leaked fixture effect knowledge",
            )
            require(
                first_recovery["recovery_decision"] == "HOLD_REVALIDATE_NO_REDISPATCH",
                "UNAVAILABLE recovery decision drift",
            )
            final = records[-1]
            require(final["externally_verified"] is True, "later full readback not verified")
            require(final["effect_count"] == 1, "later full readback effect count drift")
            require(
                final["recovery_decision"] == expected["recovery"],
                "later confirmed recovery decision drift",
            )

        before = case.get("before_recovery", {}).get("receiver", {})
        after = case.get("after_recovery", {}).get("receiver", {})
        require(
            before.get("attempt_count") == after.get("attempt_count") == 1,
            f"{case_name}: recovery redispatched provider",
        )
        require(
            before.get("effect_count") == after.get("effect_count"),
            f"{case_name}: recovery changed external effect cardinality",
        )

        verified_cases[case_name] = {
            "subject_sigkill": True,
            "durable_pending_fresh_read": True,
            "attempt_count": len(receiver["attempts"]),
            "effect_count": len(receiver["effects"]),
            "record_count": len(records),
            "final_continuity": records[-1]["continuity"],
            "final_decision": records[-1]["recovery_decision"],
        }

    result = {
        "system_case": SYSTEM_CASE,
        "status": "PASS",
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "finding": "DURABLE_PENDING_SURVIVES_SIGKILL_AND_RECOVERY_NEVER_REDISPATCHES_BLINDLY",
        "verified_cases": verified_cases,
        "invariants": [
            "PENDING was visible to a separate process before provider dispatch in every case.",
            "Each subject process died by SIGKILL before any local terminal receipt.",
            "Fresh recovery kept provider attempt count at exactly one.",
            "Verified matching effect finalized the existing action without redispatch.",
            "Verified NO_EFFECT required fresh authorization rather than automatic retry.",
            "UNAVAILABLE remained INDETERMINATE/REVALIDATE despite one retained fixture effect.",
            "Later FULL readback resolved the same action without creating a second effect.",
        ],
        "claim_ceiling":
            "Same-host SQLite process-crash proof only; no host power-loss durability, production provider, distributed consensus, recipient identity, or settlement binding.",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
