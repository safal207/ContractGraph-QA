#!/usr/bin/env python3
"""Independent scorer for Attenu observer-envelope vectors v1.1.

The verifier deliberately does not import ``attenu_guard``. It reuses the
repository's previously published standalone bundle-v1.2 scorer for the base
ledger/authority/execution checks, then implements envelope-v1 verification
locally: exact member sets, entry-hash binding, locator checks, raw-wire JCS,
Ed25519 witness verification, duplicate-subject handling, and per-entry state.

The result is evidence about one frozen 18-case corpus. It is not proof of
capture completeness, witness availability, deployment non-bypassability,
upstream correctness, or A2A adoption.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

VERIFIER_ID = "safal207-independent-envelope-v1.1"
VERIFIER_VERSION = "0.1.0"
UPSTREAM_REPOSITORY = "attenu-io/attenu-guard"
UPSTREAM_COMMIT = "f34a351c12ddc08e9c8bd3beca9da4695a46376f"
VECTOR_PATH = "tests/vectors/envelopes/envelope_vectors_v1.json"
VECTOR_CONTRACT = "envelope_vectors_v1"
VECTOR_REVISION = "envelope_vectors_v1.1"
PINNED_VECTOR_SHA256 = "6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64"
PYPI_PACKAGE = "attenu-guard==0.13.0"
NPM_PACKAGE = "attenu-guard@0.8.0"

CASE_NAMES = [
    "valid_spawn_envelope",
    "valid_allow_envelope",
    "valid_jcs_reorder",
    "absent_envelope",
    "indeterminate_result",
    "reject_rehashed_chain_sparse",
    "reject_subject_mismatch",
    "reject_bad_signature",
    "reject_unknown_version",
    "reject_non_canonical",
    "reject_member_without_bump",
    "reject_masked_bundle_mutation",
    "reject_rehashed_chain_anchored",
    "reject_rehashed_chain_unanchored",
    "reject_unknown_witness",
    "reject_locator_mismatch",
    "reject_duplicate_subject",
    "reject_unknown_alg",
]
ACCEPT_CASES = frozenset(CASE_NAMES[:5])

ENVELOPE_VERSION = 1
ENVELOPE_TYP = "delegation-event-observation"
ENVELOPE_ALG = "EdDSA"
ENVELOPE_MEMBERS = frozenset({"v", "typ", "subject", "observed", "witness", "sig"})
SUBJECT_MEMBERS = {
    "spawn": frozenset({"chain_id", "node", "seq", "entry_hash", "event"}),
    "allow": frozenset({"chain_id", "node", "seq", "entry_hash", "event", "call_id"}),
}
OBSERVED_MEMBERS = frozenset({"result", "at", "method"})
WITNESS_MEMBERS = frozenset({"kid", "alg"})
ENVELOPE_FAILURES = (
    "envelope_unknown_version",
    "envelope_unknown_member",
    "envelope_subject_mismatch",
    "envelope_duplicate_subject",
    "envelope_non_canonical",
    "envelope_unknown_witness",
    "envelope_bad_signature",
)
WITNESS_SIGNED = "witness-signed"
PROCESS_ASSERTED = "process-asserted"
GENESIS = "0" * 64
MAX_SAFE_INTEGER = 2**53 - 1


class DuplicateMember(ValueError):
    """Raised when strict JSON parsing sees the same member twice."""


class UnsupportedCanonicalValue(ValueError):
    """Raised when a value is outside this verifier's explicit JCS profile."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMember(f"duplicate JSON member: {key!r}")
        out[key] = value
    return out


def load_json_strict(raw: bytes) -> Any:
    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON number: {token}")
        ),
    )


