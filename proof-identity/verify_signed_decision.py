#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_KEYS = HERE / "keys.v0.3.json"

sys.path.insert(0, str(HERE))
from identity_crypto import (  # noqa: E402
    IdentityError,
    canonical_json_bytes,
    load_key_registry,
    require_key,
    sha256_hex,
    verify_ed25519,
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def unsigned_platform_payload(decision: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(decision)
    payload.pop("platform_signature", None)
    return payload


def verify_platform_signature(
    decision: dict[str, Any],
    key_registry_path: Path,
) -> dict[str, Any]:
    sig = decision.get("platform_signature")
    if not isinstance(sig, dict) or set(sig) != {
        "algorithm",
        "key_id",
        "payload_digest_sha256",
        "signature_b64",
    }:
        raise ValueError("missing or malformed platform_signature")
    if sig.get("algorithm") != "Ed25519":
        raise ValueError("unsupported platform signature algorithm")

    keys = load_key_registry(key_registry_path)
    try:
        key = require_key(
            keys,
            sig.get("key_id", ""),
            purpose="admission_decision",
        )
    except IdentityError as exc:
        raise ValueError(str(exc)) from exc

    payload_obj = unsigned_platform_payload(decision)
    payload = canonical_json_bytes(payload_obj)
    digest = sha256_hex(payload)
    if digest != sig.get("payload_digest_sha256"):
        raise ValueError(
            f"platform payload digest mismatch: expected {sig.get('payload_digest_sha256')}, got {digest}"
        )
    if not verify_ed25519(key["public_key_pem"], payload, sig.get("signature_b64", "")):
        raise ValueError("platform Ed25519 signature verification failed")

    core = copy.deepcopy(payload_obj)
    declared_envelope_digest = core.pop("envelope_digest_sha256", None)
    computed_envelope_digest = sha256_hex(canonical_json_bytes(core))
    if declared_envelope_digest != computed_envelope_digest:
        raise ValueError(
            f"envelope_digest_sha256 mismatch: expected {declared_envelope_digest}, got {computed_envelope_digest}"
        )

    return {
        "schema": "contractgraph.proof-identity-signature-verification.v0.3",
        "result": "PASS",
        "decision_status": decision.get("status"),
        "submission_id": decision.get("submission_id"),
        "platform_key_id": key["key_id"],
        "platform_key_spki_sha256": key["public_key_spki_sha256"],
        "platform_payload_digest_sha256": digest,
        "envelope_digest_sha256": computed_envelope_digest,
        "claim_ceiling": (
            "PASS proves that the registered platform key signed these exact admission-decision bytes. "
            "It does not establish claim truth, source authorship, certification, or production key custody."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", required=True)
    parser.add_argument("--key-registry", default=str(DEFAULT_KEYS))
    parser.add_argument("--expected-core")
    parser.add_argument("--write-report")
    args = parser.parse_args()

    decision = load_json(Path(args.decision))
    report = verify_platform_signature(decision, Path(args.key_registry))

    if args.expected_core:
        expected = load_json(Path(args.expected_core))
        actual_core = unsigned_platform_payload(decision)
        if actual_core != expected:
            raise SystemExit("signed decision core does not match regenerated identity-bound decision")

    encoded = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.write_report:
        Path(args.write_report).write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
