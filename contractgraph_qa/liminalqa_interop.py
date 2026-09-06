"""Strict, file-first ContractGraph-QA <-> LiminalQA interop profiles.

The bridge deliberately separates evidence from authority:

* ContractGraph-QA exports bounded invariant-search evidence without computing
  an LTP continuity verdict or an action-authorization decision.
* LiminalQA candidate exports are accepted only as non-authoritative search
  seeds.  ContractGraph-QA must independently re-run them against the exact
  subject before making any verification claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Iterable

from contractgraph_qa import __version__
from contractgraph_qa.engagement import STATUSES, build_engagement

CGQA_EVIDENCE_SCHEMA = "org.contractgraph-qa.liminalqa-evidence.v0.1"
CGQA_EVIDENCE_PROFILE = "org.contractgraph-qa.bounded-invariant-evidence.v0.1"
LIMINAL_CANDIDATE_SCHEMA = "org.liminalqa.cgqa-candidates.v0.1"
LIMINAL_CANDIDATE_PROFILE = "org.liminalqa.non-authoritative-candidate-seeds.v0.1"
LIMINAL_CANDIDATE_SCHEMA_SHA256 = "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60"
CGQA_IMPORT_SCHEMA = "org.contractgraph-qa.liminalqa-candidate-import.v0.1"
CGQA_IMPORT_PROFILE = "org.contractgraph-qa.non-authoritative-seed-intake.v0.1"

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class LiminalQaInteropError(ValueError):
    """Expected profile validation or projection failure."""


class _DuplicateJsonKey(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LiminalQaInteropError(message)


def _object(value: Any, field: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    _require(isinstance(value, list), f"{field} must be an array")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], field: str) -> None:
    missing = sorted(expected - set(value))
    extras = sorted(set(value) - expected)
    _require(not missing, f"{field} is missing required fields: {', '.join(missing)}")
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _non_blank(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")
    return value.strip()


def _safe_id(value: Any, field: str) -> str:
    text = _non_blank(value, field)
    _require(bool(SAFE_ID.fullmatch(text)), f"{field} contains unsafe identifier characters")
    return text


def _sha256(value: Any, field: str) -> str:
    text = _non_blank(value, field)
    _require(bool(SHA256_HEX.fullmatch(text)), f"{field} must be lowercase SHA-256 hex")
    return text


def _commit_sha(value: Any, field: str) -> str:
    text = _non_blank(value, field)
    _require(bool(COMMIT_SHA.fullmatch(text)), f"{field} must be a full lowercase 40-character commit SHA")
    return text


def _non_negative_int(value: Any, field: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0,
        f"{field} must be a non-negative integer",
    )
    return value


def _timestamp(value: Any, field: str) -> str:
    text = _non_blank(value, field)
    _require(text.endswith("Z") or bool(re.search(r"[+-]\d{2}:\d{2}$", text)), f"{field} must include an explicit UTC offset")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise LiminalQaInteropError(f"{field} must be an RFC 3339 timestamp") from exc
    _require(parsed.tzinfo is not None, f"{field} must include an explicit UTC offset")
    return text


def _timestamp_value(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the cross-language v0.1 canonical representation."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LiminalQaInteropError(f"profile is not canonical JSON data: {exc}") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _decode_profile_bytes(raw: bytes, field: str) -> dict[str, Any]:
    _require(isinstance(raw, bytes), f"{field} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonKey, ValueError) as exc:
        raise LiminalQaInteropError(f"{field} is not valid unambiguous JSON: {exc}") from exc
    return _object(value, field)


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_subject(subject: Any, field: str = "subject") -> dict[str, Any]:
    obj = _object(subject, field)
    _exact_keys(obj, {"repository", "commitSha", "contract", "network", "scopeId"}, field)
    for key in ("repository", "contract", "network", "scopeId"):
        _non_blank(obj.get(key), f"{field}.{key}")
    _commit_sha(obj.get("commitSha"), f"{field}.commitSha")
    return obj


def _validate_identity(identity: Any, field: str = "identity") -> dict[str, Any]:
    obj = _object(identity, field)
    _exact_keys(obj, {"traceId", "operationId", "attemptId"}, field)
    for key in ("traceId", "operationId", "attemptId"):
        _safe_id(obj.get(key), f"{field}.{key}")
    return obj


def _validate_times(times: Any, field: str = "times") -> dict[str, Any]:
    obj = _object(times, field)
    _exact_keys(obj, {"validAt", "observedAt", "recordedAt"}, field)
    valid_at = _timestamp(obj.get("validAt"), f"{field}.validAt")
    observed_at = _timestamp(obj.get("observedAt"), f"{field}.observedAt")
    recorded_at = _timestamp(obj.get("recordedAt"), f"{field}.recordedAt")
    _require(
        _timestamp_value(valid_at) <= _timestamp_value(observed_at) <= _timestamp_value(recorded_at),
        f"{field} must satisfy validAt <= observedAt <= recordedAt",
    )
    return obj


def build_liminalqa_evidence_export(
    manifest: dict[str, Any],
    result: dict[str, Any],
    *,
    repository: str,
    commit_sha: str,
    adapter_version: str,
    trace_id: str,
    operation_id: str,
    attempt_id: str,
    valid_at: str,
    observed_at: str,
    recorded_at: str,
    causal_parents: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a deterministic CGQA evidence export for LiminalQA."""

    engagement, _ = build_engagement(manifest, result)
    subject = {
        "repository": _non_blank(repository, "repository"),
        "commitSha": _commit_sha(commit_sha, "commitSha"),
        "contract": engagement["contract"],
        "network": engagement["network"],
        "scopeId": engagement["scopeId"],
    }
    identity = {
        "traceId": _safe_id(trace_id, "traceId"),
        "operationId": _safe_id(operation_id, "operationId"),
        "attemptId": _safe_id(attempt_id, "attemptId"),
    }
    times = {
        "validAt": _timestamp(valid_at, "validAt"),
        "observedAt": _timestamp(observed_at, "observedAt"),
        "recordedAt": _timestamp(recorded_at, "recordedAt"),
    }
    _validate_times(times)

    parent_list = [_safe_id(parent, f"causalParents[{index}]") for index, parent in enumerate(causal_parents)]
    _require(len(parent_list) == len(set(parent_list)), "causalParents must not contain duplicates")

    engagement_bytes = canonical_json_bytes(engagement)
    checks = [dict(check) for check in engagement["checks"]]
    counts = {status: sum(check["status"] == status for check in checks) for status in sorted(STATUSES)}
    debt = [
        {
            "invariantId": check["invariantId"],
            "status": "inconclusive",
            "reason": check["notes"],
        }
        for check in checks
        if check["status"] == "inconclusive"
    ]

    profile: dict[str, Any] = {
        "schema": CGQA_EVIDENCE_SCHEMA,
        "profile": CGQA_EVIDENCE_PROFILE,
        "producer": {"name": "contractgraph-qa", "version": __version__},
        "subject": subject,
        "identity": identity,
        "times": times,
        "adapter": {
            "id": engagement["adapterId"],
            "version": _non_blank(adapter_version, "adapterVersion"),
            "digest": {"algorithm": "sha256", "value": engagement["manifestSha256"]},
        },
        "bound": {
            "searchRunId": engagement["searchRunId"],
            "maxDepth": manifest["search"]["maxDepth"],
            "exploredCandidates": sum(check["exploredCandidates"] for check in checks),
            "replay": engagement["replay"],
        },
        "assessment": {
            "kind": "bounded_invariant_search",
            "statusVocabulary": ["violated", "not_found_within_bound", "inconclusive"],
            "counts": counts,
            "continuityVerdict": "not_computed",
        },
        "checks": checks,
        "artifacts": [
            {
                "artifactId": "engagement-json",
                "mediaType": "application/json",
                "sha256": sha256_hex(engagement_bytes),
                "bytes": len(engagement_bytes),
            }
        ],
        "causalParents": parent_list,
        "verificationDebt": debt,
        "limitations": [
            "A bounded search result is not proof that no violation exists outside the declared bound.",
            "The evidence is bound only to the exact repository commit and subject declared here.",
            "No request/outcome continuity verdict was computed; LTP remains the continuity verdict owner.",
            "This artifact is evidence only and does not authorize an action.",
        ],
        "authority": {
            "classification": "evidence_only",
            "mayAuthorizeAction": False,
            "actionAuthorization": "not_evaluated",
            "continuityVerdictOwner": "ltp",
        },
    }
    profile["exportId"] = "cgqa-liminalqa-" + sha256_hex(canonical_json_bytes(profile))[:24]
    validate_liminalqa_evidence_export(profile)
    return profile


