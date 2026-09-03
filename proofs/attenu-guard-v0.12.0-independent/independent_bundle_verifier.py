#!/usr/bin/env python3
"""Standalone independent scorer for Attenu bundle_vectors_v1.1.

This verifier intentionally does NOT import ``attenu_guard`` or reuse either
published Python/TypeScript verifier. It implements only the byte-level rules
and bundle-v2 execution-binding rules needed by the released
``bundle_vectors_v1.json`` corpus revision ``bundle_vectors_v1.1``.

Claim boundary:
- independently reproduces the released corpus result;
- validates the exact fixture bytes, entry hash chain, HS256 anchor,
  authority narrowing/containment, and allow/outcome binding exercised by it;
- is not a general security audit, production certification, or proof of
  CrewAI runtime behaviour outside this corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

VERIFIER_ID = "safal207-independent-bundle-v1.1"
VERIFIER_VERSION = "0.2.0"
VECTOR_CONTRACT = "bundle_vectors_v1"
VECTOR_REVISION = "bundle_vectors_v1.1"
# Exact bytes extracted from attenu_guard-0.12.0-py3-none-any.whl.
PINNED_VECTOR_SHA256 = "b21c5a44a79d422d52857f03e2f3327d559c409e98c482b4664e1ab726327403"
PINNED_CASES = [
    "valid_bundle_v2",
    "reject_params_mismatch",
    "reject_outcome_without_allow",
    "reject_outcome_before_allow",
    "reject_duplicate_outcome",
    "reject_duplicate_call_id",
    "reject_rehashed_chain",
    "reject_tampered_entry",
    "reject_widened_scope",
    "reject_uncontained_allow",
    "reject_increased_ttl",
    "reject_loosened_ceiling",
]
GENESIS = "0" * 64
MAX_SAFE_INTEGER = 2**53 - 1


class DuplicateMember(ValueError):
    pass


class UnsupportedCanonicalValue(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateMember(f"duplicate JSON member: {key!r}")
        out[key] = value
    return out


def load_json_strict(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object,
                      parse_constant=lambda token: (_ for _ in ()).throw(
                          ValueError(f"non-finite JSON number: {token}")))


def _utf16_sort_key(value: str) -> bytes:
    # RFC 8785 sorts member names by UTF-16 code units. Lone surrogates are
    # invalid I-JSON and are rejected by jcs_bytes() before this is called.
    return value.encode("utf-16-be")


def _validate_string(value: str) -> None:
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise UnsupportedCanonicalValue("lone UTF-16 surrogate")


def jcs_bytes(value: Any) -> bytes:
    """RFC-8785-compatible canonical JSON for this corpus.

    The released bundle corpus contains only null/bool/safe integers/ASCII
    strings/lists/objects. Floats fail closed rather than being serialized by a
    non-ECMAScript number formatter. This makes the implementation honest about
    its conformance boundary while reproducing every released byte exactly.
    """
    def encode(v: Any) -> str:
        if v is None:
            return "null"
        if v is True:
            return "true"
        if v is False:
            return "false"
        if isinstance(v, int) and not isinstance(v, bool):
            if abs(v) > MAX_SAFE_INTEGER:
                raise UnsupportedCanonicalValue(f"unsafe integer: {v}")
            return str(v)
        if isinstance(v, float):
            raise UnsupportedCanonicalValue("floating-point value outside published-corpus profile")
        if isinstance(v, str):
            _validate_string(v)
            # Python's encoder emits the JSON string escaping required for the
            # corpus (all fixture strings are ASCII; ensure_ascii=False keeps the
            # implementation correct for ordinary Unicode scalar values too).
            return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        if isinstance(v, list):
            return "[" + ",".join(encode(item) for item in v) + "]"
        if isinstance(v, dict):
            for key in v:
                if not isinstance(key, str):
                    raise UnsupportedCanonicalValue("non-string object key")
                _validate_string(key)
            keys = sorted(v, key=_utf16_sort_key)
            return "{" + ",".join(encode(key) + ":" + encode(v[key]) for key in keys) + "}"
        raise UnsupportedCanonicalValue(f"unsupported JSON type: {type(v).__name__}")

    return encode(value).encode("utf-8")


@dataclass(frozen=True)
class Failure:
    reason: str
    seq: int | None
    node: str | None
    detail: str
    call_id: str | None = None

    def score_key(self) -> dict[str, Any]:
        return {"reason": self.reason, "seq": self.seq, "node": self.node}


def _failure(reason: str, entry: Mapping[str, Any] | None, detail: str) -> Failure:
    if entry is None:
        return Failure(reason=reason, seq=None, node=None, call_id=None, detail=detail)
    return Failure(reason=reason, seq=entry.get("seq"), node=entry.get("node"),
                   call_id=entry.get("call_id"), detail=detail)


def _scope_covers(parent: str, child: str) -> bool:
    if parent == child:
        return True
    if parent.endswith(".*"):
        prefix = parent[:-1]  # preserve the separating dot, e.g. "crm."
        return child.startswith(prefix) and len(child) > len(prefix)
    return False


def _constraint_map(authority: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for raw in authority.get("constraints") or []:
        if isinstance(raw, dict) and isinstance(raw.get("key"), str):
            out[raw["key"]] = raw
    return out


def _authority_narrower(child: Mapping[str, Any], parent: Mapping[str, Any]) -> bool:
    child_scopes = child.get("scopes") or []
    parent_scopes = parent.get("scopes") or []
    if not all(any(_scope_covers(p, c) for p in parent_scopes) for c in child_scopes):
        return False

    child_ttl = child.get("ttl")
    parent_ttl = parent.get("ttl")
    if not isinstance(child_ttl, int) or not isinstance(parent_ttl, int) or child_ttl > parent_ttl:
        return False

    child_constraints = _constraint_map(child)
    parent_constraints = _constraint_map(parent)
    # Every bound held by the parent must remain present in the child. Omitting
    # a ceiling makes that dimension unbounded and is therefore a widening.
    for key, parent_constraint in parent_constraints.items():
        child_constraint = child_constraints.get(key)
        if child_constraint is None:
            return False
        # The released corpus exercises max_rows. Unknown constraint forms fail
        # closed instead of being assumed narrower.
        if "max" in child_constraint and "max" in parent_constraint:
            child_max = child_constraint["max"]
            parent_max = parent_constraint["max"]
            if (not isinstance(child_max, (int, float))
                    or isinstance(child_max, bool)
                    or not isinstance(parent_max, (int, float))
                    or isinstance(parent_max, bool)
                    or child_max > parent_max):
                return False
        elif child_constraint != parent_constraint:
            return False

    # Additional known max constraints narrow authority further. Unknown forms
    # stay fail-closed because this verifier claims only the published corpus
    # profile, not the draft's complete constraint vocabulary.
    for key, child_constraint in child_constraints.items():
        if key in parent_constraints:
            continue
        if (set(child_constraint) != {"key", "max"}
                or not isinstance(child_constraint.get("max"), (int, float))
                or isinstance(child_constraint.get("max"), bool)):
            return False
    return True


def _context_within(authority: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    constraints = _constraint_map(authority)
    if "rows" in context and "max_rows" in constraints:
        limit = constraints["max_rows"].get("max")
        if not isinstance(limit, int) or not isinstance(context["rows"], int) or context["rows"] > limit:
            return False
    return True


def verify_bundle(bundle: Mapping[str, Any], signer: Mapping[str, Any]) -> list[Failure]:
    failures: list[Failure] = []

    if bundle.get("v") != 2:
        failures.append(_failure("unsupported_version", None, f"bundle v={bundle.get('v')!r}"))
        return failures
    entries = bundle.get("entries")
    anchor = bundle.get("anchor")
    if not isinstance(entries, list) or not isinstance(anchor, dict):
        failures.append(_failure("malformed_bundle", None, "entries or anchor missing"))
        return failures

    # 1) Entry-chain integrity: SHA256(prev_hash ASCII || JCS(entry minus hash)).
    previous = GENESIS
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            failures.append(_failure("integrity", None, f"entry {position} is not an object"))
            continue
        payload = {key: value for key, value in entry.items() if key != "hash"}
        calculated = hashlib.sha256(previous.encode("ascii") + jcs_bytes(payload)).hexdigest()
        if entry.get("seq") != position or entry.get("prev_hash") != previous or entry.get("hash") != calculated:
            failures.append(_failure(
                "integrity", entry,
                f"entry chain mismatch at position={position}: "
                f"seq={entry.get('seq')!r}, prev={entry.get('prev_hash')!r}, "
                f"stored={entry.get('hash')!r}, calculated={calculated}",
            ))
        stored_hash = entry.get("hash")
        previous = stored_hash if isinstance(stored_hash, str) else calculated

    # 2) Signed anchor over its own canonical body and exact ledger head.
    anchor_body = {key: value for key, value in anchor.items()
                   if key not in {"kid", "sig", "verified"}}
    try:
        secret = bytes.fromhex(str(signer["secret_hex"]))
        expected_sig = hmac.new(secret, jcs_bytes(anchor_body), hashlib.sha256).hexdigest()
    except (KeyError, TypeError, ValueError, UnsupportedCanonicalValue) as exc:
        expected_sig = ""
        failures.append(_failure("integrity(anchor)", None, f"cannot verify anchor: {exc}"))

    last_seq = entries[-1].get("seq") if entries else -1
    last_hash = entries[-1].get("hash") if entries else "GENESIS"
    anchor_ok = (
        signer.get("alg") == "HS256"
        and signer.get("kid") == anchor.get("kid")
        and hmac.compare_digest(str(anchor.get("sig", "")), expected_sig)
        and anchor.get("seq") == last_seq
        and anchor.get("head") == last_hash
        and anchor.get("v") == bundle.get("v")
        and anchor.get("chain_id") == bundle.get("chain_id")
    )
    if not anchor_ok and not any(f.reason == "integrity(anchor)" for f in failures):
        failures.append(_failure(
            "integrity(anchor)", None,
            f"anchor mismatch: seq/head/signature/version/chain binding failed; "
            f"anchor_seq={anchor.get('seq')!r}, ledger_seq={last_seq!r}, "
            f"anchor_head={anchor.get('head')!r}, ledger_head={last_hash!r}",
        ))

    # 3) Reconstruct node authority and check child ⊆ parent.
    authorities: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event = entry.get("event")
        node = entry.get("node")
        if event == "root" and isinstance(node, str) and isinstance(entry.get("authority"), dict):
            authorities[node] = entry["authority"]
        elif event == "spawn" and isinstance(node, str) and isinstance(entry.get("granted"), dict):
            parent = entry.get("parent")
            parent_authority = authorities.get(parent)
            if parent_authority is None or not _authority_narrower(entry["granted"], parent_authority):
                failures.append(_failure("monotonicity", entry, f"grant for {node!r} is not within {parent!r}"))
            authorities[node] = entry["granted"]

    # 4) Every allow must be inside the acting node's reconstructed authority.
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("event") != "allow":
            continue
        authority = authorities.get(entry.get("node"))
        scope = entry.get("scope")
        context = entry.get("context") or {}
        if (authority is None or not isinstance(scope, str)
                or not any(_scope_covers(held, scope) for held in authority.get("scopes") or [])
                or not isinstance(context, dict) or not _context_within(authority, context)):
            failures.append(_failure("containment", entry, f"allow {scope!r} is outside reconstructed authority"))

    # 5) Schema-v2 execution binding.
    allow_positions: dict[str, list[int]] = {}
    for position, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("event") == "allow" and isinstance(entry.get("call_id"), str):
            allow_positions.setdefault(entry["call_id"], []).append(position)

    first_allow: dict[str, Mapping[str, Any]] = {}
    outcome_seen: set[str] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        event = entry.get("event")
        call_id = entry.get("call_id")
        if event == "allow":
            if not isinstance(call_id, str):
                failures.append(_failure("missing_call_id", entry, "allow has no call_id"))
                continue
            if call_id in first_allow:
                failures.append(_failure("duplicate_call_id", entry, f"second allow for call_id={call_id}"))
            else:
                first_allow[call_id] = entry
            continue

        if event != "outcome":
            continue
        if not isinstance(call_id, str):
            failures.append(_failure("outcome_without_allow", entry, "outcome has no call_id"))
            continue

        positions = allow_positions.get(call_id, [])
        prior_positions = [p for p in positions if p < position]
        later_positions = [p for p in positions if p > position]
        if not prior_positions:
            if later_positions:
                failures.append(_failure("outcome_before_allow", entry,
                                         f"outcome at {position} precedes allow at {later_positions[0]}"))
            else:
                failures.append(_failure("outcome_without_allow", entry,
                                         f"no allow exists for call_id={call_id}"))
            # It is still terminal for duplicate-outcome detection.
            if call_id in outcome_seen:
                failures.append(_failure("duplicate_outcome", entry,
                                         f"second terminal for call_id={call_id}"))
            outcome_seen.add(call_id)
            continue

        if call_id in outcome_seen:
            failures.append(_failure("duplicate_outcome", entry,
                                     f"second terminal for call_id={call_id}"))
        outcome_seen.add(call_id)

        # Bind to the first prior allow; duplicate allows are already a separate finding.
        allow_entry = entries[prior_positions[0]]
        if entry.get("node") != allow_entry.get("node"):
            failures.append(_failure("outcome_node_mismatch", entry,
                                     f"allow node={allow_entry.get('node')!r}, outcome node={entry.get('node')!r}"))
        if entry.get("invoked_params_hash") != allow_entry.get("authorized_params_hash"):
            failures.append(_failure("params_mismatch", entry,
                                     "invoked_params_hash differs from authorized_params_hash"))

    return failures


def score_document(document: Mapping[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    if document.get("version") != VECTOR_CONTRACT:
        raise ValueError(f"unexpected vector version: {document.get('version')!r}")
    if document.get("revision") != VECTOR_REVISION:
        raise ValueError(f"unexpected vector revision: {document.get('revision')!r}")
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("vector document has no cases list")
    names = [case.get("name") for case in cases]
    if names != PINNED_CASES:
        raise ValueError(f"unexpected case list/order: {names!r}")

    case_reports: list[dict[str, Any]] = []
    all_passed = True
    for case in cases:
        failures = verify_bundle(case["bundle"], case["signer"])
        observed = "accept" if not failures else "reject"
        expected = case["expect"]
        required = case.get("expect_failures") or []
        observed_keys = [failure.score_key() for failure in failures]
        missing = [item for item in required if item not in observed_keys]
        passed = observed == expected and not missing
        all_passed = all_passed and passed
        case_reports.append({
            "name": case["name"],
            "expected": expected,
            "observed": observed,
            "passed": passed,
            "required_failures": required,
            "missing_required_failures": missing,
            "failure_details": [asdict(failure) for failure in failures],
        })
    return all_passed, case_reports


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vectors", type=Path, help="path to released bundle_vectors_v1.json")
    parser.add_argument("--report", type=Path, help="write machine-readable report JSON")
    parser.add_argument("--allow-unpinned-bytes", action="store_true",
                        help="score a different corpus hash (reported, but not the pinned release proof)")
    args = parser.parse_args()

    # A runtime tripwire against accidentally importing either reference implementation.
    contaminated = sorted(name for name in sys.modules if name.startswith("attenu_guard"))
    if contaminated:
        raise RuntimeError(f"independence violation: imported reference modules: {contaminated}")

    raw = args.vectors.read_bytes()
    vector_sha = hashlib.sha256(raw).hexdigest()
    if vector_sha != PINNED_VECTOR_SHA256 and not args.allow_unpinned_bytes:
        raise ValueError(f"vector SHA-256 mismatch: got {vector_sha}, expected {PINNED_VECTOR_SHA256}")
    document = load_json_strict(raw)
    passed, cases = score_document(document)

    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {
        "verifier": {
            "id": VERIFIER_ID,
            "version": VERIFIER_VERSION,
            "source_sha256": source_sha,
            "independence_boundary": "stdlib-only; no attenu_guard imports; fixture read as raw bytes",
            "claim_boundary": "released bundle_vectors_v1.1 corpus only; not a general audit or runtime certification",
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "input": {
            "path": str(args.vectors),
            "bytes": len(raw),
            "sha256": vector_sha,
            "pinned_sha256": PINNED_VECTOR_SHA256,
            "contract": document.get("version"),
            "revision": document.get("revision"),
        },
        "summary": {
            "passed": passed,
            "cases_passed": sum(1 for case in cases if case["passed"]),
            "cases_total": len(cases),
        },
        "cases": cases,
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