def _validate_string(value: str) -> None:
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise UnsupportedCanonicalValue("lone UTF-16 surrogate")


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def jcs_bytes(value: Any) -> bytes:
    """RFC 8785-compatible bytes for the published corpus profile.

    The frozen vectors use null, booleans, safe integers, strings, arrays and
    objects. Floats and unsafe integers fail closed instead of being formatted
    by a non-ECMAScript number renderer.
    """

    def encode(item: Any) -> str:
        if item is None:
            return "null"
        if item is True:
            return "true"
        if item is False:
            return "false"
        if isinstance(item, int) and not isinstance(item, bool):
            if abs(item) > MAX_SAFE_INTEGER:
                raise UnsupportedCanonicalValue(f"unsafe integer: {item}")
            return str(item)
        if isinstance(item, float):
            raise UnsupportedCanonicalValue("float outside frozen-corpus JCS profile")
        if isinstance(item, str):
            _validate_string(item)
            return json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        if isinstance(item, dict):
            for key in item:
                if not isinstance(key, str):
                    raise UnsupportedCanonicalValue("non-string object key")
                _validate_string(key)
            keys = sorted(item, key=_utf16_sort_key)
            return "{" + ",".join(
                encode(key) + ":" + encode(item[key]) for key in keys
            ) + "}"
        raise UnsupportedCanonicalValue(f"unsupported JSON type: {type(item).__name__}")

    return encode(value).encode("utf-8")


@dataclass(frozen=True)
class Failure:
    reason: str
    seq: int | None
    node: str | None
    detail: str

    def score_key(self) -> dict[str, Any]:
        return {"reason": self.reason, "seq": self.seq, "node": self.node}


def _is_json_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _position(subject: Any, by_seq: Mapping[int, Mapping[str, Any]]) -> tuple[int | None, str | None]:
    seq = subject.get("seq") if isinstance(subject, Mapping) else None
    if not _is_json_integer(seq):
        return None, None
    entry = by_seq.get(seq)
    if entry is None:
        return seq, None
    return entry.get("seq"), entry.get("node")


def _add_failure(
    failures: list[Failure],
    reason: str,
    detail: str,
    subject: Any,
    by_seq: Mapping[int, Mapping[str, Any]],
) -> None:
    seq, node = _position(subject, by_seq)
    failures.append(Failure(reason, seq, node, detail))


def _recomputed_hashes(entries: Sequence[Any]) -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    previous = GENESIS
    for position, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            out[position] = None
            previous = GENESIS
            continue
        payload = {key: value for key, value in raw_entry.items() if key != "hash"}
        try:
            computed = hashlib.sha256(
                previous.encode("ascii") + jcs_bytes(payload)
            ).hexdigest()
        except Exception:
            computed = None
        seq = raw_entry.get("seq", position)
        if _is_json_integer(seq):
            out[seq] = computed
        previous = computed if computed is not None else GENESIS
    return out


def _trusted_witnesses(rows: Any) -> dict[str, bytes]:
    if not isinstance(rows, list):
        raise ValueError("witness_keys must be a list")
    trusted: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("witness key row must be an object")
        if set(row) != {"kid", "alg", "public_key_hex"}:
            raise ValueError(f"unexpected witness key members: {sorted(row)}")
        kid = row.get("kid")
        if not isinstance(kid, str) or not kid:
            raise ValueError("witness key kid must be a non-empty string")
        if row.get("alg") != ENVELOPE_ALG:
            raise ValueError(f"witness key {kid!r} is not EdDSA")
        value = row.get("public_key_hex")
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"witness key {kid!r} is not 32-byte hex")
        try:
            public = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(f"witness key {kid!r} is not hexadecimal") from exc
        if len(public) != 32 or kid in trusted:
            raise ValueError(f"invalid or duplicate witness key {kid!r}")
        trusted[kid] = public
    return trusted