def validate_liminalqa_evidence_export(profile: Any) -> dict[str, Any]:
    """Validate the producer-owned CGQA -> LiminalQA v0.1 profile."""

    obj = _object(profile, "evidence")
    _exact_keys(
        obj,
        {
            "schema", "profile", "exportId", "producer", "subject", "identity", "times",
            "adapter", "bound", "assessment", "checks", "artifacts", "causalParents",
            "verificationDebt", "limitations", "authority",
        },
        "evidence",
    )
    _require(obj["schema"] == CGQA_EVIDENCE_SCHEMA, "evidence.schema is unsupported")
    _require(obj["profile"] == CGQA_EVIDENCE_PROFILE, "evidence.profile is unsupported")
    _safe_id(obj["exportId"], "evidence.exportId")

    producer = _object(obj["producer"], "evidence.producer")
    _exact_keys(producer, {"name", "version"}, "evidence.producer")
    _require(producer.get("name") == "contractgraph-qa", "evidence.producer.name must be contractgraph-qa")
    _non_blank(producer.get("version"), "evidence.producer.version")
    _validate_subject(obj["subject"], "evidence.subject")
    _validate_identity(obj["identity"], "evidence.identity")
    _validate_times(obj["times"], "evidence.times")

    adapter = _object(obj["adapter"], "evidence.adapter")
    _exact_keys(adapter, {"id", "version", "digest"}, "evidence.adapter")
    _non_blank(adapter.get("id"), "evidence.adapter.id")
    _non_blank(adapter.get("version"), "evidence.adapter.version")
    digest = _object(adapter.get("digest"), "evidence.adapter.digest")
    _exact_keys(digest, {"algorithm", "value"}, "evidence.adapter.digest")
    _require(digest.get("algorithm") == "sha256", "evidence.adapter.digest.algorithm must be sha256")
    _sha256(digest.get("value"), "evidence.adapter.digest.value")

    bound = _object(obj["bound"], "evidence.bound")
    _exact_keys(bound, {"searchRunId", "maxDepth", "exploredCandidates", "replay"}, "evidence.bound")
    _safe_id(bound.get("searchRunId"), "evidence.bound.searchRunId")
    _require(_non_negative_int(bound.get("maxDepth"), "evidence.bound.maxDepth") > 0, "evidence.bound.maxDepth must be greater than zero")
    explored = _non_negative_int(bound.get("exploredCandidates"), "evidence.bound.exploredCandidates")
    _non_blank(bound.get("replay"), "evidence.bound.replay")

    assessment = _object(obj["assessment"], "evidence.assessment")
    _exact_keys(assessment, {"kind", "statusVocabulary", "counts", "continuityVerdict"}, "evidence.assessment")
    _require(assessment.get("kind") == "bounded_invariant_search", "evidence.assessment.kind is unsupported")
    _require(
        assessment.get("statusVocabulary") == ["violated", "not_found_within_bound", "inconclusive"],
        "evidence.assessment.statusVocabulary must preserve the canonical CGQA statuses",
    )
    _require(assessment.get("continuityVerdict") == "not_computed", "evidence must not contain a continuity verdict")

    counts = _object(assessment.get("counts"), "evidence.assessment.counts")
    _exact_keys(counts, STATUSES, "evidence.assessment.counts")
    for status in STATUSES:
        _non_negative_int(counts.get(status), f"evidence.assessment.counts.{status}")

    checks = _array(obj["checks"], "evidence.checks")
    _require(bool(checks), "evidence.checks must be non-empty")
    seen_invariants: set[str] = set()
    recomputed = {status: 0 for status in STATUSES}
    recomputed_explored = 0
    for index, item in enumerate(checks):
        check = _object(item, f"evidence.checks[{index}]")
        common = {"invariantId", "title", "severity", "status", "exploredCandidates", "notes"}
        status = _non_blank(check.get("status"), f"evidence.checks[{index}].status")
        _require(status in STATUSES, f"evidence.checks[{index}].status is unsupported")
        expected = common | ({"findingId", "pathLength"} if status == "violated" else set())
        _exact_keys(check, expected, f"evidence.checks[{index}]")
        invariant = _safe_id(check.get("invariantId"), f"evidence.checks[{index}].invariantId")
        _require(invariant not in seen_invariants, f"duplicate invariant in evidence.checks: {invariant}")
        seen_invariants.add(invariant)
        for name in ("title", "notes"):
            _non_blank(check.get(name), f"evidence.checks[{index}].{name}")
        _require(
            check.get("severity") in {"critical", "high", "medium", "low", "info"},
            f"evidence.checks[{index}].severity is unsupported",
        )
        count = _non_negative_int(check.get("exploredCandidates"), f"evidence.checks[{index}].exploredCandidates")
        recomputed_explored += count
        recomputed[status] += 1
        if status == "violated":
            _safe_id(check.get("findingId"), f"evidence.checks[{index}].findingId")
            _require(_non_negative_int(check.get("pathLength"), f"evidence.checks[{index}].pathLength") > 0, f"evidence.checks[{index}].pathLength must be greater than zero")
    _require(counts == recomputed, "evidence.assessment.counts does not match evidence.checks")
    _require(explored == recomputed_explored, "evidence.bound.exploredCandidates does not match evidence.checks")

    artifacts = _array(obj["artifacts"], "evidence.artifacts")
    _require(bool(artifacts), "evidence.artifacts must be non-empty")
    seen_artifacts: set[str] = set()
    for index, item in enumerate(artifacts):
        artifact = _object(item, f"evidence.artifacts[{index}]")
        _exact_keys(artifact, {"artifactId", "mediaType", "sha256", "bytes"}, f"evidence.artifacts[{index}]")
        artifact_id = _safe_id(artifact.get("artifactId"), f"evidence.artifacts[{index}].artifactId")
        _require(artifact_id not in seen_artifacts, f"duplicate evidence artifact id: {artifact_id}")
        seen_artifacts.add(artifact_id)
        _non_blank(artifact.get("mediaType"), f"evidence.artifacts[{index}].mediaType")
        _sha256(artifact.get("sha256"), f"evidence.artifacts[{index}].sha256")
        _require(_non_negative_int(artifact.get("bytes"), f"evidence.artifacts[{index}].bytes") > 0, f"evidence.artifacts[{index}].bytes must be greater than zero")

    parents = _array(obj["causalParents"], "evidence.causalParents")
    normalized_parents = [_safe_id(parent, f"evidence.causalParents[{index}]") for index, parent in enumerate(parents)]
    _require(len(normalized_parents) == len(set(normalized_parents)), "evidence.causalParents contains duplicates")

    debt = _array(obj["verificationDebt"], "evidence.verificationDebt")
    debt_ids: set[str] = set()
    for index, item in enumerate(debt):
        row = _object(item, f"evidence.verificationDebt[{index}]")
        _exact_keys(row, {"invariantId", "status", "reason"}, f"evidence.verificationDebt[{index}]")
        invariant = _safe_id(row.get("invariantId"), f"evidence.verificationDebt[{index}].invariantId")
        _require(invariant not in debt_ids, "evidence.verificationDebt contains duplicate invariants")
        _require(row.get("status") == "inconclusive", f"evidence.verificationDebt[{index}].status must be inconclusive")
        _non_blank(row.get("reason"), f"evidence.verificationDebt[{index}].reason")
        debt_ids.add(invariant)
    inconclusive_ids = {check["invariantId"] for check in checks if check["status"] == "inconclusive"}
    _require(debt_ids == inconclusive_ids, "evidence.verificationDebt must enumerate every and only inconclusive check")

    limitations = _array(obj["limitations"], "evidence.limitations")
    _require(bool(limitations), "evidence.limitations must be non-empty")
    for index, limitation in enumerate(limitations):
        _non_blank(limitation, f"evidence.limitations[{index}]")

    authority = _object(obj["authority"], "evidence.authority")
    _exact_keys(authority, {"classification", "mayAuthorizeAction", "actionAuthorization", "continuityVerdictOwner"}, "evidence.authority")
    _require(authority.get("classification") == "evidence_only", "evidence.authority.classification must be evidence_only")
    _require(authority.get("mayAuthorizeAction") is False, "evidence.authority.mayAuthorizeAction must be false")
    _require(authority.get("actionAuthorization") == "not_evaluated", "evidence must not assert action authorization")
    _require(authority.get("continuityVerdictOwner") == "ltp", "evidence.authority.continuityVerdictOwner must be ltp")
    return obj


