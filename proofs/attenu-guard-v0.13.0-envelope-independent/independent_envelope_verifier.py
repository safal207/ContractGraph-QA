#!/usr/bin/env python3
"""Independent scorer for Attenu observer-envelope vectors v1.1.

This verifier does not import ``attenu_guard`` and does not execute its Python
or TypeScript verifier. It reuses the previously merged, standalone
ContractGraph-QA bundle-v1.2 scorer for the ledger/anchor/authority layer, then
implements the envelope-v1 contract independently over the pinned vector data.

Claim boundary:
- exact released vector bytes, revision and case order are pinned;
- ledger checks are performed by the local independent bundle scorer;
- Ed25519 envelope signatures, subject binding, raw canonicality, failure
  positions and per-entry states are checked here;
- this is corpus interoperability evidence, not runtime certification,
  witness trust endorsement, or proof that an envelope array was never stripped.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

VERIFIER_ID = "safal207-independent-envelope-v1.1"
VERIFIER_VERSION = "0.1.0"
VECTOR_CONTRACT = "envelope_vectors_v1"
VECTOR_REVISION = "envelope_vectors_v1.1"
UPSTREAM_REPOSITORY = "attenu-io/attenu-guard"
UPSTREAM_TAG = "v0.13.0"
UPSTREAM_COMMIT = "8042a0ce33a9f8a7bf54a1917d5e8a0ac0344084"
PINNED_VECTOR_SHA256 = "6a57d75ebec881d39d5a1805793a20f9a6d7bff021b70782dcb57c43b276df64"

PINNED_CASES = [
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

ENVELOPE_VERSION = 1
ENVELOPE_TYP = "delegation-event-observation"
ENVELOPE_ALG = "EdDSA"
ENVELOPE_MEMBERS = frozenset({"v", "typ", "subject", "observed", "witness", "sig"})
OBSERVED_MEMBERS = frozenset({"result", "at", "method"})
WITNESS_MEMBERS = frozenset({"kid", "alg"})
SUBJECT_MEMBERS = {
    "spawn": frozenset({"chain_id", "node", "seq", "entry_hash", "event"}),
    "allow": frozenset(
        {"chain_id", "node", "seq", "entry_hash", "event", "call_id"}
    ),
}
ENVELOPE_RESULTS = frozenset({"matched", "not_matched", "indeterminate"})
WITNESS_SIGNED = "witness-signed"
PROCESS_ASSERTED = "process-asserted"
ENVELOPE_FAILURES = frozenset(
    {
        "envelope_unknown_version",
        "envelope_unknown_member",
        "envelope_subject_mismatch",
        "envelope_duplicate_subject",
        "envelope_non_canonical",
        "envelope_unknown_witness",
        "envelope_bad_signature",
    }
)

_BASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "attenu-guard-v0.12.1-independent"
    / "independent_bundle_verifier.py"
)


def _load_base_verifier():
    name = "_cgqa_independent_attenu_bundle_v12"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load local base verifier at {_BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base_verifier()


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class EnvelopeScore:
    failures: tuple[Any, ...]
    states: dict[str, str]
    results: dict[str, str]
    signing_inputs: tuple[str | None, ...]


@dataclass(frozen=True)
class CaseResult:
    name: str
    expected: str
    observed: str
    status: str
    required_failures: tuple[dict[str, Any], ...]
    observed_failures: tuple[dict[str, Any], ...]
    missing_required: tuple[dict[str, Any], ...]
    extra_observed: tuple[dict[str, Any], ...]
    states_match: bool
    canonical_match: bool
    anchor_mode: str
    error: str | None = None


@dataclass(frozen=True)
class CorpusReport:
    vector_sha256: str
    source_repository: str
    source_tag: str
    source_commit: str
    cases: tuple[CaseResult, ...]

    @property
    def agree_count(self) -> int:
        return sum(case.status == "agree" for case in self.cases)

    @property
    def disagree_count(self) -> int:
        return sum(case.status == "disagree" for case in self.cases)

    @property
    def unsupported_count(self) -> int:
        return sum(case.status == "unsupported" for case in self.cases)

    @property
    def all_agree(self) -> bool:
        return self.agree_count == len(self.cases)


def _is_json_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _position(
    subject: Any,
    by_seq: Mapping[int, Mapping[str, Any]],
) -> tuple[int | None, str | None, Mapping[str, Any] | None]:
    if not isinstance(subject, Mapping):
        return None, None, None
    seq = subject.get("seq")
    if not _is_json_int(seq):
        return None, None, None
    entry = by_seq.get(seq)
    if entry is None:
        return seq, None, None
    return entry.get("seq"), entry.get("node"), entry


def _envelope_failure(
    reason: str,
    subject: Any,
    by_seq: Mapping[int, Mapping[str, Any]],
    detail: str,
):
    seq, node, entry = _position(subject, by_seq)
    call_id = entry.get("call_id") if entry is not None else None
    return BASE.Failure(
        reason=reason,
        seq=seq,
        node=node,
        call_id=call_id,
        detail=f"{reason}: {detail}",
    )


def _recomputed_hashes(entries: list[Mapping[str, Any]]) -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    previous = BASE.GENESIS
    for index, entry in enumerate(entries):
        payload = {key: value for key, value in entry.items() if key != "hash"}
        try:
            computed = hashlib.sha256(
                previous.encode("ascii") + BASE.jcs_bytes(payload)
            ).hexdigest()
        except Exception:  # corpus scorer: malformed content has no usable binding hash
            computed = None
        seq = entry.get("seq", index)
        if _is_json_int(seq):
            out[seq] = computed
        previous = computed if computed is not None else BASE.GENESIS
    return out


def _trusted_witnesses(rows: Any) -> dict[str, bytes]:
    if not isinstance(rows, list):
        raise ValueError("witness_keys must be an array")
    trusted: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("each witness_keys row must be an object")
        if set(row) != {"kid", "alg", "public_key_hex"}:
            raise ValueError("witness_keys rows have an unexpected member set")
        kid = row.get("kid")
        if not isinstance(kid, str):
            raise ValueError("witness key kid must be a string")
        if row.get("alg") != ENVELOPE_ALG:
            raise ValueError(f"witness key {kid!r} does not declare EdDSA")
        raw = row.get("public_key_hex")
        if (
            not isinstance(raw, str)
            or len(raw) != 64
            or raw != raw.lower()
        ):
            raise ValueError(
                f"witness key {kid!r} must be 64 lowercase hexadecimal characters"
            )
        try:
            key = bytes.fromhex(raw)
        except ValueError as exc:
            raise ValueError(f"witness key {kid!r} is not hexadecimal") from exc
        if kid in trusted:
            raise ValueError(f"duplicate witness key kid {kid!r}")
        trusted[kid] = key
    return trusted


def _score_envelopes(
    bundle: Mapping[str, Any],
    witness_keys: Any,
    *,
    raw_hex: Any = None,
) -> EnvelopeScore:
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        raise ValueError("bundle.entries must be an array")
    envelopes = bundle.get("envelopes", [])
    if not isinstance(envelopes, list):
        raise ValueError("bundle.envelopes must be an array when present")

    trusted = _trusted_witnesses(witness_keys)
    by_seq = {
        entry.get("seq", index): entry
        for index, entry in enumerate(entries)
        if isinstance(entry, Mapping)
        and _is_json_int(entry.get("seq", index))
    }
    recomputed = _recomputed_hashes(entries)
    states = {
        str(entry.get("seq", index)): PROCESS_ASSERTED
        for index, entry in enumerate(entries)
        if isinstance(entry, Mapping)
    }
    results: dict[str, str] = {}
    claims: dict[int, int] = {}
    failures: list[Any] = []
    signing_inputs: list[str | None] = []

    received: bytes | None = None
    if raw_hex is not None:
        if not isinstance(raw_hex, str):
            raise ValueError("raw_hex must be a hexadecimal string")
        try:
            received = bytes.fromhex(raw_hex)
        except ValueError as exc:
            raise ValueError("raw_hex is not hexadecimal") from exc

    for index, envelope in enumerate(envelopes):
        signing_inputs.append(None)
        if not isinstance(envelope, Mapping):
            failures.append(
                BASE.Failure(
                    reason="envelope_unknown_version",
                    seq=None,
                    node=None,
                    call_id=None,
                    detail=(
                        "envelope_unknown_version: "
                        f"envelope #{index} is not a JSON object"
                    ),
                )
            )
            continue

        subject = envelope.get("subject")
        if (
            not _is_json_int(envelope.get("v"))
            or envelope.get("v") != ENVELOPE_VERSION
            or envelope.get("typ") != ENVELOPE_TYP
        ):
            failures.append(
                _envelope_failure(
                    "envelope_unknown_version",
                    subject,
                    by_seq,
                    (
                        f"v={envelope.get('v')!r} typ={envelope.get('typ')!r}; "
                        f"expected v={ENVELOPE_VERSION} typ={ENVELOPE_TYP!r}"
                    ),
                )
            )
            continue

        bad_members = False
        for label, value, expected in (
            ("envelope", envelope, ENVELOPE_MEMBERS),
            ("observed", envelope.get("observed"), OBSERVED_MEMBERS),
            ("witness", envelope.get("witness"), WITNESS_MEMBERS),
        ):
            if not isinstance(value, Mapping) or set(value) != expected:
                got = sorted(value) if isinstance(value, Mapping) else "not an object"
                failures.append(
                    _envelope_failure(
                        "envelope_unknown_member",
                        subject,
                        by_seq,
                        f"{label} member set is {got}, expected {sorted(expected)}",
                    )
                )
                bad_members = True
                break
        if bad_members:
            continue

        if not isinstance(subject, Mapping):
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    "subject is not a JSON object",
                )
            )
            continue
        event = subject.get("event")
        if not isinstance(event, str) or event not in SUBJECT_MEMBERS:
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    f"subject event {event!r} is not defined by envelope v1",
                )
            )
            continue
        expected_members = SUBJECT_MEMBERS[event]
        if set(subject) - expected_members:
            failures.append(
                _envelope_failure(
                    "envelope_unknown_member",
                    subject,
                    by_seq,
                    (
                        f"subject member set is {sorted(subject)}, "
                        f"expected {sorted(expected_members)}"
                    ),
                )
            )
            continue
        missing = expected_members - set(subject)
        if missing:
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    f"subject is missing {sorted(missing)}",
                )
            )
            continue

        seq = subject.get("seq")
        if not _is_json_int(seq):
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    "subject seq is not an integer",
                )
            )
            continue
        entry = by_seq.get(seq)
        if entry is None:
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    f"no entry at seq {seq!r} in this bundle",
                )
            )
            continue

        previous_claims = claims.get(seq, 0)
        claims[seq] = previous_claims + 1
        if previous_claims:
            failures.append(
                _envelope_failure(
                    "envelope_duplicate_subject",
                    subject,
                    by_seq,
                    f"seq {seq} is already covered by an earlier envelope",
                )
            )
            continue

        computed = recomputed.get(seq)
        if subject.get("entry_hash") != computed:
            failures.append(
                _envelope_failure(
                    "envelope_subject_mismatch",
                    subject,
                    by_seq,
                    (
                        f"subject entry_hash {subject.get('entry_hash')!r} "
                        f"!= recomputed {computed!r}"
                    ),
                )
            )
            continue

        locators = (
            ("chain_id", entry.get("chain_id")),
            ("node", entry.get("node")),
            ("event", entry.get("event")),
        )
        if event == "allow":
            locators += (("call_id", entry.get("call_id")),)
        locator_failed = False
        for member, actual in locators:
            if subject.get(member) != actual:
                failures.append(
                    _envelope_failure(
                        "envelope_subject_mismatch",
                        subject,
                        by_seq,
                        (
                            f"subject {member}={subject.get(member)!r} "
                            f"!= {actual!r} at seq {seq}"
                        ),
                    )
                )
                locator_failed = True
                break
        if locator_failed:
            continue

        non_canonical = False
        if index == 0 and received is not None:
            try:
                recanonicalized = BASE.jcs_bytes(dict(envelope))
            except Exception as exc:
                failures.append(
                    _envelope_failure(
                        "envelope_non_canonical",
                        subject,
                        by_seq,
                        f"envelope cannot be canonicalized: {exc}",
                    )
                )
                continue
            if received != recanonicalized:
                failures.append(
                    _envelope_failure(
                        "envelope_non_canonical",
                        subject,
                        by_seq,
                        (
                            "bytes as received are not JCS of the parsed envelope "
                            f"({len(received)} received, "
                            f"{len(recanonicalized)} canonical)"
                        ),
                    )
                )
                non_canonical = True

        witness = envelope["witness"]
        kid = witness.get("kid")
        alg = witness.get("alg")
        if not isinstance(kid, str):
            failures.append(
                _envelope_failure(
                    "envelope_unknown_witness",
                    subject,
                    by_seq,
                    "witness kid is not a string",
                )
            )
            continue
        if alg != ENVELOPE_ALG:
            failures.append(
                _envelope_failure(
                    "envelope_unknown_witness",
                    subject,
                    by_seq,
                    (
                        f"witness alg={alg!r}; envelope v1 defines "
                        f"{ENVELOPE_ALG!r} and no other algorithm"
                    ),
                )
            )
            continue
        public_key = trusted.get(kid)
        if public_key is None:
            failures.append(
                _envelope_failure(
                    "envelope_unknown_witness",
                    subject,
                    by_seq,
                    f"witness kid={kid!r} is not in the trusted witness set",
                )
            )
            continue

        signature_hex = envelope.get("sig")
        if not isinstance(signature_hex, str):
            failures.append(
                _envelope_failure(
                    "envelope_bad_signature",
                    subject,
                    by_seq,
                    "sig is not a hexadecimal string",
                )
            )
            continue
        try:
            signature = bytes.fromhex(signature_hex)
        except ValueError:
            signature = b""

        try:
            signing_input = BASE.jcs_bytes(
                {key: value for key, value in envelope.items() if key != "sig"}
            )
        except Exception as exc:
            failures.append(
                _envelope_failure(
                    "envelope_non_canonical",
                    subject,
                    by_seq,
                    f"envelope cannot be canonicalized for signing: {exc}",
                )
            )
            continue
        signing_inputs[index] = signing_input.hex()

        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature,
                signing_input,
            )
        except (InvalidSignature, ValueError):
            failures.append(
                _envelope_failure(
                    "envelope_bad_signature",
                    subject,
                    by_seq,
                    f"signature does not verify under witness kid={kid!r}",
                )
            )
            continue

        if non_canonical:
            continue

        observed = envelope["observed"]
        result = observed.get("result")
        if result not in ENVELOPE_RESULTS:
            # The released v1.1 corpus contains no unknown result row. Refuse
            # without inventing a new reason token outside the closed vocabulary.
            failures.append(
                _envelope_failure(
                    "envelope_unknown_member",
                    subject,
                    by_seq,
                    f"observed.result {result!r} is outside the v1 vocabulary",
                )
            )
            continue

        states[str(seq)] = WITNESS_SIGNED
        results[str(seq)] = result

    for seq, count in claims.items():
        if count > 1:
            states[str(seq)] = PROCESS_ASSERTED

    return EnvelopeScore(
        failures=tuple(failures),
        states=states,
        results=results,
        signing_inputs=tuple(signing_inputs),
    )


def _synthetic_anchor_for_unanchored_check(
    bundle: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Add a non-evidentiary local anchor solely to reuse the base scorer.

    The corpus's unanchored row intentionally asks no anchor question. This
    helper does not upgrade that input: it gives the existing base verifier a
    matching local anchor so its chain, authority, containment and execution
    checks can run while anchor evidence remains classified as not present.
    """

    checked = copy.deepcopy(bundle)
    entries = checked.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("unanchored corpus case requires a non-empty ledger")

    root = next(
        (entry for entry in entries if entry.get("event") == "root"),
        entries[0],
    )
    body = {
        "v": root.get("v"),
        "c14n": checked.get("c14n", "JCS"),
        "chain_id": checked.get("chain_id", root.get("chain_id")),
        "seq": entries[-1].get("seq"),
        "head": entries[-1].get("hash"),
        "ts": 0,
    }
    secret = b"cgqa-local-unanchored-check-only"
    kid = "cgqa-local-unanchored-check-only"
    signature = hmac.new(secret, BASE.jcs_bytes(body), hashlib.sha256).hexdigest()
    checked["anchor"] = {
        **body,
        "kid": kid,
        "sig": signature,
        "verified": True,
    }
    signer = {"alg": "HS256", "kid": kid, "secret_hex": secret.hex()}
    return checked, signer