def _score_envelope(
    envelope: Any,
    index: int,
    by_seq: Mapping[int, Mapping[str, Any]],
    recomputed: Mapping[int, str | None],
    trusted: Mapping[str, bytes],
    raw_received: bytes | None,
    claims: dict[int, int],
    failures: list[Failure],
) -> tuple[int | None, str | None]:
    if not isinstance(envelope, Mapping):
        failures.append(Failure(
            "envelope_unknown_version", None, None,
            f"envelope #{index} is not a JSON object",
        ))
        return None, None

    subject = envelope.get("subject")

    if (
        not _is_json_integer(envelope.get("v"))
        or envelope.get("v") != ENVELOPE_VERSION
        or envelope.get("typ") != ENVELOPE_TYP
    ):
        _add_failure(
            failures,
            "envelope_unknown_version",
            f"unknown v/typ at envelope #{index}",
            subject,
            by_seq,
        )
        return None, None

    for label, value, expected in (
        ("envelope", envelope, ENVELOPE_MEMBERS),
        ("observed", envelope.get("observed"), OBSERVED_MEMBERS),
        ("witness", envelope.get("witness"), WITNESS_MEMBERS),
    ):
        if not isinstance(value, Mapping) or set(value) != expected:
            _add_failure(
                failures,
                "envelope_unknown_member",
                f"{label} member set does not match envelope v1",
                subject,
                by_seq,
            )
            return None, None

    if not isinstance(subject, Mapping):
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "subject is not a JSON object",
            subject,
            by_seq,
        )
        return None, None
    event = subject.get("event")
    if not isinstance(event, str) or event not in SUBJECT_MEMBERS:
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "subject event is not one envelope v1 defines",
            subject,
            by_seq,
        )
        return None, None
    expected_subject = SUBJECT_MEMBERS[event]
    if set(subject) - expected_subject:
        _add_failure(
            failures,
            "envelope_unknown_member",
            "subject contains a member outside the selected v1 shape",
            subject,
            by_seq,
        )
        return None, None
    if expected_subject - set(subject):
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "subject omits a required member",
            subject,
            by_seq,
        )
        return None, None

    seq = subject.get("seq")
    if not _is_json_integer(seq):
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "subject seq is not a JSON integer",
            subject,
            by_seq,
        )
        return None, None
    entry = by_seq.get(seq)
    if entry is None:
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "subject seq names no entry in this bundle",
            subject,
            by_seq,
        )
        return None, None

    already = claims.get(seq, 0)
    claims[seq] = already + 1
    if already:
        _add_failure(
            failures,
            "envelope_duplicate_subject",
            "an earlier envelope already claimed this entry",
            subject,
            by_seq,
        )
        return None, None

    if subject.get("entry_hash") != recomputed.get(seq):
        _add_failure(
            failures,
            "envelope_subject_mismatch",
            "entry_hash does not match the value recomputed from this bundle",
            subject,
            by_seq,
        )
        return None, None

    locators = (
        ("chain_id", entry.get("chain_id")),
        ("node", entry.get("node")),
        ("event", entry.get("event")),
    )
    if event == "allow":
        locators += (("call_id", entry.get("call_id")),)
    for member, actual in locators:
        if subject.get(member) != actual:
            _add_failure(
                failures,
                "envelope_subject_mismatch",
                f"locator {member} disagrees with the entry seq found",
                subject,
                by_seq,
            )
            return None, None

    non_canonical = False
    if raw_received is not None:
        try:
            canonical_full = jcs_bytes(dict(envelope))
        except UnsupportedCanonicalValue as exc:
            _add_failure(
                failures,
                "envelope_non_canonical",
                f"envelope cannot be canonicalized: {exc}",
                subject,
                by_seq,
            )
            return None, None
        if raw_received != canonical_full:
            non_canonical = True
            _add_failure(
                failures,
                "envelope_non_canonical",
                "received bytes are not JCS of the parsed envelope",
                subject,
                by_seq,
            )

    witness = envelope["witness"]
    kid = witness.get("kid")
    alg = witness.get("alg")
    if not isinstance(kid, str) or alg != ENVELOPE_ALG or kid not in trusted:
        _add_failure(
            failures,
            "envelope_unknown_witness",
            "witness kid/alg is outside the trusted Ed25519 set",
            subject,
            by_seq,
        )
        return None, None

    signature_hex = envelope.get("sig")
    try:
        signature = bytes.fromhex(signature_hex) if isinstance(signature_hex, str) else b""
        signing_input = jcs_bytes({k: v for k, v in envelope.items() if k != "sig"})
        Ed25519PublicKey.from_public_bytes(trusted[kid]).verify(signature, signing_input)
        signature_ok = True
    except (ValueError, InvalidSignature, UnsupportedCanonicalValue):
        signature_ok = False

    if not signature_ok:
        _add_failure(
            failures,
            "envelope_bad_signature",
            "signature does not verify under witness.kid",
            subject,
            by_seq,
        )
        return None, None
    if non_canonical:
        return None, None
    return seq, envelope["observed"].get("result")


