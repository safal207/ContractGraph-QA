#!/usr/bin/env python3
"""Run the bounded FCRP-SYSTEM-007 cross-repository conformance proof.

The runner deliberately keeps native external operations in the workflow. It
builds and independently replays the deterministic boundaries around those
operations:

    intent -> ProofPath -> CML -> LiminalDB -> RINSE -> ContractGraph-QA

It never sends a provider request, performs a wallet action, deploys, mutates
source history, or grants execution authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping


CASE_ID = "FCRP-SYSTEM-007"
LOGICAL_OPERATION_ID = "neo-resonance-system-007-001"
PROOFPATH_CAPABILITY_COMMIT = "685d50e256a5125a21f4c4584b326411caaa64ad"
LIMINALDB_IMPORT_COMMIT = "00580ff097dee61b45ad3c8a3c36ae5f548f572d"
LIMINALDB_AUDIT_EVENT_BLOB = "fd733971aaae089df770062bcf7f2c2d6d19ca1d"
LIMINALDB_DURABLE_COMMIT = "61b02fc81e0cb5cf1f1ed4658ecff58f683cb728"
RINSE_REVIEWED_TIME = "2026-08-14T08:02:00Z"
EXPECTED_CHAIN = ["intent", "proofpath", "cml", "liminaldb", "rinse", "contractgraph_qa"]


class System007Error(ValueError):
    """Raised when a SYSTEM-007 invariant is not satisfied."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise System007Error(f"value is not canonical JSON: {exc}") from exc


