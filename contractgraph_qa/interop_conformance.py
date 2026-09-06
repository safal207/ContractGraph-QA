"""Portable conformance vectors for the CGQA <-> LiminalQA evidence boundary.

The suite is deliberately language-neutral JSON.  This module is the Python
reference runner, not the normative owner of Rust, Elixir, Node, or future
language implementations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from contractgraph_qa import __version__
from contractgraph_qa.liminalqa_interop import (
    CGQA_EVIDENCE_PROFILE,
    CGQA_EVIDENCE_SCHEMA,
    LIMINAL_CANDIDATE_PROFILE,
    LIMINAL_CANDIDATE_SCHEMA,
    LiminalQaInteropError,
    _decode_profile_bytes,
    canonical_json_bytes,
    import_liminalqa_candidates,
    validate_liminalqa_evidence_export,
)

SUITE_SCHEMA = "org.contractgraph-qa.liminalqa-interop-conformance-suite.v0.1"
RESULT_SCHEMA = "org.contractgraph-qa.liminalqa-interop-conformance-result.v0.1"
SUITE_VERSION = "0.1.0"
SUITE_ID = "cgqa-liminalqa-v0.1"
SUITE_SHA256 = "562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac"
SUITE_SCHEMA_SHA256 = "34acfc677802683c6c452a728ed533e92803a74d989b397d2d0fe549b1da93f9"
RESULT_SCHEMA_SHA256 = "388d0aadbb8d30fb5aee223a89f29884b89a1b3303ac88dae8b21e91ab11b423"
VALID_NON_AUTHORIZING = "VALID_NON_AUTHORIZING"
INVALID_BLOCKED = "INVALID_BLOCKED"
UNSAFE_ACCEPTED = "UNSAFE_ACCEPTED"
CLAIM_BOUNDARY = (
    "Synthetic conformance verifies adapter behavior only for these pinned fixtures and mutations. "
    "It does not verify a production system, prove security or completeness, authorize an action, "
    "or replace independent replay against the exact subject."
)
DEFAULT_SUITE_PATH = (
    Path(__file__).resolve().parent
    / "conformance"
    / "liminalqa-v0.1"
    / "suite.json"
)

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")

_EXPECTED_CONTRACTS = {
    CGQA_EVIDENCE_SCHEMA: {
        "artifactProfile": CGQA_EVIDENCE_PROFILE,
        "ownerRepository": "safal207/ContractGraph-QA",
        "producerCommit": "bdf7ced074e3a7baf57cf89ac68be9674bd76a02",
        "schemaSha256": "53b0b4a0b1f4d77de26b8be9dbb90006ea0bd30c5cd3960a2f3e7d44d9664184",
        "fixtureSha256": "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce",
    },
    LIMINAL_CANDIDATE_SCHEMA: {
        "artifactProfile": LIMINAL_CANDIDATE_PROFILE,
        "ownerRepository": "safal207/LiminalQAengineer",
        "producerCommit": "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3",
        "schemaSha256": "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60",
        "fixtureSha256": "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3",
    },
}

_TOP_LEVEL_KEYS = {
    "schema",
    "suiteId",
    "version",
    "suiteSchema",
    "resultSchema",
    "contracts",
    "cases",
    "claimBoundary",
}
_CONTRACT_KEYS = {
    "id",
    "artifactSchema",
    "artifactProfile",
    "ownerRepository",
    "producerCommit",
    "schemaPath",
    "schemaSha256",
    "fixturePath",
    "fixtureSha256",
}
_CASE_KEYS = {
    "id",
    "contract",
    "category",
    "description",
    "operation",
    "expectedInputSha256",
    "expectedSemantics",
}
_CATEGORIES = {
    "golden",
    "authority_escalation",
    "semantic_mismatch",
    "temporal_inversion",
    "unknown_field",
    "ambiguous_json",
    "verification_weakening",
    "unsafe_identifier",
}


class InteropConformanceError(ValueError):
    """The suite, its assets, or an operation is invalid."""


class _DuplicateJsonKey(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InteropConformanceError(message)


def _exact_keys(value: dict[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extras = sorted(set(value) - expected)
    _require(not missing, f"{field} is missing required fields: {', '.join(missing)}")
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value


def _safe_id(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_SAFE_ID.fullmatch(text)), f"{field} must be a safe identifier")
    return text


def _digest(value: Any, field: str, pattern: re.Pattern[str]) -> str:
    text = _text(value, field)
    _require(bool(pattern.fullmatch(text)), f"{field} has an invalid digest")
    return text


def _relative_json_path(value: Any, field: str) -> str:
    text = _text(value, field)
    path = Path(text)
    _require(not path.is_absolute(), f"{field} must be relative")
    _require(".." not in path.parts, f"{field} must not contain parent traversal")
    _require(path.suffix == ".json", f"{field} must name a JSON file")
    return text


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _strict_json(raw: bytes, field: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise InteropConformanceError(f"{field} is not valid unambiguous JSON: {exc}") from exc
    _require(isinstance(value, dict), f"{field} must contain one JSON object")
    return value


def _suite_file(path: Path | None) -> Path:
    candidate = path or DEFAULT_SUITE_PATH
    _require(not candidate.is_symlink(), "suite must not be a symbolic link")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InteropConformanceError(f"suite cannot be resolved: {exc}") from exc
    _require(resolved.is_file(), "suite must be a regular file")
    return resolved


def load_interop_conformance_suite(path: Path | None = None) -> dict[str, Any]:
    """Load and structurally validate one conformance suite."""

    suite_path = _suite_file(path)
    suite_raw = suite_path.read_bytes()
    _require(_sha256(suite_raw) == SUITE_SHA256, "suite digest does not match the v0.1 pin")
    suite = _strict_json(suite_raw, "suite")
    validate_interop_conformance_suite(suite)
    return suite


def validate_interop_conformance_suite(suite: Any) -> None:
    """Validate manifest structure and immutable v0.1 contract pins."""

    _require(isinstance(suite, dict), "suite must be an object")
    _exact_keys(suite, _TOP_LEVEL_KEYS, "suite")
    _require(suite.get("schema") == SUITE_SCHEMA, f"suite.schema must be {SUITE_SCHEMA}")
    _require(suite.get("suiteId") == SUITE_ID, f"suite.suiteId must be {SUITE_ID}")
    _require(suite.get("version") == SUITE_VERSION, f"suite.version must be {SUITE_VERSION}")
    _require(suite.get("claimBoundary") == CLAIM_BOUNDARY, "suite.claimBoundary does not match the v0.1 boundary")

    suite_schema = suite.get("suiteSchema")
    _require(isinstance(suite_schema, dict), "suite.suiteSchema must be an object")
    _exact_keys(suite_schema, {"path", "sha256"}, "suite.suiteSchema")
    _require(suite_schema.get("path") == "suite.schema.json", "suite.suiteSchema.path is unsupported")
    _require(
        suite_schema.get("sha256") == SUITE_SCHEMA_SHA256,
        "suite.suiteSchema.sha256 does not match the v0.1 pin",
    )

    result_schema = suite.get("resultSchema")
    _require(isinstance(result_schema, dict), "suite.resultSchema must be an object")
    _exact_keys(result_schema, {"path", "sha256"}, "suite.resultSchema")
    _require(result_schema.get("path") == "result.schema.json", "suite.resultSchema.path is unsupported")
    _require(
        result_schema.get("sha256") == RESULT_SCHEMA_SHA256,
        "suite.resultSchema.sha256 does not match the v0.1 pin",
    )

    contracts = suite.get("contracts")
    _require(isinstance(contracts, list) and bool(contracts), "suite.contracts must be non-empty")
    contract_ids: set[str] = set()
    contract_schemas: set[str] = set()
    for index, contract in enumerate(contracts):
        field = f"suite.contracts[{index}]"
        _require(isinstance(contract, dict), f"{field} must be an object")
        _exact_keys(contract, _CONTRACT_KEYS, field)
        contract_id = _safe_id(contract.get("id"), f"{field}.id")
        _require(contract_id not in contract_ids, f"duplicate contract id: {contract_id}")
        contract_ids.add(contract_id)
        schema = _text(contract.get("artifactSchema"), f"{field}.artifactSchema")
        _require(schema not in contract_schemas, f"duplicate artifact schema: {schema}")
        contract_schemas.add(schema)
        expected = _EXPECTED_CONTRACTS.get(schema)
        _require(expected is not None, f"{field}.artifactSchema is unsupported")
        for key in ("artifactProfile", "ownerRepository", "producerCommit", "schemaSha256", "fixtureSha256"):
            _require(contract.get(key) == expected[key], f"{field}.{key} does not match the v0.1 pin")
        _require(bool(_REPOSITORY.fullmatch(contract["ownerRepository"])), f"{field}.ownerRepository is invalid")
        _digest(contract["producerCommit"], f"{field}.producerCommit", _HEX40)
        _relative_json_path(contract.get("schemaPath"), f"{field}.schemaPath")
        _relative_json_path(contract.get("fixturePath"), f"{field}.fixturePath")

    _require(contract_schemas == set(_EXPECTED_CONTRACTS), "suite.contracts must cover both v0.1 schemas")

    cases = suite.get("cases")
    _require(isinstance(cases, list) and len(cases) == 14, "suite.cases must contain 14 vectors")
    case_ids: set[str] = set()
    coverage = {contract_id: set() for contract_id in contract_ids}
    categories: set[str] = set()
    for index, case in enumerate(cases):
        field = f"suite.cases[{index}]"
        _require(isinstance(case, dict), f"{field} must be an object")
        _exact_keys(case, _CASE_KEYS, field)
        case_id = _safe_id(case.get("id"), f"{field}.id")
        _require(case_id not in case_ids, f"duplicate case id: {case_id}")
        case_ids.add(case_id)
        contract_id = _safe_id(case.get("contract"), f"{field}.contract")
        _require(contract_id in contract_ids, f"{field}.contract is unknown")
        category = _text(case.get("category"), f"{field}.category")
        _require(category in _CATEGORIES, f"{field}.category is unsupported")
        categories.add(category)
        _text(case.get("description"), f"{field}.description")
        _digest(case.get("expectedInputSha256"), f"{field}.expectedInputSha256", _HEX64)
        expected_semantics = case.get("expectedSemantics")
        _require(
            expected_semantics in {VALID_NON_AUTHORIZING, INVALID_BLOCKED},
            f"{field}.expectedSemantics is unsupported",
        )
        coverage[contract_id].add(expected_semantics)
        _validate_operation(case.get("operation"), f"{field}.operation")

    for contract_id, outcomes in coverage.items():
        _require(
            outcomes == {VALID_NON_AUTHORIZING, INVALID_BLOCKED},
            f"contract {contract_id} must include valid and invalid cases",
        )
    _require(categories == _CATEGORIES, "suite.cases must cover every v0.1 control category")


def _validate_operation(operation: Any, field: str) -> None:
    _require(isinstance(operation, dict), f"{field} must be an object")
    kind = operation.get("kind")
    if kind == "identity":
        _exact_keys(operation, {"kind"}, field)
        return
    if kind in {"replace", "add"}:
        _exact_keys(operation, {"kind", "pointer", "value"}, field)
        _json_pointer(operation.get("pointer"), f"{field}.pointer")
        canonical_json_bytes(operation.get("value"))
        return
    if kind == "remove":
        _exact_keys(operation, {"kind", "pointer"}, field)
        _json_pointer(operation.get("pointer"), f"{field}.pointer")
        return
    if kind == "duplicate_root_key":
        _exact_keys(operation, {"kind", "key", "value"}, field)
        _text(operation.get("key"), f"{field}.key")
        canonical_json_bytes(operation.get("value"))
        return
    raise InteropConformanceError(f"{field}.kind is unsupported")


def _json_pointer(value: Any, field: str) -> str:
    pointer = _text(value, field)
    _require(pointer.startswith("/"), f"{field} must be a JSON Pointer")
    _require(re.search(r"~(?:[^01]|$)", pointer) is None, f"{field} contains an invalid escape")
    return pointer


def _resolve_asset(root: Path, relative: str, field: str) -> Path:
    path = Path(_relative_json_path(relative, field))
    unresolved = root / path
    _require(not unresolved.is_symlink(), f"{field} must not be a symbolic link")
    try:
        resolved = unresolved.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InteropConformanceError(f"{field} cannot be resolved: {exc}") from exc
    _require(resolved.is_relative_to(root.resolve()), f"{field} escapes the suite root")
    _require(resolved.is_file(), f"{field} must be a regular file")
    return resolved


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _verify_assets(suite: dict[str, Any], root: Path) -> dict[str, tuple[dict[str, Any], bytes]]:
    suite_schema = suite["suiteSchema"]
    suite_schema_path = _resolve_asset(root, suite_schema["path"], "suite.suiteSchema.path")
    suite_schema_raw = suite_schema_path.read_bytes()
    _require(
        _sha256(suite_schema_raw) == suite_schema["sha256"],
        "suite schema digest does not match suite.suiteSchema.sha256",
    )
    _strict_json(suite_schema_raw, "suite schema")

    result_schema = suite["resultSchema"]
    result_schema_path = _resolve_asset(root, result_schema["path"], "suite.resultSchema.path")
    result_schema_raw = result_schema_path.read_bytes()
    _require(
        _sha256(result_schema_raw) == result_schema["sha256"],
        "result schema digest does not match suite.resultSchema.sha256",
    )
    _strict_json(result_schema_raw, "result schema")

    assets: dict[str, tuple[dict[str, Any], bytes]] = {}
    for index, contract in enumerate(suite["contracts"]):
        field = f"suite.contracts[{index}]"
        schema_path = _resolve_asset(root, contract["schemaPath"], f"{field}.schemaPath")
        fixture_path = _resolve_asset(root, contract["fixturePath"], f"{field}.fixturePath")
        schema_raw = schema_path.read_bytes()
        fixture_raw = fixture_path.read_bytes()
        _require(_sha256(schema_raw) == contract["schemaSha256"], f"{field} schema digest mismatch")
        _require(_sha256(fixture_raw) == contract["fixtureSha256"], f"{field} fixture digest mismatch")
        _strict_json(schema_raw, f"{field} schema")
        fixture = _decode_profile_bytes(fixture_raw, f"{field} fixture")
        _require(fixture.get("schema") == contract["artifactSchema"], f"{field} fixture schema mismatch")
        _require(fixture.get("profile") == contract["artifactProfile"], f"{field} fixture profile mismatch")
        assets[contract["id"]] = (contract, fixture_raw)
    return assets


def _pointer_tokens(pointer: str) -> list[str]:
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def _container_and_key(document: Any, pointer: str) -> tuple[Any, str | int]:
    tokens = _pointer_tokens(pointer)
    _require(bool(tokens), "operation pointer must not target the document root")
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict):
            _require(token in current, f"operation pointer component does not exist: {token}")
            current = current[token]
        elif isinstance(current, list):
            _require(token.isdigit(), f"operation list pointer is invalid: {token}")
            index = int(token)
            _require(index < len(current), f"operation list index is out of range: {index}")
            current = current[index]
        else:
            raise InteropConformanceError("operation pointer traverses a scalar value")
    final = tokens[-1]
    if isinstance(current, list):
        _require(final.isdigit(), f"operation list pointer is invalid: {final}")
        return current, int(final)
    _require(isinstance(current, dict), "operation pointer parent must be an object or array")
    return current, final


def _apply_operation(base_raw: bytes, operation: dict[str, Any]) -> bytes:
    kind = operation["kind"]
    base = _decode_profile_bytes(base_raw, "case fixture")
    if kind == "identity":
        return base_raw
    if kind == "duplicate_root_key":
        key = operation["key"]
        _require(key in base, f"duplicate_root_key target does not exist: {key}")
        stripped = base_raw.lstrip()
        _require(stripped.startswith(b"{"), "duplicate_root_key requires an object fixture")
        prefix = canonical_json_bytes(key) + b":" + canonical_json_bytes(operation["value"]) + b","
        return b"{" + prefix + stripped[1:]

    document = copy.deepcopy(base)
    container, key = _container_and_key(document, operation["pointer"])
    if isinstance(container, list):
        _require(isinstance(key, int), "list operation requires an integer index")
        if kind == "add":
            _require(key <= len(container), f"operation list index is out of range: {key}")
            container.insert(key, copy.deepcopy(operation["value"]))
        else:
            _require(key < len(container), f"operation list index is out of range: {key}")
            if kind == "replace":
                container[key] = copy.deepcopy(operation["value"])
            else:
                del container[key]
    else:
        if kind == "add":
            _require(key not in container, f"add target already exists: {key}")
            container[key] = copy.deepcopy(operation["value"])
        else:
            _require(key in container, f"operation target does not exist: {key}")
            if kind == "replace":
                container[key] = copy.deepcopy(operation["value"])
            else:
                del container[key]
    return canonical_json_bytes(document) + b"\n"


def _observe(artifact_schema: str, raw: bytes) -> tuple[str, str]:
    try:
        profile = _decode_profile_bytes(raw, "case input")
        if artifact_schema == CGQA_EVIDENCE_SCHEMA:
            evidence = validate_liminalqa_evidence_export(profile)
            if evidence["authority"]["mayAuthorizeAction"] is not False:
                return UNSAFE_ACCEPTED, "adapter accepted evidence with action authority"
        elif artifact_schema == LIMINAL_CANDIDATE_SCHEMA:
            receipt = import_liminalqa_candidates(profile, source_bytes=raw)
            authority = profile["authority"]
            if authority["mayAuthorizeAction"] is not False or receipt["mayAuthorizeAction"] is not False:
                return UNSAFE_ACCEPTED, "adapter accepted candidate authority escalation"
            if (
                authority["requiresCgqaVerification"] is not True
                or receipt["requiresFreshCgqaVerification"] is not True
            ):
                return UNSAFE_ACCEPTED, "adapter accepted weakened fresh-verification requirements"
        else:
            raise InteropConformanceError(f"unsupported artifact schema: {artifact_schema}")
        return VALID_NON_AUTHORIZING, "profile accepted without action authority"
    except LiminalQaInteropError as exc:
        return INVALID_BLOCKED, str(exc)


def run_interop_conformance_suite(path: Path | None = None) -> dict[str, Any]:
    """Run all vectors with the Python reference adapter.

    This function performs validation only.  It makes no network call, does not
    execute a candidate, and cannot authorize a target-system action.
    """

    suite_path = _suite_file(path)
    suite_raw = suite_path.read_bytes()
    _require(_sha256(suite_raw) == SUITE_SHA256, "suite digest does not match the v0.1 pin")
    suite = _strict_json(suite_raw, "suite")
    validate_interop_conformance_suite(suite)
    assets = _verify_assets(suite, suite_path.parent)

    results: list[dict[str, Any]] = []
    for case in suite["cases"]:
        contract, fixture_raw = assets[case["contract"]]
        case_raw = _apply_operation(fixture_raw, case["operation"])
        _require(
            _sha256(case_raw) == case["expectedInputSha256"],
            f"case {case['id']} mutation digest does not match the v0.1 pin",
        )
        observed, diagnostic = _observe(contract["artifactSchema"], case_raw)
        status = "PASS" if observed == case["expectedSemantics"] else "FAIL"
        results.append(
            {
                "id": case["id"],
                "contract": case["contract"],
                "category": case["category"],
                "status": status,
                "expectedSemantics": case["expectedSemantics"],
                "observedSemantics": observed,
                "inputSha256": _sha256(case_raw),
                "diagnostic": diagnostic,
                "sideEffectExecuted": False,
            }
        )

    passed = sum(result["status"] == "PASS" for result in results)
    report = {
        "schema": RESULT_SCHEMA,
        "suiteId": suite["suiteId"],
        "suiteVersion": suite["version"],
        "suiteSha256": _sha256(suite_raw),
        "implementation": {
            "name": "contractgraph-qa",
            "version": __version__,
            "language": "python",
        },
        "status": "PASS" if passed == len(results) else "FAIL",
        "counts": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "contractPins": [
            {
                key: contract[key]
                for key in (
                    "id",
                    "artifactSchema",
                    "artifactProfile",
                    "ownerRepository",
                    "producerCommit",
                    "schemaSha256",
                    "fixtureSha256",
                )
            }
            for contract in suite["contracts"]
        ],
        "results": results,
        "authority": {"classification": "conformance_evidence_only", "mayAuthorizeAction": False},
        "claimBoundary": suite["claimBoundary"],
    }
    report["reportId"] = (
        "cgqa-interop-conformance-" + _sha256(canonical_json_bytes(report))[:24]
    )
    return report
