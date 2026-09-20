from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "contractgraph.astra-signed-derived-field-contradiction.v0.1"
FIXTURE_SCHEMA = "contractgraph.astra-signed-derived-field-fixture.v0.1"
ISSUE = "https://github.com/safal207/ContractGraph-QA/issues/196"
SPINE_REF = "contractgraph.astra-crash-retry.issue-196"
HERE = Path(__file__).resolve().parent
PUBLIC_KEY = HERE / "fixture_ed25519_public.pem"
FIXTURES = (
    HERE / "fixtures" / "control-consistent.json",
    HERE / "fixtures" / "signed-settled-contradiction.json",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_ed25519(payload: dict[str, Any], signature_b64: str) -> bool:
    signature = base64.b64decode(signature_b64, validate=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        payload_path = tmp / "payload.bin"
        signature_path = tmp / "signature.bin"
        payload_path.write_bytes(canonical_bytes(payload))
        signature_path.write_bytes(signature)
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(PUBLIC_KEY),
                "-rawin",
                "-in",
                str(payload_path),
                "-sigfile",
                str(signature_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    return completed.returncode == 0


def recompute_derived(primary: dict[str, Any]) -> dict[str, bool]:
    settled = primary.get("finality") == "FINAL"
    delivered = primary.get("delivery") == "DELIVERED"
    reconciled = settled and delivered and primary.get("receipt_binding") == "BOUND"
    return {
        "settled": settled,
        "delivered": delivered,
        "reconciled": reconciled,
    }


def reference_verdict(
    *,
    signature_valid: bool,
    payload: dict[str, Any],
) -> tuple[str, dict[str, bool]]:
    if not signature_valid:
        return "FAIL_SIGNATURE_INVALID", {}
    if payload.get("schema") != FIXTURE_SCHEMA:
        return "FAIL_SCHEMA_MISMATCH", {}
    primary = payload.get("primary")
    derived = payload.get("derived")
    if not isinstance(primary, dict) or not isinstance(derived, dict):
        return "FAIL_SCHEMA_MISMATCH", {}
    expected = recompute_derived(primary)
    if derived != expected:
        return "FAIL_SIGNED_DERIVED_FIELD_CONTRADICTION", expected
    return "PASS_AUTHENTICATED_SEMANTICALLY_CONSISTENT", expected


def signature_only_mutant(*, signature_valid: bool) -> str:
    return "ACCEPT" if signature_valid else "REJECT"


def evaluate_fixture(path: Path) -> dict[str, Any]:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    payload = envelope["payload"]
    signature = envelope["signature"]

    signature_valid = (
        signature.get("alg") == "Ed25519"
        and signature.get("key_id") == "astra-fixture-ed25519-v0.1"
        and verify_ed25519(payload, signature["signature_b64"])
    )
    verdict, recomputed = reference_verdict(
        signature_valid=signature_valid,
        payload=payload,
    )
    mutant = signature_only_mutant(signature_valid=signature_valid)

    expected_reference = {
        "control-consistent": "PASS_AUTHENTICATED_SEMANTICALLY_CONSISTENT",
        "signed-settled-contradiction": "FAIL_SIGNED_DERIVED_FIELD_CONTRADICTION",
    }[payload["case"]]

    passed = signature_valid and verdict == expected_reference and mutant == "ACCEPT"

    return {
        "case": payload["case"],
        "logical_action_id": payload["logical_action_id"],
        "fixture_sha256": sha256_bytes(path.read_bytes()),
        "canonical_payload_sha256": sha256_bytes(canonical_bytes(payload)),
        "signature_valid": signature_valid,
        "primary": payload["primary"],
        "derived_claim": payload["derived"],
        "recomputed_derived": recomputed,
        "reference_verdict": verdict,
        "signature_only_mutant_verdict": mutant,
        "passed": passed,
    }


def build_report() -> dict[str, Any]:
    cases = [evaluate_fixture(path) for path in FIXTURES]
    bad_case = next(
        case for case in cases if case["case"] == "signed-settled-contradiction"
    )

    return {
        "schema": SCHEMA,
        "spine_ref": SPINE_REF,
        "issue": ISSUE,
        "exact_subject": {
            "kind": "synthetic_authenticated_economic_record",
            "fixture_schema": FIXTURE_SCHEMA,
            "signature_scheme": "Ed25519",
            "verification_backend": "OpenSSL pkeyutl",
            "public_key_sha256": sha256_bytes(PUBLIC_KEY.read_bytes()),
        },
        "invariant": (
            "A cryptographically valid record must not be accepted as economic truth "
            "when deterministic derived fields contradict the primary evidence."
        ),
        "cases": cases,
        "total_cases": len(cases),
        "passed_cases": sum(1 for case in cases if case["passed"]),
        "mutant_discrimination": {
            "mutant": "signature_only_acceptance",
            "total_mutants": 1,
            "detected_mutants": int(
                bad_case["signature_only_mutant_verdict"] == "ACCEPT"
                and bad_case["reference_verdict"]
                == "FAIL_SIGNED_DERIVED_FIELD_CONTRADICTION"
            ),
        },
        "result": "PASS" if all(case["passed"] for case in cases) else "FAIL",
        "non_claims": [
            "This fixture does not prove the correctness or security of Ed25519 or OpenSSL.",
            "This fixture does not verify a live x402, AP2, MPP, wallet, facilitator, or merchant receipt.",
            "This fixture does not prove that any real payment settled or any resource was delivered.",
            "A PASS proves only that this verifier rejects a validly signed semantic contradiction in the frozen synthetic corpus.",
        ],
        "learning_decision": "PROMOTE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()

    report = build_report()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"

    if args.write_report:
        args.write_report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