def verify_envelopes(case: Mapping[str, Any]) -> tuple[list[Failure], dict[str, str]]:
    bundle = case.get("bundle")
    if not isinstance(bundle, Mapping):
        raise ValueError("case.bundle must be an object")
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        raise ValueError("bundle.entries must be a list")

    states: dict[int, str] = {}
    by_seq: dict[int, Mapping[str, Any]] = {}
    for position, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            continue
        seq = entry.get("seq", position)
        if _is_json_integer(seq):
            states[seq] = PROCESS_ASSERTED
            by_seq[seq] = entry

    envelopes = bundle.get("envelopes") or []
    if not isinstance(envelopes, list):
        raise ValueError("bundle.envelopes must be a list when present")
    recomputed = _recomputed_hashes(entries) if envelopes else {}
    trusted = _trusted_witnesses(case.get("witness_keys"))
    failures: list[Failure] = []
    claims: dict[int, int] = {}

    raw_hex = case.get("raw_hex")
    raw_rows: list[bytes | None] = []
    if raw_hex is not None:
        if not isinstance(raw_hex, str):
            raise ValueError("raw_hex must be a hex string")
        try:
            raw_rows = [bytes.fromhex(raw_hex)]
        except ValueError as exc:
            raise ValueError("raw_hex is not hexadecimal") from exc

    for index, envelope in enumerate(envelopes):
        raw = raw_rows[index] if index < len(raw_rows) else None
        seq, _result = _score_envelope(
            envelope,
            index,
            by_seq,
            recomputed,
            trusted,
            raw,
            claims,
            failures,
        )
        if seq is not None:
            states[seq] = WITNESS_SIGNED

    for seq, count in claims.items():
        if count > 1:
            states[seq] = PROCESS_ASSERTED

    return failures, {str(seq): state for seq, state in sorted(states.items())}


def _load_base_verifier(repository_root: Path):
    path = (
        repository_root
        / "proofs"
        / "attenu-guard-v0.12.1-independent"
        / "independent_bundle_verifier.py"
    )
    if not path.is_file():
        raise FileNotFoundError(f"base verifier not found: {path}")
    name = "cgqa_independent_bundle_v12"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _with_synthetic_anchor(bundle: Mapping[str, Any], base_module) -> tuple[dict[str, Any], dict[str, str]]:
    """Add a local-only anchor for subordinate checks on the no-anchor row."""
    copied = copy.deepcopy(dict(bundle))
    entries = copied.get("entries") or []
    kid = "local-unanchored-base-check"
    secret_hex = "4c6f63616c206261736520636865636b206f6e6c79202d206e6f74206576696465"
    body = {
        "v": copied.get("v"),
        "c14n": "JCS",
        "chain_id": copied.get("chain_id"),
        "seq": entries[-1].get("seq") if entries else -1,
        "head": entries[-1].get("hash") if entries else "GENESIS",
        "ts": 0,
    }
    secret = bytes.fromhex(secret_hex)
    signature = hmac.new(secret, base_module.jcs_bytes(body), hashlib.sha256).hexdigest()
    copied["anchor"] = {**body, "kid": kid, "sig": signature, "verified": True}
    signer = {"alg": "HS256", "kid": kid, "secret_hex": secret_hex}
    return copied, signer