def _score_base(case: Mapping[str, Any]) -> tuple[tuple[Any, ...], str]:
    bundle = case.get("bundle")
    if not isinstance(bundle, Mapping):
        raise ValueError("case.bundle must be an object")
    signer = case.get("signer")
    if signer is None:
        if "anchor" in bundle:
            raise ValueError("signer=null case unexpectedly carries an anchor")
        checked, local_signer = _synthetic_anchor_for_unanchored_check(bundle)
        return tuple(BASE.verify_bundle(checked, local_signer)), "not_present_not_checked"
    if not isinstance(signer, Mapping):
        raise ValueError("case.signer must be an object or null")
    return tuple(BASE.verify_bundle(bundle, signer)), "fixture_anchor_checked"


def _score_key(failure: Any) -> dict[str, Any]:
    return {
        "reason": failure.reason,
        "seq": failure.seq,
        "node": failure.node,
    }


def _covered_seqs(bundle: Mapping[str, Any]) -> set[int]:
    covered: set[int] = set()
    for envelope in bundle.get("envelopes", []) or []:
        if not isinstance(envelope, Mapping):
            continue
        subject = envelope.get("subject")
        if isinstance(subject, Mapping) and _is_json_int(subject.get("seq")):
            covered.add(subject["seq"])
    return covered


