#!/usr/bin/env python3
"""Run the Attenu observer-envelope v1.2 scorer against exact published copies.

Envelope verification logic is intentionally reused byte-for-byte from the
already published v1.1 independent scorer. This runner changes only the frozen
subject pins and case set, then adds a focused row-19 discrimination check.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PYTHON_REPOSITORY = "attenu-io/attenu-guard"
PYTHON_COMMIT = "8a8d598e2036d6815b50df01b776a13777c1d72b"
PYTHON_RELEASE = "v0.15.0"
PYPI_PACKAGE = "attenu-guard==0.15.0"
TYPESCRIPT_REPOSITORY = "attenu-io/attenu-guard-ts"
TYPESCRIPT_COMMIT = "ae055c92ce2f23e476c42b1a742c3babfa543bb2"
TYPESCRIPT_RELEASE = "v0.9.0"
VECTOR_PATH = "tests/vectors/envelopes/envelope_vectors_v1.json"
TYPESCRIPT_VECTOR_PATH = "test/fixtures/vectors/envelopes/envelope_vectors_v1.json"
VECTOR_CONTRACT = "envelope_vectors_v1"
VECTOR_REVISION = "envelope_vectors_v1.2"
PINNED_VECTOR_SHA256 = "a8be5ff764a86122ca09e94340416b7169531bf5d0cc76a0b1fc87f8272eb16e"
PINNED_VECTOR_BYTES = 197_346
ROW19 = "reject_duplicate_subject_defective_second"

VERIFIER_ID = "safal207-independent-envelope-v1.2"
VERIFIER_VERSION = "0.2.0"
CORE_SOURCE = "proofs/attenu-envelope-v1.1-independent/verify_envelope_vectors.py"

OLD_CORPUS_CLAIM = "independent agreement with the frozen 18-case observer-envelope corpus"
NEW_CORPUS_CLAIM = "independent agreement with the frozen 19-case observer-envelope corpus"
OLD_COPY_CLAIM = "byte identity of repository, PyPI, and npm vector copies"
NEW_COPY_CLAIM = (
    "byte identity of Python repository, PyPI wheel, and TypeScript "
    "repository vector copies"
)
TYPESCRIPT_SOURCE = (
    f"{TYPESCRIPT_REPOSITORY}@{TYPESCRIPT_COMMIT}:{TYPESCRIPT_VECTOR_PATH}"
)


def _load_core() -> tuple[Any, Path]:
    path = Path(__file__).with_name("verify_envelope_vectors.py")
    spec = importlib.util.spec_from_file_location("cgqa_envelope_v12_core", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load core verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, path


def _patch_subject(core: Any) -> None:
    """Retarget the frozen-corpus scorer without changing verification logic."""
    core.VERIFIER_ID = VERIFIER_ID
    core.VERIFIER_VERSION = VERIFIER_VERSION
    core.UPSTREAM_REPOSITORY = PYTHON_REPOSITORY
    core.UPSTREAM_COMMIT = PYTHON_COMMIT
    core.VECTOR_PATH = VECTOR_PATH
    core.VECTOR_CONTRACT = VECTOR_CONTRACT
    core.VECTOR_REVISION = VECTOR_REVISION
    core.PINNED_VECTOR_SHA256 = PINNED_VECTOR_SHA256
    core.PYPI_PACKAGE = PYPI_PACKAGE
    core.NPM_PACKAGE = "attenu-guard@0.9.0"

    if list(core.CASE_NAMES)[-1] == ROW19:
        case_names = list(core.CASE_NAMES)
    else:
        case_names = [*core.CASE_NAMES, ROW19]
    core.CASE_NAMES = case_names
    core.ACCEPT_CASES = frozenset(case_names[:5])


def _keys(failures: list[Any]) -> list[dict[str, Any]]:
    return [failure.score_key() for failure in failures]


def _row19_discrimination(core: Any, document: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Show that row 19 distinguishes claim-first from validate-first ordering."""
    errors: list[str] = []
    cases = document.get("cases")
    if not isinstance(cases, list):
        raise ValueError("vector document cases must be a list")
    rows = [case for case in cases if isinstance(case, dict) and case.get("name") == ROW19]
    if len(rows) != 1:
        raise ValueError(f"expected one {ROW19!r} row, got {len(rows)}")
    row = rows[0]
    envelopes = row.get("bundle", {}).get("envelopes")
    if not isinstance(envelopes, list) or len(envelopes) != 2:
        raise ValueError("row 19 must carry exactly two envelopes")

    full_failures, full_states = core.verify_envelopes(row)
    full_keys = _keys(full_failures)
    required_duplicate = {
        "reason": "envelope_duplicate_subject",
        "seq": 1,
        "node": "vectors:n1",
    }
    if required_duplicate not in full_keys:
        errors.append(f"row 19 did not report the required duplicate: {full_keys}")
    if full_states.get("1") != core.PROCESS_ASSERTED:
        errors.append(
            "row 19 did not fall seq 1 back to process-asserted: "
            f"{full_states.get('1')!r}"
        )

    first_only = copy.deepcopy(row)
    first_only["bundle"]["envelopes"] = [copy.deepcopy(envelopes[0])]
    first_failures, first_states = core.verify_envelopes(first_only)
    if first_failures:
        errors.append(f"first envelope alone was not valid: {_keys(first_failures)}")
    if first_states.get("1") != core.WITNESS_SIGNED:
        errors.append(
            "first envelope alone did not make seq 1 witness-signed: "
            f"{first_states.get('1')!r}"
        )

    second_only = copy.deepcopy(row)
    second_only["bundle"]["envelopes"] = [copy.deepcopy(envelopes[1])]
    second_failures, second_states = core.verify_envelopes(second_only)
    second_keys = _keys(second_failures)
    expected_bad_signature = {
        "reason": "envelope_bad_signature",
        "seq": 1,
        "node": "vectors:n1",
    }
    if expected_bad_signature not in second_keys:
        errors.append(
            "defective second envelope alone did not expose bad signature: "
            f"{second_keys}"
        )
    if second_states.get("1") != core.PROCESS_ASSERTED:
        errors.append(
            "defective second envelope alone unexpectedly verified seq 1: "
            f"{second_states.get('1')!r}"
        )

    return {
        "case": ROW19,
        "claim_first_full_row": {
            "required_failure": required_duplicate,
            "state_seq_1": full_states.get("1"),
        },
        "first_envelope_alone": {
            "failures": _keys(first_failures),
            "state_seq_1": first_states.get("1"),
        },
        "defective_second_alone": {
            "required_failure": expected_bad_signature,
            "state_seq_1": second_states.get("1"),
        },
        "distinguishes": (
            "claiming subject.seq before later validation prevents a defective "
            "duplicate from leaving the first envelope witness-signed"
        ),
    }, errors


