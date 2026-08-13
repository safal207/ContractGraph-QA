"""Deterministic customer-facing evidence pack for agent-payment decisions."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from contractgraph_qa.agent_payment_decision import (
    AgentPaymentDecisionError,
    evaluate_agent_payment_decision,
)

PACK_SCHEMA = "cgqa.agent-payment-evidence-pack.v0.1"
MANIFEST_SCHEMA = "cgqa.agent-payment-evidence-pack-manifest.v0.1"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_CONTENT_NAMES = ["input.json", "decision.json", "customer-summary.md"]
_PACK_NAMES = [*_CONTENT_NAMES, "manifest.json"]
_AUTHORITY = {
    "classification": "RESEARCH_ONLY",
    "securityCertification": False,
    "productionAuthorization": False,
    "financialAuthorization": False,
}


class PaymentEvidencePackError(ValueError):
    """Raised when a customer evidence pack is invalid or cannot be verified."""


def _canonical_json(payload: object) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PaymentEvidencePackError(f"unable to read decision input: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PaymentEvidencePackError(f"invalid decision input JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaymentEvidencePackError("decision input root must be an object")
    return payload


def _customer_summary(decision: dict[str, Any]) -> bytes:
    state = decision["state"]
    authority = state["authority"]
    payment = state["payment"]
    fulfillment = state["fulfillment"]
    decision_name = str(decision["decision"])
    money = "YES" if decision["monetaryActionAllowed"] else "NO"

    remediation = {
        "ALLOW": "Proceed only within the currently proven authorization and operation scope.",
        "HOLD": "Do not perform another monetary action. Resolve the listed authority blocker first.",
        "STOP": "Do not perform another monetary action for this logical operation.",
        "RECONCILE": "Collect discriminating evidence for the unresolved state before any new monetary action.",
        "COMPENSATE": "Resolve refund or compensation disposition before any repurchase or replacement payment.",
    }[decision_name]

    blockers = decision.get("blockers", [])
    blocker_text = ", ".join(str(item) for item in blockers) if blockers else "none"
    lines = [
        "# Agent Payment Evidence Pack v0.1",
        "",
        "## Executive verdict",
        "",
        f"**Decision: `{decision_name}` — monetary action allowed: `{money}`.**",
        "",
        remediation,
        "",
        "## Causal decision chain",
        "",
        "| Claim | Observed state | Evidence |",
        "|---|---|---|",
        f"| Authority | `{authority['status']}` | `{authority['evidenceRef']}` |",
        f"| Payment | `{payment['outcome']}` / reconciliation `{payment['reconciliationStatus']}` | `{payment['evidenceRef']}` |",
        f"| Retry authority | `{payment['retryAuthorityStatus']}` / allowed `{str(payment['retryAllowed']).lower()}` | payment decision state |",
        f"| Fulfillment | `{fulfillment['outcome']}` / required `{str(fulfillment['required']).lower()}` | `{fulfillment['evidenceRef']}` |",
        f"| Gate | `{decision_name}` | reason `{decision['reason']}` |",
        "",
        f"**Blocking coordinate(s):** {blocker_text}",
        "",
        "## Safety invariant",
        "",
        "A final financial state does not by itself authorize a new financial action. In particular, a committed payment with unresolved fulfillment remains fail-closed until fulfillment or compensation is reconciled.",
        "",
        "## Recommended next proof",
        "",
        "1. Obtain evidence that resolves the blocking coordinate named above.",
        "2. Re-run the unified Agent Payment Decision Gate with the new evidence state.",
        "3. Permit another monetary action only if the new machine decision is `ALLOW`.",
        "",
        "## Scope boundary",
        "",
        "This pack is a deterministic research/customer-communication artifact. It does not call a provider, move funds, certify security, or grant production financial authority. Synthetic demo evidence must not be represented as a provider-specific finding.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def _zip_entry(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_payment_evidence_pack(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Build a deterministic ZIP containing source state, decision, summary and hashes."""
    payload = _load_json(input_path)
    try:
        decision = evaluate_agent_payment_decision(payload)
    except AgentPaymentDecisionError as exc:
        raise PaymentEvidencePackError(str(exc)) from exc

    artifacts = {
        "input.json": _canonical_json(payload),
        "decision.json": _canonical_json(decision),
        "customer-summary.md": _customer_summary(decision),
    }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "packSchema": PACK_SCHEMA,
        "decisionId": decision["decisionId"],
        "logicalOperationId": decision["logicalOperationId"],
        "decision": decision["decision"],
        "monetaryActionAllowed": decision["monetaryActionAllowed"],
        "entries": [
            {"path": name, "sha256": _sha256(artifacts[name]), "bytes": len(artifacts[name])}
            for name in _CONTENT_NAMES
        ],
        "authority": dict(_AUTHORITY),
    }
    manifest_bytes = _canonical_json(manifest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in _CONTENT_NAMES:
            archive.writestr(_zip_entry(name), artifacts[name])
        archive.writestr(_zip_entry("manifest.json"), manifest_bytes)

    pack_bytes = output_path.read_bytes()
    return {
        "schema": PACK_SCHEMA,
        "output": str(output_path),
        "sha256": _sha256(pack_bytes),
        "decision": decision["decision"],
        "monetaryActionAllowed": decision["monetaryActionAllowed"],
        "entries": _PACK_NAMES,
    }


def verify_payment_evidence_pack(pack_path: Path) -> dict[str, Any]:
    """Verify canonical ZIP metadata, hashes, decision and human summary."""
    try:
        with zipfile.ZipFile(pack_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != _PACK_NAMES:
                raise PaymentEvidencePackError(
                    f"pack entries must be exactly {', '.join(_PACK_NAMES)} in canonical order"
                )
            for info in infos:
                if info.date_time != _FIXED_ZIP_TIME:
                    raise PaymentEvidencePackError(f"non-canonical ZIP timestamp: {info.filename}")
                if info.compress_type != zipfile.ZIP_STORED:
                    raise PaymentEvidencePackError(f"non-canonical ZIP compression: {info.filename}")
                if info.create_system != 3 or info.external_attr != 0o100644 << 16:
                    raise PaymentEvidencePackError(f"non-canonical ZIP file mode: {info.filename}")
            blobs = {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise PaymentEvidencePackError(f"unable to read evidence pack: {exc}") from exc

    try:
        manifest = json.loads(blobs["manifest.json"])
        source_input = json.loads(blobs["input.json"])
        packed_decision = json.loads(blobs["decision.json"])
    except json.JSONDecodeError as exc:
        raise PaymentEvidencePackError(f"pack JSON is invalid: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise PaymentEvidencePackError("manifest schema mismatch")
    if manifest.get("packSchema") != PACK_SCHEMA:
        raise PaymentEvidencePackError("manifest packSchema mismatch")
    if manifest.get("authority") != _AUTHORITY:
        raise PaymentEvidencePackError("manifest authority boundary mismatch")
    if blobs["manifest.json"] != _canonical_json(manifest):
        raise PaymentEvidencePackError("manifest.json is not canonical JSON")
    if blobs["input.json"] != _canonical_json(source_input):
        raise PaymentEvidencePackError("input.json is not canonical JSON")
    if blobs["decision.json"] != _canonical_json(packed_decision):
        raise PaymentEvidencePackError("decision.json is not canonical JSON")

    declared = manifest.get("entries")
    if not isinstance(declared, list) or len(declared) != len(_CONTENT_NAMES):
        raise PaymentEvidencePackError("manifest must hash exactly three content entries")
    declared_names = [item.get("path") if isinstance(item, dict) else None for item in declared]
    if declared_names != _CONTENT_NAMES:
        raise PaymentEvidencePackError("manifest content entries are not canonical")
    for item in declared:
        if not isinstance(item, dict):
            raise PaymentEvidencePackError("manifest entry must be an object")
        name = str(item["path"])
        data = blobs[name]
        if item.get("sha256") != _sha256(data) or item.get("bytes") != len(data):
            raise PaymentEvidencePackError(f"content hash/size mismatch: {name}")

    try:
        recomputed = evaluate_agent_payment_decision(source_input)
    except AgentPaymentDecisionError as exc:
        raise PaymentEvidencePackError(f"packed decision input is invalid: {exc}") from exc
    if _canonical_json(recomputed) != blobs["decision.json"]:
        raise PaymentEvidencePackError("decision.json does not match recomputed decision from input.json")
    if _customer_summary(recomputed) != blobs["customer-summary.md"]:
        raise PaymentEvidencePackError("customer-summary.md does not match the recomputed decision")
    if manifest.get("decisionId") != recomputed["decisionId"]:
        raise PaymentEvidencePackError("manifest decisionId mismatch")
    if manifest.get("logicalOperationId") != recomputed["logicalOperationId"]:
        raise PaymentEvidencePackError("manifest logicalOperationId mismatch")
    if manifest.get("decision") != recomputed["decision"]:
        raise PaymentEvidencePackError("manifest decision does not match recomputed decision")
    if manifest.get("monetaryActionAllowed") != recomputed["monetaryActionAllowed"]:
        raise PaymentEvidencePackError("manifest monetaryActionAllowed mismatch")

    return {
        "schema": PACK_SCHEMA,
        "status": "verified",
        "sha256": _sha256(pack_path.read_bytes()),
        "decision": recomputed["decision"],
        "monetaryActionAllowed": recomputed["monetaryActionAllowed"],
        "logicalOperationId": recomputed["logicalOperationId"],
    }
