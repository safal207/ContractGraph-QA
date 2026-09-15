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
    private_key_public_fingerprint,
    require_key,
    sha256_hex,
    sign_ed25519,
)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", required=True, help="Unsigned identity-bound decision envelope")
    parser.add_argument("--private-key", required=True, help="External Ed25519 private-key PEM; never commit it")
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--key-registry", default=str(DEFAULT_KEYS))
    parser.add_argument("--write-signed", required=True)
    args = parser.parse_args()

    decision = load_json(Path(args.decision))
    if "platform_signature" in decision:
        raise SystemExit("decision is already signed")

    keys = load_key_registry(Path(args.key_registry))
    try:
        key = require_key(keys, args.key_id, purpose="admission_decision")
    except IdentityError as exc:
        raise SystemExit(str(exc)) from exc

    private_path = Path(args.private_key)
    actual_fp = private_key_public_fingerprint(private_path)
    if actual_fp != key["public_key_spki_sha256"]:
        raise SystemExit(
            f"private key does not match registered platform public key: expected "
            f"{key['public_key_spki_sha256']}, got {actual_fp}"
        )

    payload = canonical_json_bytes(decision)
    signed = copy.deepcopy(decision)
    signed["platform_signature"] = {
        "algorithm": "Ed25519",
        "key_id": key["key_id"],
        "payload_digest_sha256": sha256_hex(payload),
        "signature_b64": sign_ed25519(private_path, payload),
    }
    Path(args.write_signed).write_text(
        json.dumps(signed, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