def _assert_position_rules(
    bundle: Mapping[str, Any],
    failures: tuple[Any, ...],
) -> None:
    covered = _covered_seqs(bundle)
    for failure in failures:
        if failure.reason.startswith("envelope_") and failure.seq not in covered:
            raise ValueError(
                f"{failure.reason} landed at seq {failure.seq!r}, "
                "which no envelope covers"
            )


def score_case(case: Mapping[str, Any]) -> CaseResult:
    name = case.get("name")
    if not isinstance(name, str):
        return CaseResult(
            name="<unnamed>",
            expected="unknown",
            observed="unsupported",
            status="unsupported",
            required_failures=(),
            observed_failures=(),
            missing_required=(),
            extra_observed=(),
            states_match=False,
            canonical_match=False,
            anchor_mode="unknown",
            error="case name must be a string",
        )

    try:
        expected = case.get("expect")
        if expected not in {"accept", "reject"}:
            raise ValueError("case.expect must be accept or reject")
        required_raw = case.get("expect_failures")
        if not isinstance(required_raw, list):
            raise ValueError("expect_failures must be an array")
        required = tuple(
            {
                "reason": item.get("reason"),
                "seq": item.get("seq"),
                "node": item.get("node"),
            }
            for item in required_raw
            if isinstance(item, Mapping)
        )
        if len(required) != len(required_raw):
            raise ValueError("every expect_failures row must be an object")

        base_failures, anchor_mode = _score_base(case)
        envelope_score = _score_envelopes(
            case["bundle"],
            case.get("witness_keys"),
            raw_hex=case.get("raw_hex"),
        )
        all_failures = tuple(base_failures) + tuple(envelope_score.failures)
        _assert_position_rules(case["bundle"], all_failures)

        observed = "accept" if not all_failures else "reject"
        observed_keys = tuple(_score_key(failure) for failure in all_failures)
        missing = tuple(item for item in required if item not in observed_keys)
        extra = tuple(item for item in observed_keys if item not in required)

        expected_states = case.get("expect_states")
        if not isinstance(expected_states, Mapping):
            raise ValueError("expect_states must be an object")
        states_match = envelope_score.states == dict(expected_states)

        canonical_match = True
        if "canonical_hex" in case:
            expected_hex = case.get("canonical_hex")
            produced = (
                envelope_score.signing_inputs[0]
                if envelope_score.signing_inputs
                else None
            )
            canonical_match = isinstance(expected_hex, str) and produced == expected_hex

        agrees = (
            observed == expected
            and not missing
            and states_match
            and canonical_match
        )
        return CaseResult(
            name=name,
            expected=expected,
            observed=observed,
            status="agree" if agrees else "disagree",
            required_failures=required,
            observed_failures=observed_keys,
            missing_required=missing,
            extra_observed=extra,
            states_match=states_match,
            canonical_match=canonical_match,
            anchor_mode=anchor_mode,
        )
    except Exception as exc:  # one hostile case must not stop scoring the corpus
        return CaseResult(
            name=name,
            expected=str(case.get("expect", "unknown")),
            observed="unsupported",
            status="unsupported",
            required_failures=(),
            observed_failures=(),
            missing_required=(),
            extra_observed=(),
            states_match=False,
            canonical_match=False,
            anchor_mode="unknown",
            error=str(exc),
        )