def validate_liminalqa_candidate_export(profile: Any) -> dict[str, Any]:
    """Validate the LiminalQA-owned non-authoritative candidate profile."""

    obj = _object(profile, "candidateExport")
    _exact_keys(
        obj,
        {
            "schema", "profile", "exportId", "producer", "sourceEvidence", "subject",
            "identity", "derivedAt", "authority", "candidates", "causalParents",
            "limitations", "verificationDebt",
        },
        "candidateExport",
    )
    _require(obj.get("schema") == LIMINAL_CANDIDATE_SCHEMA, "candidateExport.schema is unsupported")
    _require(obj.get("profile") == LIMINAL_CANDIDATE_PROFILE, "candidateExport.profile is unsupported")
    _safe_id(obj.get("exportId"), "candidateExport.exportId")
    producer = _object(obj.get("producer"), "candidateExport.producer")
    _exact_keys(producer, {"name", "version"}, "candidateExport.producer")
    _require(producer.get("name") == "liminalqa", "candidateExport.producer.name must be liminalqa")
    _non_blank(producer.get("version"), "candidateExport.producer.version")

    source = _object(obj.get("sourceEvidence"), "candidateExport.sourceEvidence")
    _exact_keys(source, {"schema", "exportId", "sha256"}, "candidateExport.sourceEvidence")
    _require(source.get("schema") == CGQA_EVIDENCE_SCHEMA, "candidateExport.sourceEvidence.schema is unsupported")
    _safe_id(source.get("exportId"), "candidateExport.sourceEvidence.exportId")
    _sha256(source.get("sha256"), "candidateExport.sourceEvidence.sha256")
    _validate_subject(obj.get("subject"), "candidateExport.subject")
    _validate_identity(obj.get("identity"), "candidateExport.identity")
    _timestamp(obj.get("derivedAt"), "candidateExport.derivedAt")

    authority = _object(obj.get("authority"), "candidateExport.authority")
    _exact_keys(authority, {"classification", "mayAuthorizeAction", "requiresCgqaVerification"}, "candidateExport.authority")
    _require(authority.get("classification") == "non_authoritative_seed", "candidateExport authority must be non_authoritative_seed")
    _require(authority.get("mayAuthorizeAction") is False, "candidateExport mayAuthorizeAction must be false")
    _require(authority.get("requiresCgqaVerification") is True, "candidateExport requiresCgqaVerification must be true")

    candidates = _array(obj.get("candidates"), "candidateExport.candidates")
    seen_candidates: set[str] = set()
    seen_invariants: set[str] = set()
    for index, item in enumerate(candidates):
        candidate = _object(item, f"candidateExport.candidates[{index}]")
        _exact_keys(candidate, {"candidateId", "invariantId", "sourceStatus", "kind", "priority", "reason", "requiredChecks"}, f"candidateExport.candidates[{index}]")
        candidate_id = _safe_id(candidate.get("candidateId"), f"candidateExport.candidates[{index}].candidateId")
        _require(candidate_id not in seen_candidates, f"duplicate candidate id: {candidate_id}")
        seen_candidates.add(candidate_id)
        invariant_id = _safe_id(candidate.get("invariantId"), f"candidateExport.candidates[{index}].invariantId")
        _require(invariant_id not in seen_invariants, f"duplicate candidate invariant: {invariant_id}")
        seen_invariants.add(invariant_id)
        source_status = candidate.get("sourceStatus")
        _require(source_status in {"violated", "inconclusive"}, f"candidateExport.candidates[{index}].sourceStatus must be violated or inconclusive")
        expected_kind = "replay_regression" if source_status == "violated" else "verification_debt"
        _require(candidate.get("kind") == expected_kind, f"candidateExport.candidates[{index}].kind does not match sourceStatus")
        _require(candidate.get("priority") in {"critical", "high", "medium", "low"}, f"candidateExport.candidates[{index}].priority is unsupported")
        _non_blank(candidate.get("reason"), f"candidateExport.candidates[{index}].reason")
        required_checks = _array(candidate.get("requiredChecks"), f"candidateExport.candidates[{index}].requiredChecks")
        _require(bool(required_checks), f"candidateExport.candidates[{index}].requiredChecks must be non-empty")
        normalized_checks = {
            _non_blank(check, f"candidateExport.candidates[{index}].requiredChecks[{check_index}]")
            for check_index, check in enumerate(required_checks)
        }
        _require(
            len(normalized_checks) == len(required_checks),
            f"candidateExport.candidates[{index}].requiredChecks contains duplicates",
        )
        required = {"exact_subject", "independent_cgqa_replay"}
        required.add("failing_path_integrity" if source_status == "violated" else "reviewed_bound_change")
        _require(
            required <= normalized_checks,
            f"candidateExport.candidates[{index}].requiredChecks omits mandatory fresh-verification checks",
        )

    parents = _array(obj.get("causalParents"), "candidateExport.causalParents")
    normalized_parents = [_safe_id(parent, f"candidateExport.causalParents[{index}]") for index, parent in enumerate(parents)]
    _require(source["exportId"] in normalized_parents, "candidateExport.causalParents must include the source evidence exportId")
    _require(len(normalized_parents) == len(set(normalized_parents)), "candidateExport.causalParents contains duplicates")
    limitations = _array(obj.get("limitations"), "candidateExport.limitations")
    _require(bool(limitations), "candidateExport.limitations must be non-empty")
    for index, limitation in enumerate(limitations):
        _non_blank(limitation, f"candidateExport.limitations[{index}]")
    debt = _array(obj.get("verificationDebt"), "candidateExport.verificationDebt")
    debt_ids: set[str] = set()
    for index, item in enumerate(debt):
        row = _object(item, f"candidateExport.verificationDebt[{index}]")
        _exact_keys(row, {"invariantId", "reason"}, f"candidateExport.verificationDebt[{index}]")
        invariant_id = _safe_id(row.get("invariantId"), f"candidateExport.verificationDebt[{index}].invariantId")
        _require(invariant_id not in debt_ids, "candidateExport.verificationDebt contains duplicate invariants")
        debt_ids.add(invariant_id)
        _non_blank(row.get("reason"), f"candidateExport.verificationDebt[{index}].reason")
    expected_debt = {candidate["invariantId"] for candidate in candidates if candidate["sourceStatus"] == "inconclusive"}
    _require(debt_ids == expected_debt, "candidateExport.verificationDebt must enumerate every and only inconclusive candidate")
    return obj