def _replace_required(values: Any, old: str, new: str, errors: list[str]) -> None:
    if not isinstance(values, list) or old not in values:
        errors.append(f"report did not expose expected claim text: {old!r}")
        return
    values[values.index(old)] = new


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", required=True, type=Path)
    parser.add_argument("--python-vector", required=True, type=Path)
    parser.add_argument("--typescript-vector", required=True, type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()

    try:
        core, core_path = _load_core()
        _patch_subject(core)

        vector_bytes = args.vectors.read_bytes()
        if len(vector_bytes) != PINNED_VECTOR_BYTES:
            raise ValueError(
                f"vector byte count mismatch: {len(vector_bytes)} != {PINNED_VECTOR_BYTES}"
            )
        document = core.load_json_strict(vector_bytes)
        if not isinstance(document, dict):
            raise ValueError("vector document must be an object")

        report, errors = core.build_report(
            args.vectors,
            args.python_vector,
            args.typescript_vector,
        )

        copies = report.get("subject", {}).get("source_copies")
        if not isinstance(copies, list) or len(copies) != 3:
            errors.append(
                "source topology mismatch: expected Python repository, PyPI wheel, "
                "and TypeScript repository copies"
            )
        else:
            copies[2]["source"] = TYPESCRIPT_SOURCE

        proved = report.get("claim_boundary", {}).get("proved")
        _replace_required(proved, OLD_CORPUS_CLAIM, NEW_CORPUS_CLAIM, errors)
        _replace_required(proved, OLD_COPY_CLAIM, NEW_COPY_CLAIM, errors)

        errors = [
            error.replace("npm attenu-guard@0.9.0", TYPESCRIPT_SOURCE)
            for error in errors
        ]

        discrimination, discrimination_errors = _row19_discrimination(core, document)
        errors.extend(f"{ROW19}: {error}" for error in discrimination_errors)

        report["subject"]["bytes"] = PINNED_VECTOR_BYTES
        report["subject"]["python_release"] = PYTHON_RELEASE
        report["subject"]["typescript_release"] = TYPESCRIPT_RELEASE
        report["verifier"]["id"] = VERIFIER_ID
        report["verifier"]["version"] = VERIFIER_VERSION
        report["verifier"]["core_source"] = CORE_SOURCE
        report["verifier"]["core_sha256"] = hashlib.sha256(
            core_path.read_bytes()
        ).hexdigest()
        report["verifier"]["logic_delta_from_v1_1"] = (
            "none; the envelope verification core is byte-identical"
        )
        report["row19_discrimination"] = discrimination
        report["summary"]["overall"] = "AGREE" if not errors else "DISAGREE"

        core.write_json(args.json_out, report)
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
