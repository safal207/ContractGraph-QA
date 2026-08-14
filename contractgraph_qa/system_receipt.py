"""Synthetic end-to-end receipt for the NEO REZONANS system contract.

The receipt proves one logical operation can traverse the canonical system
snapshot without losing logical identity, causal/evidence lineage, or leaking
execution authority across a non-authority boundary.

It is deliberately synthetic and non-executing. A PASS is a composition proof,
not permission to mutate repositories, call providers, move funds, or perform
any external effect.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from contractgraph_qa.system_snapshot import validate_system_snapshot

SYSTEM_RECEIPT_TRACE_SCHEMA = "cgqa.neo-rezonans-system-trace.v0.1"
SYSTEM_RECEIPT_RESULT_SCHEMA = "cgqa.neo-rezonans-system-receipt.v0.1"


class SystemReceiptError(ValueError):
    """Raised when an end-to-end synthetic trace violates the system contract."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemReceiptError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise SystemReceiptError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemReceiptError(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise SystemReceiptError(f"{field} must be a boolean")
    return value


def _text_list(value: object, field: str, *, non_empty: bool = False) -> list[str]:
    raw = _list(value, field)
    values = [_text(item, f"{field}[{index}]") for index, item in enumerate(raw)]
    if non_empty and not values:
        raise SystemReceiptError(f"{field} must not be empty")
    if len(values) != len(set(values)):
        raise SystemReceiptError(f"{field} must not contain duplicates")
    return values


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def build_system_receipt(trace: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate one synthetic traversal and emit a deterministic system receipt."""

    snapshot_result = validate_system_snapshot(snapshot)
    trace = _object(trace, "trace")
    if trace.get("schema") != SYSTEM_RECEIPT_TRACE_SCHEMA:
        raise SystemReceiptError(f"trace.schema must be {SYSTEM_RECEIPT_TRACE_SCHEMA}")

    trace_id = _text(trace.get("traceId"), "trace.traceId")
    logical_operation_id = _text(
        trace.get("logicalOperationId"),
        "trace.logicalOperationId",
    )
    if _text(trace.get("snapshotId"), "trace.snapshotId") != snapshot_result["snapshotId"]:
        raise SystemReceiptError("trace.snapshotId must match the validated system snapshot")

    boundary = _object(trace.get("authorityBoundary"), "trace.authorityBoundary")
    if not _bool(boundary.get("syntheticOnly"), "trace.authorityBoundary.syntheticOnly"):
        raise SystemReceiptError("end-to-end v0.1 receipts must be synthetic-only")
    if _bool(
        boundary.get("externalEffectsAllowed"),
        "trace.authorityBoundary.externalEffectsAllowed",
    ):
        raise SystemReceiptError("synthetic system receipt may not allow external effects")
    if _bool(
        boundary.get("evidenceMayGrantAuthority"),
        "trace.authorityBoundary.evidenceMayGrantAuthority",
    ):
        raise SystemReceiptError("evidence may not grant authority in the end-to-end trace")
    if _bool(
        boundary.get("receiptGrantsMutationAuthority"),
        "trace.authorityBoundary.receiptGrantsMutationAuthority",
    ):
        raise SystemReceiptError("the system receipt may not itself grant mutation authority")

    chain = list(snapshot["primaryChain"])
    layers = {item["id"]: item for item in snapshot["layers"]}
    edges = {(item["from"], item["to"]): item for item in snapshot["edges"]}

    stages_raw = _list(trace.get("stages"), "trace.stages")
    if len(stages_raw) != len(chain):
        raise SystemReceiptError("trace.stages must contain exactly one stage for every system layer")

    stage_ids: set[str] = set()
    stage_digests: list[dict[str, str]] = []
    previous_stage_id: str | None = None
    previous_output_evidence_ref: str | None = None
    identity_preserved = True
    causal_lineage_preserved = True
    evidence_lineage_preserved = True
    source_mutation_observed = False
    external_effect_observed = False

    for index, raw in enumerate(stages_raw):
        stage = _object(raw, f"trace.stages[{index}]")
        expected_layer = chain[index]
        layer_id = _text(stage.get("layerId"), f"trace.stages[{index}].layerId")
        if layer_id != expected_layer:
            raise SystemReceiptError(
                f"trace stage {index} must target layer {expected_layer}, got {layer_id}"
            )
        if layer_id not in layers:
            raise SystemReceiptError(f"trace stage {index} references unknown layer {layer_id}")

        stage_id = _text(stage.get("stageId"), f"trace.stages[{index}].stageId")
        if stage_id in stage_ids:
            raise SystemReceiptError(f"duplicate stageId {stage_id}")
        stage_ids.add(stage_id)

        stage_operation_id = _text(
            stage.get("logicalOperationId"),
            f"trace.stages[{index}].logicalOperationId",
        )
        if stage_operation_id != logical_operation_id:
            identity_preserved = False
            raise SystemReceiptError(
                f"stage {stage_id} changed logicalOperationId from {logical_operation_id}"
            )

        parent_stage_id = stage.get("parentStageId")
        if index == 0:
            if parent_stage_id is not None:
                causal_lineage_preserved = False
                raise SystemReceiptError("the first stage must have parentStageId=null")
        else:
            if parent_stage_id != previous_stage_id:
                causal_lineage_preserved = False
                raise SystemReceiptError(
                    f"stage {stage_id} must name previous stage {previous_stage_id} as parent"
                )

        input_evidence_refs = _text_list(
            stage.get("inputEvidenceRefs", []),
            f"trace.stages[{index}].inputEvidenceRefs",
        )
        output_evidence_ref = _text(
            stage.get("outputEvidenceRef"),
            f"trace.stages[{index}].outputEvidenceRef",
        )
        if index == 0:
            if input_evidence_refs:
                raise SystemReceiptError("the first stage must not claim inherited evidence")
        elif previous_output_evidence_ref not in input_evidence_refs:
            evidence_lineage_preserved = False
            raise SystemReceiptError(
                f"stage {stage_id} must inherit prior evidence {previous_output_evidence_ref}"
            )

        _text(stage.get("eventType"), f"trace.stages[{index}].eventType")
        _text_list(
            stage.get("factsProduced"),
            f"trace.stages[{index}].factsProduced",
            non_empty=True,
        )
        if _bool(stage.get("sourceMutation"), f"trace.stages[{index}].sourceMutation"):
            source_mutation_observed = True
            raise SystemReceiptError(f"stage {stage_id} may not mutate source history")
        if _bool(stage.get("externalEffect"), f"trace.stages[{index}].externalEffect"):
            external_effect_observed = True
            raise SystemReceiptError(f"stage {stage_id} may not perform an external effect")

        digest_payload = {
            "stage": stage,
            "snapshotId": snapshot_result["snapshotId"],
            "snapshotDigest": snapshot_result["snapshotDigest"],
        }
        stage_digests.append({"stageId": stage_id, "digest": _sha256(digest_payload)})
        previous_stage_id = stage_id
        previous_output_evidence_ref = output_evidence_ref

    transfers_raw = _list(trace.get("transfers"), "trace.transfers")
    if len(transfers_raw) != len(chain):
        raise SystemReceiptError(
            "trace.transfers must contain every primary transfer plus the feedback transfer"
        )

    expected_pairs = list(zip(chain, chain[1:])) + [(chain[-1], chain[0])]
    authority_transfer_count = 0
    authority_leak_count = 0
    feedback_count = 0
    transfer_digests: list[dict[str, str]] = []

    for index, raw in enumerate(transfers_raw):
        transfer = _object(raw, f"trace.transfers[{index}]")
        expected_source, expected_target = expected_pairs[index]
        source = _text(transfer.get("from"), f"trace.transfers[{index}].from")
        target = _text(transfer.get("to"), f"trace.transfers[{index}].to")
        if (source, target) != (expected_source, expected_target):
            raise SystemReceiptError(
                f"transfer {index} must be {expected_source}->{expected_target}, got {source}->{target}"
            )
        edge = edges.get((source, target))
        if edge is None:
            raise SystemReceiptError(f"system snapshot does not authorize transfer edge {source}->{target}")

        transfer_operation_id = _text(
            transfer.get("logicalOperationId"),
            f"trace.transfers[{index}].logicalOperationId",
        )
        if transfer_operation_id != logical_operation_id:
            raise SystemReceiptError(
                f"transfer {source}->{target} changed logicalOperationId"
            )

        facts = _text_list(
            transfer.get("facts"),
            f"trace.transfers[{index}].facts",
            non_empty=True,
        )
        unknown_facts = sorted(set(facts) - set(edge["allowedFacts"]))
        if unknown_facts:
            raise SystemReceiptError(
                f"transfer {source}->{target} carries facts not allowed by snapshot: {unknown_facts}"
            )
        forbidden_carried = sorted(set(facts) & set(edge["forbiddenInferences"]))
        if forbidden_carried:
            raise SystemReceiptError(
                f"transfer {source}->{target} carries forbidden inference(s): {forbidden_carried}"
            )

        authority_transferred = _bool(
            transfer.get("authorityTransferred"),
            f"trace.transfers[{index}].authorityTransferred",
        )
        authorization_ref = transfer.get("authorizationRef")
        if edge["authorityMode"] == "NONE":
            if authority_transferred or authorization_ref not in (None, ""):
                authority_leak_count += 1
                raise SystemReceiptError(
                    f"authority leaked across non-authority edge {source}->{target}"
                )
        elif edge["authorityMode"] == "EXPLICIT_CONTRACT_ONLY":
            if not authority_transferred:
                raise SystemReceiptError(
                    f"explicit authority edge {source}->{target} must declare authorityTransferred=true"
                )
            _text(authorization_ref, f"trace.transfers[{index}].authorizationRef")
            if "authorization_ref" not in facts:
                raise SystemReceiptError(
                    f"explicit authority edge {source}->{target} must carry authorization_ref"
                )
            authority_transfer_count += 1
        else:  # defensive: snapshot validator should already reject this
            raise SystemReceiptError(f"unsupported authority mode on edge {source}->{target}")

        feedback = _bool(transfer.get("feedback"), f"trace.transfers[{index}].feedback")
        if feedback != bool(edge["feedback"]):
            raise SystemReceiptError(
                f"transfer {source}->{target} feedback flag must match system snapshot"
            )
        if feedback:
            feedback_count += 1

        transfer_digests.append(
            {
                "edge": f"{source}->{target}",
                "digest": _sha256(
                    {
                        "transfer": transfer,
                        "snapshotId": snapshot_result["snapshotId"],
                        "snapshotDigest": snapshot_result["snapshotDigest"],
                    }
                ),
            }
        )

    if authority_transfer_count != 1:
        raise SystemReceiptError("end-to-end trace must contain exactly one explicit authority transfer")
    if feedback_count != 1:
        raise SystemReceiptError("end-to-end trace must contain exactly one reflection feedback transfer")

    final = _object(trace.get("final"), "trace.final")
    if _text(final.get("logicalOperationId"), "trace.final.logicalOperationId") != logical_operation_id:
        raise SystemReceiptError("final result changed logicalOperationId")
    if _text(final.get("status"), "trace.final.status") != "REFLECTED_WITH_EVIDENCE":
        raise SystemReceiptError("trace.final.status must be REFLECTED_WITH_EVIDENCE")
    if _text(final.get("evidenceRef"), "trace.final.evidenceRef") != previous_output_evidence_ref:
        raise SystemReceiptError("final evidenceRef must equal the last stage outputEvidenceRef")
    if _bool(final.get("executionAuthorized"), "trace.final.executionAuthorized"):
        raise SystemReceiptError("reflection feedback may not end with executionAuthorized=true")
    if _bool(final.get("sourceMutated"), "trace.final.sourceMutated"):
        raise SystemReceiptError("reflection feedback may not mutate source history")

    result_without_digest = {
        "schema": SYSTEM_RECEIPT_RESULT_SCHEMA,
        "traceId": trace_id,
        "logicalOperationId": logical_operation_id,
        "snapshotId": snapshot_result["snapshotId"],
        "snapshotDigest": snapshot_result["snapshotDigest"],
        "decision": "PASS",
        "stageCount": len(stages_raw),
        "transferCount": len(transfers_raw),
        "identityPreserved": identity_preserved,
        "causalLineagePreserved": causal_lineage_preserved,
        "evidenceLineagePreserved": evidence_lineage_preserved,
        "authorityTransferCount": authority_transfer_count,
        "authorityLeakCount": authority_leak_count,
        "feedbackCount": feedback_count,
        "sourceMutationObserved": source_mutation_observed,
        "externalEffectObserved": external_effect_observed,
        "finalStatus": final["status"],
        "stageDigests": stage_digests,
        "transferDigests": transfer_digests,
        "traceDigest": _sha256(trace),
    }
    return {
        **result_without_digest,
        "receiptDigest": _sha256(result_without_digest),
    }