def verify_base(case: Mapping[str, Any], base_module) -> list[Failure]:
    bundle = case.get("bundle")
    signer = case.get("signer")
    if signer is None:
        if not isinstance(bundle, Mapping) or "anchor" in bundle:
            raise ValueError("the unanchored corpus row must omit both signer and anchor")
        checked_bundle, checked_signer = _with_synthetic_anchor(bundle, base_module)
    else:
        checked_bundle, checked_signer = bundle, signer
    base_failures = base_module.verify_bundle(checked_bundle, checked_signer)
    return [Failure(f.reason, f.seq, f.node, f.detail) for f in base_failures]


def _case_result(case: Mapping[str, Any], base_module) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    name = case.get("name")
    if not isinstance(name, str):
        raise ValueError("case.name must be a string")

    base_failures = verify_base(case, base_module)
    envelope_failures, states = verify_envelopes(case)
    all_failures = [*base_failures, *envelope_failures]
    observed = "reject" if all_failures else "accept"
    expected = case.get("expect")

    if observed != expected:
        errors.append(f"verdict: expected {expected!r}, observed {observed!r}")

    reported = [failure.score_key() for failure in all_failures]
    required = case.get("expect_failures")
    if not isinstance(required, list):
        raise ValueError(f"{name}: expect_failures must be a list")
    missing = [item for item in required if item not in reported]
    if missing:
        errors.append(f"required failures missing: {missing}")

    expected_states = case.get("expect_states")
    if states != expected_states:
        errors.append(f"states differ: expected {expected_states}, observed {states}")

    if expected == "accept" and all_failures:
        errors.append(f"accept row emitted failures: {reported}")

    covered = {
        env.get("subject", {}).get("seq")
        for env in (case.get("bundle", {}).get("envelopes") or [])
        if isinstance(env, Mapping)
        and isinstance(env.get("subject"), Mapping)
        and _is_json_integer(env["subject"].get("seq"))
    }
    misplaced = [
        failure.score_key()
        for failure in envelope_failures
        if failure.seq not in covered
    ]
    if misplaced:
        errors.append(f"envelope failures outside claimed coverage: {misplaced}")

    if name == "valid_jcs_reorder":
        envelope = case["bundle"]["envelopes"][0]
        actual = jcs_bytes({k: v for k, v in envelope.items() if k != "sig"}).hex()
        if actual != case.get("canonical_hex"):
            errors.append("canonical_hex does not equal the independently built signing input")
    if name == "reject_non_canonical":
        raw = bytes.fromhex(case["raw_hex"])
        envelope = case["bundle"]["envelopes"][0]
        try:
            parsed = load_json_strict(raw)
        except Exception as exc:
            errors.append(f"raw_hex does not parse: {exc}")
        else:
            if parsed != envelope:
                errors.append("raw_hex parses to a different envelope")
            if raw == jcs_bytes(envelope):
                errors.append("raw_hex is canonical and therefore not a negative control")
    if name == "absent_envelope" and "envelopes" in case.get("bundle", {}):
        errors.append("absent_envelope unexpectedly carries an envelopes member")
    if name == "reject_rehashed_chain_unanchored":
        if case.get("signer") is not None or "anchor" in case.get("bundle", {}):
            errors.append("unanchored row unexpectedly carries signer or anchor")

    assertions = {
        "verdict": observed == expected,
        "minimal_failures": not missing,
        "entry_states": states == expected_states,
        "failure_position_rule": not misplaced,
    }
    return {
        "name": name,
        "expected": expected,
        "observed": observed,
        "assertions": assertions,
        "status": "AGREE" if not errors else "DISAGREE",
    }, errors