def score_corpus(raw: bytes) -> CorpusReport:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PINNED_VECTOR_SHA256:
        raise ValueError(
            f"vector SHA-256 {digest} != pinned {PINNED_VECTOR_SHA256}"
        )
    document = BASE.load_json_strict(raw)
    if not isinstance(document, Mapping):
        raise ValueError("vector document must be a JSON object")
    if document.get("version") != VECTOR_CONTRACT:
        raise ValueError(
            f"version {document.get('version')!r} != {VECTOR_CONTRACT!r}"
        )
    if document.get("revision") != VECTOR_REVISION:
        raise ValueError(
            f"revision {document.get('revision')!r} != {VECTOR_REVISION!r}"
        )
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("cases must be an array")
    names = [
        case.get("name") if isinstance(case, Mapping) else None
        for case in cases
    ]
    if names != PINNED_CASES:
        raise ValueError(f"case order {names!r} != pinned {PINNED_CASES!r}")

    return CorpusReport(
        vector_sha256=digest,
        source_repository=UPSTREAM_REPOSITORY,
        source_tag=UPSTREAM_TAG,
        source_commit=UPSTREAM_COMMIT,
        cases=tuple(score_case(case) for case in cases),
    )


def report_as_json(report: CorpusReport) -> dict[str, Any]:
    return {
        "verifier": {
            "id": VERIFIER_ID,
            "version": VERIFIER_VERSION,
            "base_ledger_verifier": {
                "id": BASE.VERIFIER_ID,
                "version": BASE.VERIFIER_VERSION,
                "path": _display_path(_BASE_PATH),
            },
        },
        "source": {
            "repository": report.source_repository,
            "tag": report.source_tag,
            "commit": report.source_commit,
            "vector_contract": VECTOR_CONTRACT,
            "vector_revision": VECTOR_REVISION,
            "vector_sha256": report.vector_sha256,
        },
        "summary": {
            "total": len(report.cases),
            "agree": report.agree_count,
            "disagree": report.disagree_count,
            "unsupported": report.unsupported_count,
        },
        "cases": [asdict(case) for case in report.cases],
        "claim_boundary": {
            "proved_for_pinned_corpus": [
                "exact vector bytes, revision, and case order",
                "independent ledger hash, HS256 anchor, authority, containment, and execution-binding checks",
                "Ed25519 witness signature under the named trusted kid",
                "entry_hash binding and locator consistency",
                "raw-envelope JCS canonicality where raw_hex is supplied",
                "minimal required failure reasons at exact seq/node positions",
                "per-entry witness-signed or process-asserted state",
                "duplicate-subject fallback to process-asserted",
            ],
            "not_proved": [
                "completeness of witness coverage",
                "that an absent envelopes array was never stripped",
                "authority or independence of a configured witness",
                "runtime enforcement outside the frozen cases",
                "general verifier completeness or security certification",
                "endorsement by attenu-guard or A2A maintainers",
            ],
        },
    }


