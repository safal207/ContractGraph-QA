"""Hydrate a static Contract Lattice template with normalized runtime evidence.

The composition keeps claim boundaries explicit:
- Solidity/static extraction proves the declared lifecycle structure and liveness.
- ExecutionTrace proves normalized economic-cardinality and successor-consistency claims.
- Hydration checks that committed runtime transitions conform to the static lattice,
  advance exactly one version, and carry the required authority/time/evidence bindings.

Missing proof material yields INCONCLUSIVE. Contradictory evidence or an impossible
runtime transition yields FAIL. No ambient clock or inferred authority is used.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from contractgraph_qa.execution_trace import (
    ExecutionTrace,
    execution_trace_sha256,
    load_execution_trace,
    run_execution_trace,
)

BINDINGS_SCHEMA_VERSION = "hydration-bindings-v0.1"
RESULT_SCHEMA_VERSION = "hydrated-contract-lattice-result-v0.1"
STATIC_RUNTIME_INVARIANT = "CGQ-HYDRATE-001"
VERSION_INVARIANT = "CGQ-LATTICE-VER-001"
BINDING_INVARIANT = "CGQ-LATTICE-BIND-001"
TIME_INVARIANT = "CGQ-LATTICE-TIME-001"

_BINDING_KEYS = {
    "schemaVersion",
    "bindingId",
    "authorityRequiredOperations",
    "timeSensitiveOperations",
    "commits",
    "scope",
}
_COMMIT_BINDING_KEYS = {"commitId", "authorityRef", "evidenceRefs", "timeWitnessRefs"}


@dataclass(frozen=True, slots=True)
class CommitBinding:
    commit_id: str
    authority_ref: str | None
    evidence_refs: tuple[str, ...]
    time_witness_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HydrationBindings:
    binding_id: str
    authority_required_operations: tuple[str, ...]
    time_sensitive_operations: tuple[str, ...]
    commits: tuple[CommitBinding, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _refs(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list), f"{field} must be an array")
    refs = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(refs) == len(set(refs)), f"{field} must contain unique values")
    return refs


def _canonical_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hydration_bindings_from_dict(data: dict[str, Any]) -> HydrationBindings:
    _require(isinstance(data, dict), "hydration bindings must be a JSON object")
    extras = sorted(set(data) - _BINDING_KEYS)
    _require(not extras, "hydration bindings contain unexpected fields: " + ", ".join(extras))
    required = _BINDING_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "hydration bindings missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == BINDINGS_SCHEMA_VERSION, f"schemaVersion must be {BINDINGS_SCHEMA_VERSION}")

    authority_operations = _refs(data["authorityRequiredOperations"], "authorityRequiredOperations")
    time_operations = _refs(data["timeSensitiveOperations"], "timeSensitiveOperations")
    commits_raw = data["commits"]
    _require(isinstance(commits_raw, list), "commits must be an array")

    commits: list[CommitBinding] = []
    seen: set[str] = set()
    for index, item in enumerate(commits_raw):
        field = f"commits[{index}]"
        _require(isinstance(item, dict), f"{field} must be an object")
        extras = sorted(set(item) - _COMMIT_BINDING_KEYS)
        missing = sorted(_COMMIT_BINDING_KEYS - set(item))
        _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")
        _require(not missing, f"{field} missing required fields: {', '.join(missing)}")
        commit_id = _text(item["commitId"], f"{field}.commitId")
        _require(commit_id not in seen, f"duplicate commitId in hydration bindings: {commit_id}")
        seen.add(commit_id)
        authority_raw = item["authorityRef"]
        _require(authority_raw is None or isinstance(authority_raw, str), f"{field}.authorityRef must be string or null")
        authority_ref = None if authority_raw is None else _text(authority_raw, f"{field}.authorityRef")
        commits.append(
            CommitBinding(
                commit_id=commit_id,
                authority_ref=authority_ref,
                evidence_refs=_refs(item["evidenceRefs"], f"{field}.evidenceRefs"),
                time_witness_refs=_refs(item["timeWitnessRefs"], f"{field}.timeWitnessRefs"),
            )
        )

    scope_raw = data.get("scope")
    scope = None if scope_raw is None else _text(scope_raw, "scope")
    return HydrationBindings(
        binding_id=_text(data["bindingId"], "bindingId"),
        authority_required_operations=authority_operations,
        time_sensitive_operations=time_operations,
        commits=tuple(commits),
        scope=scope,
    )


def load_hydration_bindings(path: Path) -> HydrationBindings:
    with path.open("r", encoding="utf-8") as handle:
        return hydration_bindings_from_dict(json.load(handle))


def hydration_bindings_to_dict(bindings: HydrationBindings) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": BINDINGS_SCHEMA_VERSION,
        "bindingId": bindings.binding_id,
        "authorityRequiredOperations": list(bindings.authority_required_operations),
        "timeSensitiveOperations": list(bindings.time_sensitive_operations),
        "commits": [
            {
                "commitId": item.commit_id,
                "authorityRef": item.authority_ref,
                "evidenceRefs": list(item.evidence_refs),
                "timeWitnessRefs": list(item.time_witness_refs),
            }
            for item in bindings.commits
        ],
    }
    if bindings.scope is not None:
        document["scope"] = bindings.scope
    return document


def hydration_bindings_sha256(bindings: HydrationBindings) -> str:
    return _canonical_sha256(hydration_bindings_to_dict(bindings))


def _static_transition_index(static_result: Mapping[str, object]) -> set[tuple[str, str, str]]:
    template = static_result.get("latticeTemplate")
    _require(isinstance(template, dict), "static result missing latticeTemplate")
    transitions = template.get("transitionTemplates")
    _require(isinstance(transitions, list), "static latticeTemplate.transitionTemplates must be an array")
    allowed: set[tuple[str, str, str]] = set()
    for index, item in enumerate(transitions):
        _require(isinstance(item, dict), f"static transitionTemplates[{index}] must be an object")
        evidence = item.get("sourceEvidence")
        function = evidence.get("function") if isinstance(evidence, dict) else None
        _require(isinstance(function, str) and function, f"static transitionTemplates[{index}] missing source function evidence")
        allowed.add((str(item.get("sourceState")), function, str(item.get("targetState"))))
    return allowed


def _state_semantics(static_result: Mapping[str, object]) -> dict[str, tuple[bool, bool]]:
    template = static_result.get("latticeTemplate")
    _require(isinstance(template, dict), "static result missing latticeTemplate")
    points = template.get("points")
    _require(isinstance(points, list), "static latticeTemplate.points must be an array")
    semantics: dict[str, tuple[bool, bool]] = {}
    for item in points:
        if not isinstance(item, dict):
            continue
        state = item.get("state")
        if isinstance(state, str):
            semantics[state] = (bool(item.get("valuePresence")), bool(item.get("safeTerminal")))
    return semantics


def run_hydrated_lattice(
    static_result: Mapping[str, object],
    trace: ExecutionTrace,
    bindings: HydrationBindings,
) -> dict[str, object]:
    """Compose static possibility evidence with normalized runtime evidence."""

    static_status = static_result.get("status")
    _require(static_status in {"pass", "fail", "inconclusive"}, "static result has invalid status")
    allowed = _static_transition_index(static_result)
    semantics = _state_semantics(static_result)
    trace_result = run_execution_trace(trace)
    binding_by_commit = {item.commit_id: item for item in bindings.commits}

    runtime_violations: list[dict[str, object]] = []
    missing_authority: list[str] = []
    missing_time: list[str] = []
    missing_evidence: list[str] = []
    observed_points: dict[tuple[str, int], dict[str, object]] = {}
    observed_transitions: list[dict[str, object]] = []
    committed_count = 0

    for event in trace.events:
        commit = event.state_commit
        if commit is None or not bool(commit["committed"]):
            continue
        committed_count += 1
        commit_id = str(commit["commitId"])
        source_state = str(commit["parentState"])
        target_state = str(commit["successorState"])
        operation = str(commit["operation"])
        source_version = int(commit["parentVersion"])
        target_version = int(commit["successorVersion"])

        if (source_state, operation, target_state) not in allowed:
            runtime_violations.append(
                {
                    "invariantId": STATIC_RUNTIME_INVARIANT,
                    "kind": "runtime_transition_not_in_static_lattice",
                    "commitId": commit_id,
                    "transition": [source_state, operation, target_state],
                }
            )
        if target_version != source_version + 1:
            runtime_violations.append(
                {
                    "invariantId": VERSION_INVARIANT,
                    "kind": "non_unit_runtime_version_step",
                    "commitId": commit_id,
                    "parentVersion": source_version,
                    "successorVersion": target_version,
                }
            )

        binding = binding_by_commit.get(commit_id)
        if operation in bindings.authority_required_operations and (binding is None or binding.authority_ref is None):
            missing_authority.append(commit_id)
        if operation in bindings.time_sensitive_operations and (binding is None or not binding.time_witness_refs):
            missing_time.append(commit_id)
        if event.source_ref is None and (binding is None or not binding.evidence_refs):
            missing_evidence.append(commit_id)

        for state, version in ((source_state, source_version), (target_state, target_version)):
            value_presence, safe_terminal = semantics.get(state, (False, False))
            observed_points[(state, version)] = {
                "id": f"{state}@{version}",
                "state": state,
                "version": version,
                "valuePresence": value_presence,
                "safeTerminal": safe_terminal,
            }

        observed_transitions.append(
            {
                "commitId": commit_id,
                "source": f"{source_state}@{source_version}",
                "target": f"{target_state}@{target_version}",
                "operation": operation,
                "sourceRef": event.source_ref,
                "authorityRef": None if binding is None else binding.authority_ref,
                "evidenceRefs": [] if binding is None else list(binding.evidence_refs),
                "timeWitnessRefs": [] if binding is None else list(binding.time_witness_refs),
                "staticTemplateMatched": (source_state, operation, target_state) in allowed,
            }
        )

    conformance_status = "inconclusive" if committed_count == 0 else ("fail" if runtime_violations else "pass")
    binding_status = "pass"
    if missing_authority or missing_time or missing_evidence or committed_count == 0:
        binding_status = "inconclusive"

    economic_status = str(trace_result["economicCardinality"]["status"])
    successor_status = str(trace_result["successorConsistency"]["status"])
    required_runtime_complete = economic_status == "pass" and successor_status == "pass"

    fail = (
        static_status == "fail"
        or trace_result["status"] == "fail"
        or conformance_status == "fail"
    )
    if fail:
        overall = "fail"
    elif (
        static_status == "pass"
        and conformance_status == "pass"
        and binding_status == "pass"
        and required_runtime_complete
    ):
        overall = "pass"
    else:
        overall = "inconclusive"

    extraction = static_result.get("extraction")
    static_fingerprint = {
        "astSha256": extraction.get("astSha256") if isinstance(extraction, dict) else None,
        "profileSha256": extraction.get("profileSha256") if isinstance(extraction, dict) else None,
    }
    evidence_fingerprint = {
        **static_fingerprint,
        "traceSha256": execution_trace_sha256(trace),
        "bindingsSha256": hydration_bindings_sha256(bindings),
    }

    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": overall,
        "staticLifecycle": {
            "status": static_status,
            "verification": static_result.get("lifecycleVerification"),
        },
        "runtimeVerification": trace_result,
        "staticRuntimeConformance": {
            "status": conformance_status,
            "invariantId": STATIC_RUNTIME_INVARIANT,
            "committedTransitionCount": committed_count,
            "violations": runtime_violations,
        },
        "bindingVerification": {
            "status": binding_status,
            "invariantIds": [BINDING_INVARIANT, TIME_INVARIANT],
            "missingAuthorityCommitIds": sorted(set(missing_authority)),
            "missingTimeWitnessCommitIds": sorted(set(missing_time)),
            "missingEvidenceCommitIds": sorted(set(missing_evidence)),
        },
        "hydratedLattice": {
            "dimensions": ["state", "version", "valuePresence", "authority", "evidence", "timeWitness"],
            "observedPoints": sorted(observed_points.values(), key=lambda item: (int(item["version"]), str(item["state"]))),
            "observedTransitions": sorted(observed_transitions, key=lambda item: str(item["commitId"])),
            "valueSemantics": "presence_only_from_reviewed_static_profile; concrete amount not inferred",
        },
        "evidenceFingerprint": {
            **evidence_fingerprint,
            "assessmentSha256": _canonical_sha256(evidence_fingerprint),
        },
        "claimBoundary": (
            "PASS requires static lifecycle PASS, runtime economic-cardinality PASS, runtime successor-consistency PASS, "
            "runtime transitions conforming to the static lattice, unit version steps, and complete declared authority/time/evidence bindings. "
            "Raw provider/EVM capture completeness and semantic normalization remain independent provenance claims."
        ),
    }


def run_hydrated_lattice_files(
    static_result: Mapping[str, object],
    trace_path: Path,
    bindings_path: Path,
) -> dict[str, object]:
    return run_hydrated_lattice(
        static_result,
        load_execution_trace(trace_path),
        load_hydration_bindings(bindings_path),
    )