def import_liminalqa_candidates(profile: Any, *, source_bytes: bytes | None = None) -> dict[str, Any]:
    """Create a deterministic receipt without treating candidates as verified findings."""

    candidate_export = validate_liminalqa_candidate_export(profile)
    if source_bytes is None:
        raw = canonical_json_bytes(candidate_export)
    else:
        decoded_source = _decode_profile_bytes(source_bytes, "sourceBytes")
        _require(
            decoded_source == candidate_export,
            "sourceBytes does not encode the validated candidate export",
        )
        raw = source_bytes
    candidates = [
        {
            "candidateId": candidate["candidateId"],
            "invariantId": candidate["invariantId"],
            "sourceStatus": candidate["sourceStatus"],
            "kind": candidate["kind"],
            "priority": candidate["priority"],
        }
        for candidate in candidate_export["candidates"]
    ]
    receipt: dict[str, Any] = {
        "schema": CGQA_IMPORT_SCHEMA,
        "profile": CGQA_IMPORT_PROFILE,
        "consumer": {"name": "contractgraph-qa", "version": __version__},
        "source": {
            "schema": candidate_export["schema"],
            "exportId": candidate_export["exportId"],
            "sha256": sha256_hex(raw),
        },
        "subject": dict(candidate_export["subject"]),
        "identity": dict(candidate_export["identity"]),
        "acceptedAs": "non_authoritative_seed",
        "mayAuthorizeAction": False,
        "requiresFreshCgqaVerification": True,
        "candidateCount": len(candidates),
        "candidates": candidates,
        "limitations": [
            "Import validates the interchange profile; it does not verify a candidate against the subject.",
            "Every candidate must be independently replayed by ContractGraph-QA against the exact commit.",
            "The receipt is not an action authorization or an LTP continuity verdict.",
        ],
    }
    receipt["receiptId"] = "cgqa-seed-import-" + sha256_hex(canonical_json_bytes(receipt))[:24]
    return receipt
