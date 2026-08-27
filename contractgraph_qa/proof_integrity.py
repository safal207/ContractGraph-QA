"""Verification-of-verification primitives for the causal-temporal core."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from contractgraph_qa.causal_temporal_utils import (
    CausalTemporalError,
    canonical_sha256,
    require_bool,
    require_int,
    require_list,
    require_object,
    require_subject,
    require_text,
)


class ProofIntegrityError(CausalTemporalError):
    """Raised when proof-integrity inputs are malformed."""


def _strings(value: object, name: str) -> list[str]:
    rows = require_list(value, name)
    out: list[str] = []
    for index, raw in enumerate(rows):
        out.append(require_text(raw, f"{name}[{index}]"))
    if len(out) != len(set(out)):
        raise ProofIntegrityError(f"{name} must not contain duplicates")
    return out


def evaluate_subject_freeze(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/subject-freeze/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/subject-freeze/v0.1'")
    before = require_object(model.get("subjectBefore"), "subjectBefore")
    after = require_object(model.get("subjectAfter"), "subjectAfter")
    if not before or not after:
        raise ProofIntegrityError("subjectBefore and subjectAfter must not be empty")
    before_hash = canonical_sha256(before)
    after_hash = canonical_sha256(after)
    unchanged = before_hash == after_hash
    return {
        "schema": "cgqa/subject-freeze-result/v0.1",
        "status": "pass" if unchanged else "fail",
        "classification": "UNCHANGED" if unchanged else "STALE_SUBJECT",
        "subjectBeforeHash": before_hash,
        "subjectAfterHash": after_hash,
        "inputHash": canonical_sha256(model),
        "claimBoundary": "Stable subject identity is required before evidence can be attributed to the same target.",
    }


def _validate_plan_core(value: object, name: str) -> dict[str, Any]:
    plan = require_object(value, name)
    require_text(plan.get("subjectHash"), f"{name}.subjectHash")
    for field in ("invariants", "forbiddenStates", "capabilities", "negativeControls"):
        _strings(plan.get(field, []), f"{name}.{field}")
    bounds = require_object(plan.get("bounds", {}), f"{name}.bounds")
    for key, raw in bounds.items():
        if not isinstance(raw, (str, int, float, bool)) or raw is None:
            raise ProofIntegrityError(f"{name}.bounds.{key} must be scalar")
    return plan


def evaluate_verification_plan(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/verification-plan/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/verification-plan/v0.1'")
    base_plan = _validate_plan_core(model.get("plan"), "plan")
    current_plan = dict(base_plan)
    base_hash = canonical_sha256(base_plan)
    current_hash = base_hash
    amendment_receipts: list[dict[str, object]] = []
    for index, raw in enumerate(require_list(model.get("amendments", []), "amendments")):
        amendment = require_object(raw, f"amendments[{index}]")
        if require_text(amendment.get("fromPlanHash"), f"amendments[{index}].fromPlanHash") != current_hash:
            raise ProofIntegrityError(f"amendments[{index}] does not chain from the current plan")
        reason = require_text(amendment.get("reason"), f"amendments[{index}].reason")
        next_plan = _validate_plan_core(amendment.get("toPlan"), f"amendments[{index}].toPlan")
        if next_plan["subjectHash"] != base_plan["subjectHash"]:
            raise ProofIntegrityError("plan amendment cannot silently change exact subject")
        next_hash = canonical_sha256(next_plan)
        amendment_receipts.append(
            {"index": index, "fromPlanHash": current_hash, "toPlanHash": next_hash, "reason": reason}
        )
        current_plan = dict(next_plan)
        current_hash = next_hash

    result = require_object(model.get("result"), "result")
    result_plan_hash = require_text(result.get("planHash"), "result.planHash")
    result_subject_hash = require_text(result.get("subjectHash"), "result.subjectHash")
    executed = _strings(result.get("executedCapabilities", []), "result.executedCapabilities")
    observed_bounds = require_object(result.get("bounds", {}), "result.bounds")
    reasons: list[str] = []
    if result_plan_hash != current_hash:
        reasons.append("RESULT_PLAN_HASH_MISMATCH")
    if result_subject_hash != current_plan["subjectHash"]:
        reasons.append("RESULT_SUBJECT_MISMATCH")
    undeclared = sorted(set(executed) - set(current_plan.get("capabilities", [])))
    if undeclared:
        reasons.append("UNDECLARED_CAPABILITY_EXECUTED")
    if observed_bounds != current_plan.get("bounds", {}):
        reasons.append("POST_HOC_BOUND_DRIFT")

    return {
        "schema": "cgqa/verification-plan-result/v0.1",
        "status": "pass" if not reasons else "fail",
        "basePlanHash": base_hash,
        "finalPlanHash": current_hash,
        "amendments": amendment_receipts,
        "undeclaredCapabilities": undeclared,
        "reasons": reasons,
        "claimBoundary": "CommitBeforeObserve makes post-hoc plan changes visible; preregistration does not prove the plan is good.",
    }


def evaluate_trace_integrity(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/trace-integrity/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/trace-integrity/v0.1'")
    _, subject_hash = require_subject(model)
    complete_expected = model.get("completeExpected", True)
    require_bool(complete_expected, "completeExpected")
    events = require_list(model.get("events"), "events")
    if not events:
        raise ProofIntegrityError("events must not be empty")

    reasons: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    expected_sequence: int | None = None
    previous_id: str | None = None
    for index, raw in enumerate(events):
        event = require_object(raw, f"events[{index}]")
        event_id = require_text(event.get("eventId"), f"events[{index}].eventId")
        sequence = require_int(event.get("sequence"), f"events[{index}].sequence")
        if sequence < 0:
            raise ProofIntegrityError("event sequence must be >= 0")
        if event.get("subjectHash") != subject_hash:
            reasons.append({"code": "FOREIGN_SUBJECT_EVENT", "refs": [event_id]})
        if event_id in seen_ids:
            reasons.append({"code": "DUPLICATE_EVENT_ID", "refs": [event_id]})
        if sequence in seen_sequences:
            reasons.append({"code": "DUPLICATE_SEQUENCE", "refs": [event_id, str(sequence)]})
        seen_ids.add(event_id)
        seen_sequences.add(sequence)

        if expected_sequence is None:
            expected_sequence = sequence
        if sequence != expected_sequence:
            code = "OUT_OF_ORDER" if sequence < expected_sequence else "UNMARKED_TRACE_GAP"
            reasons.append({"code": code, "refs": [event_id, str(expected_sequence), str(sequence)]})

        predecessor = event.get("predecessorId")
        if previous_id is not None and predecessor != previous_id:
            reasons.append({"code": "PREDECESSOR_MISMATCH", "refs": [event_id, previous_id]})

        kind = str(event.get("kind", "EVENT")).upper()
        if kind == "GAP":
            gap_from = require_int(event.get("gapFrom"), f"events[{index}].gapFrom")
            gap_to = require_int(event.get("gapTo"), f"events[{index}].gapTo")
            if gap_from != sequence or gap_to < gap_from:
                reasons.append({"code": "INVALID_GAP_MARKER", "refs": [event_id]})
                expected_sequence = sequence + 1
            else:
                expected_sequence = gap_to + 1
        else:
            expected_sequence = sequence + 1
        previous_id = event_id

    if not complete_expected and not any(str(event.get("kind", "")).upper() == "GAP" for event in events):
        reasons.append({"code": "PARTIAL_TRACE_WITHOUT_GAP_MARKER", "refs": []})
    reasons.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
    return {
        "schema": "cgqa/trace-integrity-result/v0.1",
        "status": "pass" if not reasons else "fail",
        "subjectHash": subject_hash,
        "traceHash": canonical_sha256(model),
        "reasons": reasons,
        "claimBoundary": "missing != absent; unknown != false; a partial trace is not a complete trace.",
    }


EVIDENCE_CLASSES = {
    "WITNESSED",
    "REPORTED",
    "REFLECTED",
    "DERIVED",
    "MODEL_OUTPUT",
    "NON_DETECTION",
    "COUNTEREVIDENCE",
}


def evaluate_evidence_readiness(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/evidence-readiness/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/evidence-readiness/v0.1'")
    _, subject_hash = require_subject(model)
    evidence = require_list(model.get("evidence"), "evidence")
    requirements = require_object(model.get("requirements", {}), "requirements")
    expected_counter = set(_strings(requirements.get("expectedCounterevidenceIds", []), "requirements.expectedCounterevidenceIds"))
    require_fresh = requirements.get("requireFresh", True)
    require_replay = requirements.get("requireReplayable", True)
    require_bool(require_fresh, "requirements.requireFresh")
    require_bool(require_replay, "requirements.requireReplayable")

    hard: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    classes: dict[str, int] = {}
    present_counter: set[str] = set()
    for index, raw in enumerate(evidence):
        item = require_object(raw, f"evidence[{index}]")
        item_id = require_text(item.get("id"), f"evidence[{index}].id")
        evidence_class = require_text(item.get("class"), f"evidence[{index}].class")
        if evidence_class not in EVIDENCE_CLASSES:
            raise ProofIntegrityError(f"unsupported evidence class: {evidence_class}")
        if item.get("subjectHash") != subject_hash:
            hard.append({"code": "EVIDENCE_SUBJECT_MISMATCH", "refs": [item_id]})
        source_type = require_text(item.get("sourceType"), f"evidence[{index}].sourceType")
        replayable = item.get("replayable", False)
        fresh = item.get("fresh", False)
        independent = item.get("independent", False)
        require_bool(replayable, f"evidence[{index}].replayable")
        require_bool(fresh, f"evidence[{index}].fresh")
        require_bool(independent, f"evidence[{index}].independent")
        if evidence_class == "WITNESSED" and source_type != "DIRECT_OBSERVATION":
            hard.append({"code": "FALSE_WITNESS_CLASS", "refs": [item_id]})
        if require_replay and not replayable and evidence_class not in {"REPORTED", "REFLECTED"}:
            unresolved.append({"code": "EVIDENCE_NOT_REPLAYABLE", "refs": [item_id]})
        if require_fresh and not fresh:
            unresolved.append({"code": "EVIDENCE_STALE", "refs": [item_id]})
        if evidence_class == "WITNESSED" and not independent:
            unresolved.append({"code": "WITNESS_NOT_INDEPENDENT", "refs": [item_id]})
        if evidence_class == "COUNTEREVIDENCE":
            present_counter.add(item_id)
        classes[evidence_class] = classes.get(evidence_class, 0) + 1

    missing_counter = sorted(expected_counter - present_counter)
    if missing_counter:
        hard.append({"code": "COUNTEREVIDENCE_OMITTED", "refs": missing_counter})
    hard.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
    unresolved.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
    readiness = "UNSTABLE" if hard else "PARTIAL" if unresolved else "READY"
    return {
        "schema": "cgqa/evidence-readiness-result/v0.1",
        "status": "pass" if readiness == "READY" else "hold" if readiness == "PARTIAL" else "fail",
        "readiness": readiness,
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(model),
        "classCounts": {key: classes[key] for key in sorted(classes)},
        "hardFindings": hard,
        "unresolved": unresolved,
        "truthProbability": None,
        "claimBoundary": "HighEvidenceReadiness != Truth; reflected/model evidence cannot masquerade as witnessed execution.",
    }


def evaluate_root_cause(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/root-cause-collapse/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/root-cause-collapse/v0.1'")
    findings_raw = require_list(model.get("findings"), "findings")
    findings: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(findings_raw):
        item = require_object(raw, f"findings[{index}]")
        finding_id = require_text(item.get("id"), f"findings[{index}].id")
        require_text(item.get("invariant"), f"findings[{index}].invariant")
        if finding_id in findings:
            raise ProofIntegrityError(f"duplicate finding id: {finding_id}")
        findings[finding_id] = item
    edges = require_list(model.get("edges"), "edges")
    children: dict[str, list[str]] = {finding_id: [] for finding_id in findings}
    incoming: dict[str, int] = {finding_id: 0 for finding_id in findings}
    for index, raw in enumerate(edges):
        edge = require_object(raw, f"edges[{index}]")
        source = require_text(edge.get("from"), f"edges[{index}].from")
        target = require_text(edge.get("to"), f"edges[{index}].to")
        relation = require_text(edge.get("relation"), f"edges[{index}].relation")
        if relation != "CAUSES":
            raise ProofIntegrityError("root-cause v0.1 supports only CAUSES edges")
        if source not in findings or target not in findings:
            raise ProofIntegrityError("root-cause edge references unknown finding")
        children[source].append(target)
        incoming[target] += 1

    visiting: set[str] = set()
    visited: set[str] = set()
    cycle = False

    def walk(node: str) -> None:
        nonlocal cycle
        if node in visiting:
            cycle = True
            return
        if node in visited:
            return
        visiting.add(node)
        for child in children[node]:
            walk(child)
        visiting.remove(node)
        visited.add(node)

    for finding_id in sorted(findings):
        walk(finding_id)
    if cycle:
        return {
            "schema": "cgqa/root-cause-collapse-result/v0.1",
            "status": "fail",
            "roots": [],
            "reasons": ["CAUSAL_GRAPH_CYCLE"],
            "claimBoundary": "Root-cause collapse is graph-relative and is not universal causality proof.",
        }

    roots = sorted(finding_id for finding_id, count in incoming.items() if count == 0)
    groups: list[dict[str, object]] = []
    for root in roots:
        descendants: set[str] = set()
        stack = list(children[root])
        while stack:
            current = stack.pop()
            if current in descendants:
                continue
            descendants.add(current)
            stack.extend(children[current])
        groups.append(
            {
                "rootFindingId": root,
                "rootInvariant": findings[root]["invariant"],
                "downstreamFindingIds": sorted(descendants),
            }
        )
    return {
        "schema": "cgqa/root-cause-collapse-result/v0.1",
        "status": "pass",
        "roots": groups,
        "independentRootCount": len(roots),
        "inputHash": canonical_sha256(model),
        "claimBoundary": "many red symptoms != many independent root defects; collapse is relative to declared CAUSES edges.",
    }


def evaluate_metamorphic(data: object) -> dict[str, object]:
    model = require_object(data, "model")
    if model.get("schema") != "cgqa/metamorphic-roundtrip/v0.1":
        raise ProofIntegrityError("schema must equal 'cgqa/metamorphic-roundtrip/v0.1'")
    _, subject_hash = require_subject(model)
    cases = require_list(model.get("cases"), "cases")
    results: list[dict[str, object]] = []
    for index, raw in enumerate(cases):
        case = require_object(raw, f"cases[{index}]")
        case_id = require_text(case.get("id"), f"cases[{index}].id")
        before = require_object(case.get("before"), f"cases[{index}].before")
        after = require_object(case.get("after"), f"cases[{index}].after")
        preserve = require_object(case.get("preserve"), f"cases[{index}].preserve")
        mismatches: list[str] = []
        for side_name, side in (("before", before), ("after", after)):
            if side.get("subjectHash") != subject_hash:
                mismatches.append(f"{side_name}.subjectHash")
        for field in ("state", "effects", "history"):
            if field not in before or field not in after:
                raise ProofIntegrityError(f"case {case_id} requires before/after {field}")
            required = preserve.get(field, True)
            require_bool(required, f"cases[{index}].preserve.{field}")
            if required and before[field] != after[field]:
                mismatches.append(field)
        results.append({"id": case_id, "status": "pass" if not mismatches else "fail", "mismatches": sorted(mismatches)})
    failed = [row["id"] for row in results if row["status"] == "fail"]
    return {
        "schema": "cgqa/metamorphic-roundtrip-result/v0.1",
        "status": "pass" if not failed else "fail",
        "subjectHash": subject_hash,
        "inputHash": canonical_sha256(model),
        "cases": results,
        "failedCaseIds": failed,
        "claimBoundary": "Round-trip preservation proves only the declared relational properties for the supplied transformation boundary.",
    }


def _safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ProofIntegrityError(f"unsafe durable evidence path: {value}")
    return path.as_posix()


def build_durable_manifest(root: Path, paths: list[str]) -> dict[str, object]:
    root = root.resolve()
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_path in sorted(paths):
        relative = _safe_relative_path(raw_path)
        if relative in seen:
            raise ProofIntegrityError(f"duplicate durable evidence path: {relative}")
        seen.add(relative)
        file_path = (root / relative).resolve()
        if root not in file_path.parents and file_path != root:
            raise ProofIntegrityError(f"durable evidence path escapes root: {relative}")
        payload = file_path.read_bytes()
        entries.append(
            {
                "path": relative,
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    manifest: dict[str, object] = {
        "schema": "cgqa/durable-evidence-manifest/v0.1",
        "entries": entries,
    }
    manifest["manifestHash"] = canonical_sha256(manifest)
    return manifest


def verify_durable_manifest(root: Path, manifest: object) -> dict[str, object]:
    manifest_obj = require_object(manifest, "manifest")
    if manifest_obj.get("schema") != "cgqa/durable-evidence-manifest/v0.1":
        raise ProofIntegrityError("unsupported durable evidence manifest schema")
    entries = require_list(manifest_obj.get("entries"), "manifest.entries")
    expected_hash = manifest_obj.get("manifestHash")
    unsigned = {"schema": manifest_obj["schema"], "entries": entries}
    reasons: list[dict[str, object]] = []
    if expected_hash != canonical_sha256(unsigned):
        reasons.append({"code": "MANIFEST_HASH_MISMATCH", "refs": []})
    root = root.resolve()
    seen: set[str] = set()
    for index, raw in enumerate(entries):
        entry = require_object(raw, f"manifest.entries[{index}]")
        relative = _safe_relative_path(require_text(entry.get("path"), f"manifest.entries[{index}].path"))
        if relative in seen:
            reasons.append({"code": "DUPLICATE_MANIFEST_ENTRY", "refs": [relative]})
            continue
        seen.add(relative)
        file_path = (root / relative).resolve()
        if root not in file_path.parents and file_path != root:
            reasons.append({"code": "PATH_ESCAPE", "refs": [relative]})
            continue
        if not file_path.is_file():
            reasons.append({"code": "MISSING_ARTIFACT", "refs": [relative]})
            continue
        payload = file_path.read_bytes()
        if len(payload) != entry.get("size"):
            reasons.append({"code": "SIZE_MISMATCH", "refs": [relative]})
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            reasons.append({"code": "SHA256_MISMATCH", "refs": [relative]})
    reasons.sort(key=lambda row: (str(row["code"]), tuple(row["refs"])))
    return {
        "schema": "cgqa/durable-evidence-verification/v0.1",
        "status": "pass" if not reasons else "fail",
        "manifestHash": expected_hash,
        "verifiedEntryCount": len(entries) if not reasons else len(entries) - len({ref for row in reasons for ref in row["refs"]}),
        "reasons": reasons,
        "claimBoundary": "InMemoryVerified != DurableEvidenceVerified; durable reopen does not prove external authenticity without an independent anchor.",
    }
