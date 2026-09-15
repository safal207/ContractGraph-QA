#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class IdentityError(ValueError):
    pass


class IdentityRegistryError(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_key_registry(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != "contractgraph.proof-identity-keys.v0.3":
        raise IdentityRegistryError("unsupported proof identity key-registry schema")
    rows = payload.get("keys")
    if not isinstance(rows, list):
        raise IdentityRegistryError("key registry must contain a keys list")

    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise IdentityRegistryError("key entry must be an object")
        key_id = row.get("key_id")
        if not isinstance(key_id, str) or not key_id:
            raise IdentityRegistryError("key entry is missing key_id")
        if key_id in out:
            raise IdentityRegistryError(f"duplicate key_id: {key_id}")
        if row.get("algorithm") != "Ed25519":
            raise IdentityRegistryError(f"{key_id}: unsupported algorithm")
        if row.get("status") not in {"active", "revoked", "disabled"}:
            raise IdentityRegistryError(f"{key_id}: unsupported status")
        purposes = row.get("purposes")
        if not isinstance(purposes, list) or not purposes or any(not isinstance(v, str) for v in purposes):
            raise IdentityRegistryError(f"{key_id}: malformed purposes")
        identity = row.get("identity")
        if not isinstance(identity, dict) or set(identity) != {"kind", "id"}:
            raise IdentityRegistryError(f"{key_id}: malformed identity binding")
        pem = row.get("public_key_pem")
        expected_fp = row.get("public_key_spki_sha256")
        if not isinstance(pem, str) or not pem.startswith("-----BEGIN PUBLIC KEY-----"):
            raise IdentityRegistryError(f"{key_id}: malformed public key PEM")
        if not isinstance(expected_fp, str) or len(expected_fp) != 64:
            raise IdentityRegistryError(f"{key_id}: malformed SPKI fingerprint")
        actual_fp = public_key_spki_sha256(pem)
        if actual_fp != expected_fp:
            raise IdentityRegistryError(
                f"{key_id}: public-key fingerprint mismatch: expected {expected_fp}, got {actual_fp}"
            )
        out[key_id] = row
    return out


def public_key_spki_sha256(public_key_pem: str) -> str:
    with tempfile.TemporaryDirectory(prefix="cgqa-ed25519-pub-") as tmp:
        pub = Path(tmp) / "pub.pem"
        pub.write_text(public_key_pem, encoding="utf-8")
        completed = subprocess.run(
            ["openssl", "pkey", "-pubin", "-in", str(pub), "-outform", "DER"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise IdentityRegistryError(
                "OpenSSL could not parse public key: "
                + completed.stderr.decode("utf-8", errors="replace")[-2000:]
            )
        return hashlib.sha256(completed.stdout).hexdigest()


def verify_ed25519(public_key_pem: str, payload: bytes, signature_b64: str) -> bool:
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False

    with tempfile.TemporaryDirectory(prefix="cgqa-ed25519-verify-") as tmp:
        tmp_path = Path(tmp)
        pub = tmp_path / "pub.pem"
        message = tmp_path / "payload.bin"
        signature_path = tmp_path / "signature.bin"
        pub.write_text(public_key_pem, encoding="utf-8")
        message.write_bytes(payload)
        signature_path.write_bytes(signature)
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(pub),
                "-rawin",
                "-in",
                str(message),
                "-sigfile",
                str(signature_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return completed.returncode == 0


def sign_ed25519(private_key_path: Path, payload: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="cgqa-ed25519-sign-") as tmp:
        tmp_path = Path(tmp)
        message = tmp_path / "payload.bin"
        signature_path = tmp_path / "signature.bin"
        message.write_bytes(payload)
        completed = subprocess.run(
            [
                "openssl",
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key_path),
                "-rawin",
                "-in",
                str(message),
                "-out",
                str(signature_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise IdentityError(
                "OpenSSL signing failed: "
                + completed.stderr.decode("utf-8", errors="replace")[-2000:]
            )
        return base64.b64encode(signature_path.read_bytes()).decode("ascii")


def private_key_public_fingerprint(private_key_path: Path) -> str:
    completed = subprocess.run(
        ["openssl", "pkey", "-in", str(private_key_path), "-pubout", "-outform", "DER"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise IdentityError(
            "OpenSSL could not derive public key from private key: "
            + completed.stderr.decode("utf-8", errors="replace")[-2000:]
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def require_key(
    keys: dict[str, dict[str, Any]],
    key_id: str,
    *,
    purpose: str,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = keys.get(key_id)
    if row is None:
        raise IdentityError(f"unknown key_id: {key_id}")
    if row.get("status") != "active":
        raise IdentityError(f"key is not active: {key_id}")
    if purpose not in row.get("purposes", []):
        raise IdentityError(f"key is not authorized for purpose {purpose}: {key_id}")
    if identity is not None and row.get("identity") != identity:
        raise IdentityError(
            f"key identity binding mismatch: key={row.get('identity')!r}, submission={identity!r}"
        )
    return row
