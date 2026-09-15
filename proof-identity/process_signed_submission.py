#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_KEYS = HERE / "keys.v0.3.json"
DEFAULT_PROFILES = REPO_ROOT / "proof-submissions" / "profiles.v0.2.json"
V02_PROCESSOR = REPO_ROOT / "proof-submissions" / "process_submission.py"

sys.path.insert(0, str(HERE))
from identity_crypto import (  # noqa: E402
    IdentityError,
    IdentityRegistryError,
    canonical_json_bytes,
    load_key_registry,
    require_key,
    sha256_hex,
    verify_ed25519,
)

SIGNED_SCHEMA = "contractgraph.external-proof-submission.v0.3"
ENVELOPE_SCHEMA = "contractgraph.proof-identity-decision.v0.3"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def load_v02_processor():
    spec = importlib.util.spec_from_file_location("cgqa_v02_submission", V02_PROCESSOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load v0.2 submission processor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finalize_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(envelope)
    core.pop("envelope_digest_sha256", None)
    core.pop("platform_signature", None)
    envelope["envelope_digest_sha256"] = sha256_hex(canonical_json_bytes(core))
    return envelope


def reject(
    status: str,
    submission: dict[str, Any],
    reason: str,
    **fields: Any,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "submission_id": submission.get("submission_id"),
        "status": status,
        "reason": reason,
        "proof_identity": fields.pop("proof_identity", None),
        "admission_decision": None,
        "claim_ceiling": (
            "Identity-layer rejection only. No evidence or claim truth is established by this decision."
        ),
        **fields,
    }
    return finalize_envelope(envelope)


def validate_signed_shape(submission: dict[str, Any]) -> None:
    if submission.get("schema") != SIGNED_SCHEMA:
        raise ValueError(f"unsupported signed submission schema: {submission.get('schema')!r}")
    required = {
        "schema",
        "submission_id",
        "submitted_by",
        "protocol_namespace",
        "verification_profile",
        "source",
        "requested_claims",
        "non_claims",
        "signature",
    }
    missing = sorted(required - set(submission))
    extra = sorted(set(submission) - required)
    if missing:
        raise ValueError(f"missing signed submission fields: {missing}")
    if extra:
        raise ValueError(f"unknown signed submission fields: {extra}")
    sig = submission.get("signature")
    if not isinstance(sig, dict) or set(sig) != {
        "algorithm",
        "key_id",
        "payload_digest_sha256",
        "signature_b64",
    }:
        raise ValueError("signature must contain exactly algorithm, key_id, payload_digest_sha256, signature_b64")


def verify_submission_identity(
    submission: dict[str, Any],
    key_registry_path: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        validate_signed_shape(submission)
    except ValueError as exc:
        return None, reject("REJECTED_SCHEMA", submission, str(exc))

    try:
        keys = load_key_registry(key_registry_path)
    except IdentityRegistryError:
        raise

    sig = submission["signature"]
    if sig.get("algorithm") != "Ed25519":
        return None, reject(
            "REJECTED_SIGNATURE",
            submission,
            "unsupported signature algorithm",
        )

    try:
        key = require_key(
            keys,
            sig.get("key_id", ""),
            purpose="external_submission",
            identity=submission.get("submitted_by"),
        )
    except IdentityError as exc:
        return None, reject(
            "REJECTED_IDENTITY",
            submission,
            str(exc),
            proof_identity={
                "signature_verified": False,
                "key_id": sig.get("key_id"),
            },
        )

    unsigned = copy.deepcopy(submission)
    unsigned.pop("signature", None)
    payload = canonical_json_bytes(unsigned)
    payload_digest = sha256_hex(payload)
    if payload_digest != sig.get("payload_digest_sha256"):
        return None, reject(
            "REJECTED_SIGNATURE",
            submission,
            "signed payload digest mismatch",
            proof_identity={
                "signature_verified": False,
                "key_id": key["key_id"],
                "public_key_spki_sha256": key["public_key_spki_sha256"],
                "computed_payload_digest_sha256": payload_digest,
            },
        )

    if not verify_ed25519(key["public_key_pem"], payload, sig.get("signature_b64", "")):
        return None, reject(
            "REJECTED_SIGNATURE",
            submission,
            "Ed25519 signature verification failed",
            proof_identity={
                "signature_verified": False,
                "key_id": key["key_id"],
                "public_key_spki_sha256": key["public_key_spki_sha256"],
                "payload_digest_sha256": payload_digest,
            },
        )

    identity = {
        "signature_verified": True,
        "algorithm": "Ed25519",
        "key_id": key["key_id"],
        "public_key_spki_sha256": key["public_key_spki_sha256"],
        "registered_identity": key["identity"],
        "manifest_payload_digest_sha256": payload_digest,
        "source_repository": submission["source"]["repository"],
        "source_authorship_attested_by_signature": False,
        "identity_claim_ceiling": key["claim_ceiling"],
    }
    return identity, None


def process_signed_submission(
    submission: dict[str, Any],
    *,
    key_registry_path: Path,
    profiles_path: Path,
    source_file: str | None,
) -> dict[str, Any]:
    proof_identity, identity_rejection = verify_submission_identity(submission, key_registry_path)
    if identity_rejection is not None:
        return identity_rejection
    assert proof_identity is not None

    v02 = load_v02_processor()
    base = copy.deepcopy(submission)
    base.pop("signature", None)
    base["schema"] = "contractgraph.external-proof-submission.v0.2"
    admission = v02.process_submission(base, profiles_path, source_file)

    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "submission_id": submission["submission_id"],
        "status": admission.get("status"),
        "proof_identity": proof_identity,
        "admission_decision": admission,
        "claim_ceiling": (
            "The submission signature proves possession of the registered Ed25519 private key "
            "for the exact manifest bytes. The nested admission decision retains its own evidence "
            "and claim ceiling. Neither signature nor admission proves real-world identity, source "
            "authorship, key-custody quality, claim truth, certification, or automatic registry ownership."
        ),
    }
    return finalize_envelope(envelope)


def write_json(payload: dict[str, Any], path: str | None) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if path:
        Path(path).write_text(encoded, encoding="utf-8")
    sys.stdout.write(encoded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", required=True)
    parser.add_argument("--key-registry", default=str(DEFAULT_KEYS))
    parser.add_argument("--profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--source-file")
    parser.add_argument("--write-decision")
    args = parser.parse_args()

    submission = load_json(Path(args.submission))
    decision = process_signed_submission(
        submission,
        key_registry_path=Path(args.key_registry),
        profiles_path=Path(args.profiles),
        source_file=args.source_file,
    )
    write_json(decision, args.write_decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