def sha256_hex(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_ref(value: object) -> str:
    return "sha256:" + sha256_hex(value)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise System007Error(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise System007Error(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise System007Error(f"{field} must be a non-empty string")
    return value.strip()


def require_false(value: object, field: str) -> None:
    if value is not False:
        raise System007Error(f"{field} must be false")


def validate_intent(
    intent: Mapping[str, Any],
    *,
    used_nonces: set[str] | None = None,
) -> dict[str, str]:
    """Validate the current intent and reject replay or argument drift."""

    if not isinstance(intent, Mapping):
        raise System007Error("intent must be an object")
    if intent.get("schema") != "cgqa.system-007-intent.v0.1":
        raise System007Error("intent.schema is unsupported")
    if intent.get("case_id") != CASE_ID:
        raise System007Error("intent.case_id must identify FCRP-SYSTEM-007")

    logical_operation_id = require_text(
        intent.get("logical_operation_id"), "intent.logical_operation_id"
    )
    if logical_operation_id != LOGICAL_OPERATION_ID:
        raise System007Error("intent.logical_operation_id is not the pinned operation")

    nonce = require_text(intent.get("nonce"), "intent.nonce")
    if used_nonces is not None and nonce in used_nonces:
        raise System007Error("intent nonce was already consumed")

    require_text(intent.get("observed_at"), "intent.observed_at")
    require_text(intent.get("reviewed_at"), "intent.reviewed_at")
    intent_body = intent.get("intent")
    if not isinstance(intent_body, Mapping):
        raise System007Error("intent.intent must be an object")
    require_text(intent_body.get("kind"), "intent.intent.kind")
    require_text(intent_body.get("purpose"), "intent.intent.purpose")
    require_text(intent_body.get("expected_outcome"), "intent.intent.expected_outcome")

    arguments = intent.get("arguments")
    if not isinstance(arguments, Mapping) or not arguments:
        raise System007Error("intent.arguments must be a non-empty object")
    recorded_digest = require_text(intent.get("argument_digest"), "intent.argument_digest")
    expected_digest = sha256_ref(arguments)
    if recorded_digest != expected_digest:
        raise System007Error(
            "intent.argument_digest does not match the canonical argument object"
        )

    authority = intent.get("authority")
    if not isinstance(authority, Mapping):
        raise System007Error("intent.authority must be an object")
    require_text(authority.get("evidence_ref"), "intent.authority.evidence_ref")
    for field in (
        "execution_authorized",
        "mutation_authorized",
        "external_effects_authorized",
    ):
        require_false(authority.get(field), f"intent.authority.{field}")

    parents = intent.get("parents")
    if parents != []:
        raise System007Error("SYSTEM-007 intent must have an explicit empty parent list")

    return {
        "logical_operation_id": logical_operation_id,
        "nonce": nonce,
        "argument_digest": recorded_digest,
        "observed_at": require_text(intent.get("observed_at"), "intent.observed_at"),
        "reviewed_at": require_text(intent.get("reviewed_at"), "intent.reviewed_at"),
    }


def compare_declared_heads(
    observed: Mapping[str, str],
    expected: Mapping[str, str],
) -> None:
    for name, expected_sha in expected.items():
        actual = observed.get(name)
        if actual != expected_sha:
            raise System007Error(
                f"stale dependency head for {name}: expected {expected_sha}, observed {actual}"
            )


def git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise System007Error(f"cannot resolve exact head for {root}: {exc}") from exc


def assert_exact_heads(args: argparse.Namespace) -> dict[str, str]:
    roots = {
        "contractgraph_qa": (Path(args.cgqa_root), args.subject_head),
        "proofpath": (Path(args.proofpath_root), args.proofpath_head),
        "cml": (Path(args.cml_root), args.cml_head),
        "liminaldb": (Path(args.liminaldb_root), args.liminaldb_head),
        "rinse": (Path(args.rinse_root), args.rinse_head),
    }
    observed = {name: git_head(root) for name, (root, _expected) in roots.items()}
    compare_declared_heads(observed, {name: expected for name, (_root, expected) in roots.items()})
    return observed


def _cml_api(cml_root: Path) -> tuple[Any, Any, Any, Any, Any, Any]:
    root = str(cml_root.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from cml import Actor, Action, CausalRecord, reconstruct_chain, records_to_index
    except (ImportError, AttributeError) as exc:
        raise System007Error(f"cannot import the pinned CML API: {exc}") from exc
    return Actor, Action, CausalRecord, reconstruct_chain, records_to_index, root


def _record(
    CausalRecord: Any,
    Actor: Any,
    *,
    record_id: str,
    timestamp: int,
    action: str,
    object_value: dict[str, Any],
    permitted_by: str,
    parent_cause: str | None,
) -> Any:
    record = CausalRecord(
        id=record_id,
        timestamp=timestamp,
        actor=Actor(pid=7007, uid=0, comm="fcrp-system-007"),
        action=action,
        object=object_value,
        permitted_by=permitted_by,
        parent_cause=parent_cause,
    )
    record.integrity = sha256_ref(record.to_dict())
    return record


def build_cml_chain(
    cml_root: Path,
    *,
    logical_operation_id: str,
    intent_digest: str,
    scig_projection_digest: str,
) -> tuple[list[Any], dict[str, Any]]:
    Actor, Action, CausalRecord, reconstruct_chain, records_to_index, _ = _cml_api(cml_root)
    root = _record(
        CausalRecord,
        Actor,
        record_id="system-007-intent",
        timestamp=1,
        action=Action.OPEN,
        object_value={
            "logical_operation_id": logical_operation_id,
            "intent_digest": intent_digest,
            "stage": "intent",
        },
        permitted_by="root_event:fcrp-system-007",
        parent_cause=None,
    )
    proofpath = _record(
        CausalRecord,
        Actor,
        record_id="system-007-proofpath-decision",
        timestamp=2,
        action=Action.READ,
        object_value={
            "logical_operation_id": logical_operation_id,
            "decision": "STOP",
            "scig_projection_digest": scig_projection_digest,
            "stage": "proofpath",
        },
        permitted_by=f"intent:{intent_digest}",
        parent_cause=root.id,
    )
    cml_record = _record(
        CausalRecord,
        Actor,
        record_id="system-007-cml-causal-record",
        timestamp=3,
        action=Action.WRITE,
        object_value={
            "logical_operation_id": logical_operation_id,
            "source_record": proofpath.id,
            "stage": "cml",
            "causal_claim": "proofpath decision is linked to the declared intent",
        },
        permitted_by=f"proofpath:{proofpath.id}",
        parent_cause=proofpath.id,
    )
    records = [root, proofpath, cml_record]
    index = records_to_index(records)
    chain = reconstruct_chain(cml_record.id, index)
    expected_ids = [root.id, proofpath.id, cml_record.id]
    if [record.id for record in chain] != expected_ids:
        raise System007Error("CML did not reconstruct the expected root-first causal chain")
    if any(
        record.object.get("logical_operation_id") != logical_operation_id
        for record in chain
    ):
        raise System007Error("CML changed logical_operation_id inside the causal chain")
    chain_digest = sha256_ref([record.to_dict() for record in chain])
    return records, {
        "schema": "cgqa.system-007-cml-chain.v0.1",
        "logical_operation_id": logical_operation_id,
        "chain_ids": expected_ids,
        "terminal_record_id": cml_record.id,
        "chain_sha256": chain_digest,
        "record_count": len(records),
        "source_revision": git_head(cml_root),
    }


def write_cml_records(path: Path, records: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def read_cml_chain(
    path: Path,
    cml_root: Path,
    *,
    logical_operation_id: str,
    expected_ids: list[str],
) -> dict[str, Any]:
    _Actor, _Action, CausalRecord, reconstruct_chain, records_to_index, _ = _cml_api(cml_root)
    records = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = CausalRecord.from_dict(json.loads(raw))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise System007Error(f"invalid CML record at line {line_number}: {exc}") from exc
        raw_record = record.to_dict()
        integrity = raw_record.pop("integrity", None)
        if integrity != sha256_ref(raw_record):
            raise System007Error(f"CML record {record.id} integrity mismatch")
        records.append(record)
    if len(records) != len(expected_ids):
        raise System007Error("CML record count changed")
    index = records_to_index(records)
    chain = reconstruct_chain(expected_ids[-1], index)
    if [record.id for record in chain] != expected_ids:
        raise System007Error("CML parent-cause lineage changed")
    if any(
        record.object.get("logical_operation_id") != logical_operation_id
        for record in chain
    ):
        raise System007Error("CML logical operation identity changed")
    return {
        "chain_ids": [record.id for record in chain],
        "chain_sha256": sha256_ref([record.to_dict() for record in chain]),
        "record_count": len(records),
        "terminal_record_id": expected_ids[-1],
    }


def assert_reflection_boundary(loop: Mapping[str, Any]) -> None:
    if not isinstance(loop, Mapping):
        raise System007Error("RINSE loop must be an object")
    if loop.get("source_mutated") is not False:
        raise System007Error("RINSE source_mutated must remain false")
    if loop.get("write_back_performed") is not False:
        raise System007Error("RINSE write_back_performed must remain false")
    graph = loop.get("graph")
    if not isinstance(graph, Mapping):
        raise System007Error("RINSE graph must be an object")
    if graph.get("verdict") != "ACCEPT_WITH_LIMITS":
        raise System007Error("RINSE graph verdict must remain ACCEPT_WITH_LIMITS")
    authority = graph.get("authority")
    if not isinstance(authority, Mapping):
        raise System007Error("RINSE graph authority must be an object")
    if authority.get("classification") != "REFLECTION_ONLY":
        raise System007Error("RINSE graph authority must remain REFLECTION_ONLY")
    for field in ("truth_authorized", "execution_authorized", "mutation_authorized"):
        if authority.get(field) is True:
            raise System007Error(f"RINSE graph escalated {field}")
    handoffs = graph.get("candidate_handoffs")
    if not isinstance(handoffs, list):
        raise System007Error("RINSE candidate_handoffs must be an array")
    for index, handoff in enumerate(handoffs):
        if not isinstance(handoff, Mapping):
            raise System007Error(f"RINSE handoff {index} must be an object")
        if handoff.get("execution_allowed") is True:
            raise System007Error(f"RINSE handoff {index} became executable")


def expect_rejection(
    negative_cases: dict[str, str],
    name: str,
    operation: Callable[[], object],
) -> None:
    try:
        operation()
    except Exception:
        negative_cases[name] = "REJECTED"
    else:
        raise System007Error(f"negative case {name} was accepted")


def prepare(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    heads = assert_exact_heads(args)
    intent = load_json(Path(args.intent))
    identity = validate_intent(intent)
    source_case = load_json(Path(args.source_case))
    if source_case.get("caseId") != "CGQA-PROOFPATH-001":
        raise System007Error("SYSTEM-007 must start from the reviewed CGQA-PROOFPATH-001 fixture")
    if source_case.get("proofpath", {}).get("canonicalCapabilityCommit") != PROOFPATH_CAPABILITY_COMMIT:
        raise System007Error("source fixture is not pinned to the canonical ProofPath capability")

    adapter = load_json(Path(args.adapter))
    observations = load_json(Path(args.observations))
    observations = copy.deepcopy(observations)
    observations["logicalOperationId"] = identity["logical_operation_id"]
    observations["executionId"] = "exec-system-007-001"
    authority = {
        "status": "authorized",
        "evidenceRef": intent["authority"]["evidence_ref"],
    }

    from contractgraph_qa.provider_decision_evidence import build_provider_decision_evidence
    from contractgraph_qa.provider_payment_decision import evaluate_provider_payment_decision
    from contractgraph_qa.proofpath_scig_adapter import (
        build_proofpath_scig_from_provider_evidence,
    )

    decision = evaluate_provider_payment_decision(
        adapter,
        observations,
        authority,
        decision_id=f"system-007-decision:{identity['logical_operation_id']}",
    )
    if decision["decision"]["decision"] != "STOP":
        raise System007Error("SYSTEM-007 source decision must be STOP")
    pack = build_provider_decision_evidence(adapter, observations, authority, decision)
    scig = build_proofpath_scig_from_provider_evidence(
        pack,
        observed_at=identity["observed_at"],
    )
    scig_projection_digest = sha256_ref(scig)
    records, cml_summary = build_cml_chain(
        Path(args.cml_root),
        logical_operation_id=identity["logical_operation_id"],
        intent_digest=sha256_ref(intent),
        scig_projection_digest=scig_projection_digest,
    )
    scig["system_chain"] = {
        "schema": "cgqa.system-007-chain-extension.v0.1",
        "case_id": CASE_ID,
        "logical_operation_id": identity["logical_operation_id"],
        "intent_nonce": identity["nonce"],
        "intent_argument_digest": identity["argument_digest"],
        "intent_digest": sha256_ref(intent),
        "cml_terminal_record_id": cml_summary["terminal_record_id"],
        "cml_chain_sha256": cml_summary["chain_sha256"],
        "component_heads": heads,
        "authority_boundary": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
        },
    }

    write_json(output / "intent.json", intent)
    write_json(output / "provider-evidence-pack.json", pack)
    write_json(output / "scig.json", scig)
    write_cml_records(output / "cml-records.jsonl", records)
    write_json(output / "cml-chain-summary.json", cml_summary)
    write_json(
        output / "prepare-result.json",
        {
            "schema": "cgqa.system-007-prepare-result.v0.1",
            "case_id": CASE_ID,
            "logical_operation_id": identity["logical_operation_id"],
            "component_heads": heads,
            "intent_digest": sha256_ref(intent),
            "scig_digest": sha256_ref(scig),
            "cml_chain_sha256": cml_summary["chain_sha256"],
            "authority_transfer": "NONE",
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_performed": False,
        },
    )
    print("FCRP_SYSTEM_007_PREPARE_PASS", sha256_ref(scig))


def finalize(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    heads = assert_exact_heads(args)
    scig = load_json(output / "scig.json")
    stdout = Path(args.native_stdout).read_text(encoding="utf-8")
    from contractgraph_qa.liminaldb_proofpath_adapter import (
        build_liminaldb_proofpath_audit_event,
    )
    from contractgraph_qa.proofpath_scig_adapter import finalize_native_proofpath_receipt

    receipt = finalize_native_proofpath_receipt(
        scig,
        stdout,
        proofpath_capability_commit=PROOFPATH_CAPABILITY_COMMIT,
    )
    event = build_liminaldb_proofpath_audit_event(
        scig,
        receipt,
        observed_at=load_json(output / "intent.json")["observed_at"],
    )
    if event["correlationId"] != LOGICAL_OPERATION_ID:
        raise System007Error("LiminalDB event changed logical operation identity")
    write_json(output / "native-proofpath-receipt.json", receipt)
    (output / "liminaldb-proofpath-event.jsonl").write_text(
        json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    write_json(
        output / "storage-scope.json",
        {
            "schema": "cgqa.system-007-storage-scope.v0.1",
            "scope": "local_test_only",
            "source_revision": heads["contractgraph_qa"],
            "durable_consumer_revision": heads["liminaldb"],
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
        },
    )
    print("FCRP_SYSTEM_007_PROOFPATH_PASS", receipt["receiptDigest"])


def reflect(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    heads = assert_exact_heads(args)
    rinse_root = str(Path(args.rinse_root).resolve())
    if rinse_root not in sys.path:
        sys.path.insert(0, rinse_root)
    from rinse.adapters.liminaldb_durable_proof import derive_durable_proof_reflection

    summary = load_json(Path(args.summary))
    event_path = Path(args.event)
    admission_path = Path(args.admission)
    loop = derive_durable_proof_reflection(
        summary,
        event_path.read_bytes(),
        admission_path.read_bytes(),
        reviewed_time=load_json(output / "intent.json")["reviewed_at"],
        liminaldb_durable_commit=LIMINALDB_DURABLE_COMMIT,
    )
    assert_reflection_boundary(loop)
    source_trace = loop["source_trace"]
    if source_trace["context"]["logical_operation_id"] != LOGICAL_OPERATION_ID:
        raise System007Error("RINSE changed logical operation identity")
    write_json(output / "rinse-reflection-loop.json", loop)
    write_json(
        output / "reflection-result.json",
        {
            "schema": "cgqa.system-007-reflection-result.v0.1",
            "logical_operation_id": LOGICAL_OPERATION_ID,
            "source_record_hash": source_trace["context"]["record_hash"],
            "rinse_head": heads["rinse"],
            "verdict": loop["graph"]["verdict"],
            "authority_classification": loop["graph"]["authority"]["classification"],
            "source_mutated": loop["source_mutated"],
            "write_back_performed": loop["write_back_performed"],
        },
    )
    print("FCRP_SYSTEM_007_RINSE_PASS", loop["reflection"]["id"])


def verify(args: argparse.Namespace) -> None:
    output = Path(args.output_dir)
    heads = assert_exact_heads(args)
    expected_heads = {
        "contractgraph_qa": args.subject_head,
        "proofpath": args.proofpath_head,
        "cml": args.cml_head,
        "liminaldb": args.liminaldb_head,
        "rinse": args.rinse_head,
    }
    compare_declared_heads(heads, expected_heads)

    intent = load_json(output / "intent.json")
    identity = validate_intent(intent)
    if identity["logical_operation_id"] != LOGICAL_OPERATION_ID:
        raise System007Error("final identity did not preserve logical operation")
    provider_pack = load_json(output / "provider-evidence-pack.json")
    scig = load_json(output / "scig.json")
    native_stdout = Path(args.native_stdout).read_text(encoding="utf-8")
    native_receipt = load_json(output / "native-proofpath-receipt.json")
    cml_summary = load_json(output / "cml-chain-summary.json")
    durable_summary = load_json(Path(args.summary))
    event_bytes = Path(args.event).read_bytes()
    admission_bytes = Path(args.admission).read_bytes()
    reflection = load_json(output / "rinse-reflection-loop.json")

    from contractgraph_qa.fcrp_v02 import evaluate_fcrp_v02_case
    from contractgraph_qa.liminaldb_proofpath_adapter import (
        build_liminaldb_proofpath_audit_event,
    )
    from contractgraph_qa.proofpath_scig_adapter import (
        finalize_native_proofpath_receipt,
    )
    from contractgraph_qa.provider_decision_evidence import (
        verify_provider_decision_evidence,
    )

    provider_decision = verify_provider_decision_evidence(provider_pack)
    if provider_decision["logicalOperationId"] != LOGICAL_OPERATION_ID:
        raise System007Error("provider decision changed logical operation identity")
    if provider_decision["decision"]["decision"] != "STOP":
        raise System007Error("provider decision no longer stops the operation")

    if scig.get("logical_operation_id") != LOGICAL_OPERATION_ID:
        raise System007Error("SCIG changed logical operation identity")
    system_chain = scig.get("system_chain")
    if not isinstance(system_chain, Mapping):
        raise System007Error("SCIG is missing the SYSTEM-007 chain extension")
    if system_chain.get("intent_digest") != sha256_ref(intent):
        raise System007Error("SCIG intent digest is not bound to the exact intent")
    if system_chain.get("component_heads") != heads:
        raise System007Error("SCIG component head map is stale")

    recomputed_receipt = finalize_native_proofpath_receipt(
        scig,
        native_stdout,
        proofpath_capability_commit=PROOFPATH_CAPABILITY_COMMIT,
    )
    if recomputed_receipt != native_receipt:
        raise System007Error("native ProofPath receipt is not reproducible from raw stdout")

    expected_event = build_liminaldb_proofpath_audit_event(
        scig,
        native_receipt,
        observed_at=identity["observed_at"],
    )
    try:
        decoded_event = json.loads(event_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise System007Error(f"durable event is not JSON: {exc}") from exc
    if decoded_event != expected_event:
        raise System007Error("durable event is not the exact expected ProofPath event")

    expected_ids = ["system-007-intent", "system-007-proofpath-decision", "system-007-cml-causal-record"]
    cml_replayed = read_cml_chain(
        output / "cml-records.jsonl",
        Path(args.cml_root),
        logical_operation_id=LOGICAL_OPERATION_ID,
        expected_ids=expected_ids,
    )
    for key in ("chain_ids", "chain_sha256", "record_count", "terminal_record_id"):
        if cml_replayed[key] != cml_summary[key]:
            raise System007Error(f"CML summary field {key} is not reproducible")
    if system_chain.get("cml_chain_sha256") != cml_summary["chain_sha256"]:
        raise System007Error("SCIG CML chain digest is stale")

    rinse_root = str(Path(args.rinse_root).resolve())
    if rinse_root not in sys.path:
        sys.path.insert(0, rinse_root)
    from rinse.adapters.liminaldb_durable_proof import (
        build_durable_source_trace,
        derive_durable_proof_reflection,
        validate_durable_bundle,
    )

    validated = validate_durable_bundle(
        durable_summary,
        event_bytes,
        admission_bytes,
        liminaldb_durable_commit=LIMINALDB_DURABLE_COMMIT,
    )
    if validated["logical_operation_id"] != LOGICAL_OPERATION_ID:
        raise System007Error("LiminalDB durable summary changed logical operation identity")
    recomputed_reflection = derive_durable_proof_reflection(
        durable_summary,
        event_bytes,
        admission_bytes,
        reviewed_time=identity["reviewed_at"],
        liminaldb_durable_commit=LIMINALDB_DURABLE_COMMIT,
    )
    assert_reflection_boundary(reflection)
    if recomputed_reflection != reflection:
        raise System007Error("RINSE reflection is not reproducible from durable raw bytes")
    source_trace = build_durable_source_trace(
        durable_summary,
        event_bytes,
        admission_bytes,
        liminaldb_durable_commit=LIMINALDB_DURABLE_COMMIT,
    )
    if source_trace["id"] != reflection["source_trace"]["id"]:
        raise System007Error("RINSE source-trace identity changed")

    case = load_json(Path(args.case))
    fcrp_result = evaluate_fcrp_v02_case(case)
    if fcrp_result["caseId"] != CASE_ID or fcrp_result["decision"] != "PASS":
        raise System007Error("FCRP-SYSTEM-007 case did not evaluate to PASS")
    if fcrp_result["mutationAuthorized"] is not False:
        raise System007Error("FCRP case escalated mutation authority")

    negative_cases: dict[str, str] = {}
    expect_rejection(negative_cases, "missing_intent", lambda: validate_intent({}))
    expect_rejection(
        negative_cases,
        "replayed_nonce",
        lambda: validate_intent(intent, used_nonces={identity["nonce"]}),
    )
    changed_intent = copy.deepcopy(intent)
    changed_intent["arguments"]["expected_decision"] = "ALLOW"
    expect_rejection(
        negative_cases,
        "changed_argument_digest",
        lambda: validate_intent(changed_intent),
    )
    stale_expected = dict(expected_heads)
    stale_expected["rinse"] = "0" * 40
    expect_rejection(
        negative_cases,
        "stale_dependency_head",
        lambda: compare_declared_heads(heads, stale_expected),
    )
    expect_rejection(
        negative_cases,
        "tampered_durable_record",
        lambda: validate_durable_bundle(
            durable_summary,
            event_bytes + b" ",
            admission_bytes,
            liminaldb_durable_commit=LIMINALDB_DURABLE_COMMIT,
        ),
    )
    escalated = copy.deepcopy(reflection)
    escalated_graph = escalated.setdefault("graph", {})
    escalated_handoffs = escalated_graph.setdefault("candidate_handoffs", [{}])
    escalated_handoffs[0]["execution_allowed"] = True
    expect_rejection(
        negative_cases,
        "reflection_execution_escalation",
        lambda: assert_reflection_boundary(escalated),
    )
    if set(negative_cases) != {
        "missing_intent",
        "replayed_nonce",
        "changed_argument_digest",
        "stale_dependency_head",
        "tampered_durable_record",
        "reflection_execution_escalation",
    }:
        raise System007Error("SYSTEM-007 negative-case coverage is incomplete")

    result = {
        "schema": "cgqa.system-007-result.v0.1",
        "case_id": CASE_ID,
        "decision": "PASS",
        "logical_operation_id": LOGICAL_OPERATION_ID,
        "chain": EXPECTED_CHAIN,
        "component_heads": heads,
        "identity_preserved": True,
        "cml_chain_replayed": True,
        "proofpath_native_result": "VALID",
        "liminaldb_reopen_byte_match": True,
        "liminaldb_retry_status": "ALREADY_PRESENT",
        "rinse_verdict": reflection["graph"]["verdict"],
        "rinse_authority": reflection["graph"]["authority"]["classification"],
        "source_mutated": reflection["source_mutated"],
        "write_back_performed": reflection["write_back_performed"],
        "negative_cases": negative_cases,
        "authority": {
            "execution_authorized": False,
            "mutation_authorized": False,
            "external_effects_authorized": False,
        },
        "evidence_digests": {
            "intent": sha256_ref(intent),
            "provider_evidence_pack": sha256_ref(provider_pack),
            "scig": sha256_ref(scig),
            "cml_chain": cml_summary["chain_sha256"],
            "durable_record": durable_summary["record_hash"],
            "rinse_reflection": sha256_ref(reflection),
        },
        "fcrp_result": fcrp_result,
    }
    write_json(output / "fcrp-system-007-result.json", result)
    print("FCRP_SYSTEM_007_PASS", sha256_ref(result))


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cgqa-root", default=".")
    parser.add_argument("--subject-head", required=True)
    parser.add_argument("--proofpath-root", required=True)
    parser.add_argument("--proofpath-head", required=True)
    parser.add_argument("--cml-root", required=True)
    parser.add_argument("--cml-head", required=True)
    parser.add_argument("--liminaldb-root", required=True)
    parser.add_argument("--liminaldb-head", required=True)
    parser.add_argument("--rinse-root", required=True)
    parser.add_argument("--rinse-head", required=True)
    parser.add_argument("--output-dir", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    add_common(prepare_parser)
    prepare_parser.add_argument("--intent", required=True)
    prepare_parser.add_argument("--source-case", required=True)
    prepare_parser.add_argument("--adapter", required=True)
    prepare_parser.add_argument("--observations", required=True)
    prepare_parser.set_defaults(handler=prepare)

    finalize_parser = subparsers.add_parser("finalize")
    add_common(finalize_parser)
    finalize_parser.add_argument("--native-stdout", required=True)
    finalize_parser.set_defaults(handler=finalize)

    reflect_parser = subparsers.add_parser("reflect")
    add_common(reflect_parser)
    reflect_parser.add_argument("--summary", required=True)
    reflect_parser.add_argument("--event", required=True)
    reflect_parser.add_argument("--admission", required=True)
    reflect_parser.set_defaults(handler=reflect)

    verify_parser = subparsers.add_parser("verify")
    add_common(verify_parser)
    verify_parser.add_argument("--case", required=True)
    verify_parser.add_argument("--native-stdout", required=True)
    verify_parser.add_argument("--summary", required=True)
    verify_parser.add_argument("--event", required=True)
    verify_parser.add_argument("--admission", required=True)
    verify_parser.set_defaults(handler=verify)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (OSError, System007Error, subprocess.CalledProcessError) as exc:
        print(f"FCRP_SYSTEM_007_INCOMPLETE {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