def build_report(
    vector_path: Path,
    python_vector: Path | None,
    npm_vector: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    source_bytes = vector_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != PINNED_VECTOR_SHA256:
        errors.append(
            f"source vector SHA-256 mismatch: expected {PINNED_VECTOR_SHA256}, got {source_sha}"
        )

    copies = [
        {
            "source": f"{UPSTREAM_REPOSITORY}@{UPSTREAM_COMMIT}:{VECTOR_PATH}",
            "sha256": source_sha,
        }
    ]
    for label, path in (
        (f"PyPI {PYPI_PACKAGE}", python_vector),
        (f"npm {NPM_PACKAGE}", npm_vector),
    ):
        if path is None:
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        copies.append({"source": label, "sha256": digest})
        if raw != source_bytes:
            errors.append(f"{label} vector bytes differ from the pinned repository copy")

    document = load_json_strict(source_bytes)
    if not isinstance(document, dict):
        raise ValueError("vector document must be an object")
    if document.get("version") != VECTOR_CONTRACT:
        errors.append(f"vector contract is {document.get('version')!r}")
    if document.get("revision") != VECTOR_REVISION:
        errors.append(f"vector revision is {document.get('revision')!r}")
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("vector document cases must be a list")
    names = [case.get("name") if isinstance(case, dict) else None for case in cases]
    if names != CASE_NAMES:
        errors.append(f"case order/name set differs: {names}")

    repository_root = Path(__file__).resolve().parents[2]
    base_module = _load_base_verifier(repository_root)

    rows: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            errors.append("case is not an object")
            continue
        row, case_errors = _case_result(case, base_module)
        rows.append(row)
        errors.extend(f"{row['name']}: {error}" for error in case_errors)

    agree = sum(row["status"] == "AGREE" for row in rows)
    report = {
        "subject": {
            "repository": UPSTREAM_REPOSITORY,
            "commit": UPSTREAM_COMMIT,
            "path": VECTOR_PATH,
            "sha256": PINNED_VECTOR_SHA256,
            "version": VECTOR_CONTRACT,
            "revision": VECTOR_REVISION,
            "case_count": len(CASE_NAMES),
            "source_copies": copies,
        },
        "verifier": {
            "id": VERIFIER_ID,
            "version": VERIFIER_VERSION,
            "upstream_runtime_imported": False,
            "base_bundle_verifier": (
                "proofs/attenu-guard-v0.12.1-independent/"
                "independent_bundle_verifier.py"
            ),
        },
        "summary": {
            "cases": len(rows),
            "agree": agree,
            "disagree": len(rows) - agree,
            "accept_cases": sum(row["observed"] == "accept" for row in rows),
            "reject_cases": sum(row["observed"] == "reject" for row in rows),
            "failure_vocabulary_covered": len(ENVELOPE_FAILURES),
            "overall": "AGREE" if agree == len(CASE_NAMES) and not errors else "DISAGREE",
        },
        "failure_vocabulary": list(ENVELOPE_FAILURES),
        "cases": rows,
        "claim_boundary": {
            "proved": [
                "independent agreement with the frozen 18-case observer-envelope corpus",
                "byte identity of repository, PyPI, and npm vector copies",
                "entry_hash binding plus locator mismatch detection",
                "raw-wire JCS and Ed25519 witness verification exercised by the corpus",
                "duplicate-subject rejection and exact per-entry state mapping",
            ],
            "not_proved": [
                "global capture completeness or absence of never-recorded effects",
                "that an absent envelope was expected or that a witness was available",
                "witness freshness, non-equivocation, or deployment non-bypassability",
                "integrity of an envelope array stripped outside the ledger anchor",
                "correctness of the upstream specification or every implementation",
                "A2A adoption, certification, or endorsement",
            ],
        },
    }
    return report, errors


def write_json(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", required=True, type=Path)
    parser.add_argument("--python-vector", type=Path)
    parser.add_argument("--npm-vector", type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()

    try:
        report, errors = build_report(args.vectors, args.python_vector, args.npm_vector)
        write_json(args.json_out, report)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report["summary"], sort_keys=True))
    if errors:
        for error in errors:
            print(f"DISAGREE: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