def render_markdown(report: CorpusReport) -> str:
    rows = []
    for case in report.cases:
        required = ", ".join(
            f"`{item['reason']}@{item['seq']}`"
            for item in case.required_failures
        ) or "—"
        extras = ", ".join(
            f"`{item['reason']}@{item['seq']}`"
            for item in case.extra_observed
        ) or "—"
        rows.append(
            f"| `{case.name}` | {case.expected} | {case.observed} | "
            f"{required} | {extras} | "
            f"{'yes' if case.states_match else 'no'} | "
            f"{'yes' if case.canonical_match else 'no'} | "
            f"**{case.status.upper()}** |"
        )

    return "\n".join(
        [
            "# Independent reproduction: Attenu observer envelopes v1.1",
            "",
            f"**Bounded result: {report.agree_count}/{len(report.cases)} "
            "released cases conformant.**",
            "",
            "## Exact subject",
            "",
            f"- Repository: `{report.source_repository}`",
            f"- Release tag: `{report.source_tag}`",
            f"- Commit: `{report.source_commit}`",
            f"- Contract: `{VECTOR_CONTRACT}`",
            f"- Revision: `{VECTOR_REVISION}`",
            f"- Vector SHA-256: `{report.vector_sha256}`",
            f"- Verifier: `{VERIFIER_ID}` `{VERIFIER_VERSION}`",
            f"- Base ledger scorer: `{BASE.VERIFIER_ID}` `{BASE.VERIFIER_VERSION}`",
            "- Upstream verifier execution: **disabled**.",
            "",
            "## Case matrix",
            "",
            "| Case | Expected | Observed | Required failures | Extra failures | "
            "States match | Canonical bytes match | Result |",
            "|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "The corpus uses a minimal-set rule: extra findings are permitted, but "
            "every declared `{reason, seq, node}` must be present, and the per-entry "
            "state must match exactly. Envelope failures are constrained to covered "
            "hops; they never manufacture a chain-level anchor failure.",
            "",
            "## What this independently checks",
            "",
            "1. The exact released JSON bytes, revision, SHA-256 and 18-case order.",
            "2. The ledger hash chain, HS256 anchor where present, delegation "
            "monotonicity, containment and bundle-v2 execution binding through the "
            "already merged standalone ContractGraph-QA scorer.",
            "3. Envelope-v1 member sets, event-specific subjects, recomputed "
            "`entry_hash`, locator consistency and one-envelope-per-entry.",
            "4. Ed25519 verification under the `kid`-selected trusted key, with "
            "`EdDSA` as the only accepted v1 algorithm.",
            "5. Raw-byte JCS canonicality for the non-canonical negative control and "
            "exact signing bytes for the reorder positive control.",
            "6. Exact required reason/position pairs and every entry's "
            "`witness-signed` or `process-asserted` state.",
            "",
            "## Boundary preserved",
            "",
            "A valid envelope proves that a configured witness key signed the "
            "identity of one committed entry. It does not prove that the witness was "
            "authoritative, that coverage was complete, or that a missing top-level "
            "`envelopes` array was never stripped. Envelope v1 keeps that array "
            "outside the ledger anchor; this report preserves the limitation rather "
            "than upgrading absence into evidence.",
            "",
            "## Non-claims",
            "",
            "This is frozen-corpus interoperability evidence. It is not a general "
            "security audit, runtime certification, proof of witness independence, "
            "proof of global coverage, A2A conformance certification, or endorsement "
            "in either direction.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independently score Attenu observer-envelope vectors v1.1."
    )
    parser.add_argument("vector_file", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args(argv)

    report = score_corpus(args.vector_file.read_bytes())
    for case in report.cases:
        detail = case.error or (
            f"required={len(case.required_failures)} "
            f"extra={len(case.extra_observed)} "
            f"states={case.states_match} canonical={case.canonical_match}"
        )
        print(f"{case.status.upper():11} {case.name}: {detail}")
    print(
        f"\n{len(report.cases)} cases: {report.agree_count} agree, "
        f"{report.disagree_count} disagree, "
        f"{report.unsupported_count} unsupported"
    )

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report_as_json(report), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_out is not None:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(report), encoding="utf-8")

    return 0 if report.all_agree else 1


if __name__ == "__main__":
    raise SystemExit(main())
