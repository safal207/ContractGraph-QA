"""Machine-readable NEO REZONANS system-snapshot validation.

The snapshot binds exact canonical repository revisions and, more importantly,
what facts may and may not cross each repository boundary. It is a point-in-time
system contract, not a claim that pinned `main` heads remain current forever.

Because the snapshot is hosted inside one of its own component repositories,
the host is bound to the exact pre-acceptance capability base. The governance
merge that introduces the snapshot is explicitly not treated as semantic layer
drift; later host changes still require revalidation.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SYSTEM_SNAPSHOT_SCHEMA = "cgqa.neo-rezonans-system-snapshot.v0.1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_AUTHORITY_MODES = {"NONE", "EXPLICIT_CONTRACT_ONLY"}
_REQUIRED_ROLES = {
    "INTENT_OBSERVATORY",
    "CAUSAL_MEMORY",
    "CAUSAL_NAVIGATION",
    "AUTHORIZATION_GOVERNANCE",
    "STATE_TRANSITION_VERIFICATION",
    "PROOF_PROVENANCE",
    "DURABLE_VERIFIED_STATE",
    "REINTERPRETATION",
}


class SystemSnapshotError(ValueError):
    """Raised when the NEO REZONANS snapshot violates the system contract."""


def _object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemSnapshotError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise SystemSnapshotError(f"{field} must be an array")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemSnapshotError(f"{field} must be a non-empty string")
    return value.strip()


def _bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise SystemSnapshotError(f"{field} must be a boolean")
    return value


def _text_list(value: object, field: str, *, non_empty: bool = False) -> list[str]:
    raw = _list(value, field)
    values = [_text(item, f"{field}[{index}]") for index, item in enumerate(raw)]
    if non_empty and not values:
        raise SystemSnapshotError(f"{field} must not be empty")
    if len(values) != len(set(values)):
        raise SystemSnapshotError(f"{field} must not contain duplicates")
    return values


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(snapshot)).hexdigest()


def validate_system_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    snapshot = _object(snapshot, "snapshot")
    if snapshot.get("schema") != SYSTEM_SNAPSHOT_SCHEMA:
        raise SystemSnapshotError(f"snapshot.schema must be {SYSTEM_SNAPSHOT_SCHEMA}")

    snapshot_id = _text(snapshot.get("snapshotId"), "snapshot.snapshotId")
    _text(snapshot.get("observedAt"), "snapshot.observedAt")

    idea = _object(snapshot.get("ideaContract"), "snapshot.ideaContract")
    _text(idea.get("purpose"), "snapshot.ideaContract.purpose")
    _text(idea.get("expectedOutcome"), "snapshot.ideaContract.expectedOutcome")
    _text_list(idea.get("invariants"), "snapshot.ideaContract.invariants", non_empty=True)
    _text_list(
        idea.get("forbiddenOutcomes"),
        "snapshot.ideaContract.forbiddenOutcomes",
        non_empty=True,
    )

    policy = _object(snapshot.get("snapshotPolicy"), "snapshot.snapshotPolicy")
    if not _bool(
        policy.get("mainHeadMustMatchAtAcceptance"),
        "snapshot.snapshotPolicy.mainHeadMustMatchAtAcceptance",
    ):
        raise SystemSnapshotError(
            "system acceptance must verify external main heads and the host pre-acceptance base"
        )
    host_repo = _text(policy.get("hostRepository"), "snapshot.snapshotPolicy.hostRepository")
    host_base = _text(policy.get("hostBaseCommit"), "snapshot.snapshotPolicy.hostBaseCommit")
    if not _REPOSITORY.fullmatch(host_repo):
        raise SystemSnapshotError("snapshotPolicy.hostRepository has invalid format")
    if not _SHA40.fullmatch(host_base):
        raise SystemSnapshotError("snapshotPolicy.hostBaseCommit must be a full lowercase SHA")
    if _text(
        policy.get("hostAcceptanceMode"),
        "snapshot.snapshotPolicy.hostAcceptanceMode",
    ) != "BASE_PLUS_GOVERNANCE_SNAPSHOT":
        raise SystemSnapshotError(
            "snapshotPolicy.hostAcceptanceMode must be BASE_PLUS_GOVERNANCE_SNAPSHOT"
        )
    if not _bool(
        policy.get("hostAcceptanceDoesNotCountAsDrift"),
        "snapshot.snapshotPolicy.hostAcceptanceDoesNotCountAsDrift",
    ):
        raise SystemSnapshotError(
            "the declared host acceptance commit must be distinguished from later semantic drift"
        )
    if _text(
        policy.get("onHeadDrift"),
        "snapshot.snapshotPolicy.onHeadDrift",
    ) != "REVALIDATE_SYSTEM_SNAPSHOT":
        raise SystemSnapshotError(
            "snapshotPolicy.onHeadDrift must be REVALIDATE_SYSTEM_SNAPSHOT"
        )
    if _bool(
        policy.get("branchOnlyDefaultDependenciesAllowed"),
        "snapshot.snapshotPolicy.branchOnlyDefaultDependenciesAllowed",
    ):
        raise SystemSnapshotError("branch-only work may not become a default system dependency")

    engine = _object(snapshot.get("fcrpEngine"), "snapshot.fcrpEngine")
    if _text(engine.get("protocolSchema"), "snapshot.fcrpEngine.protocolSchema") != "cgqa.fcrp-case.v0.2":
        raise SystemSnapshotError("system snapshot must be evaluated against FCRP v0.2")
    engine_repo = _text(engine.get("repository"), "snapshot.fcrpEngine.repository")
    engine_commit = _text(engine.get("canonicalCommit"), "snapshot.fcrpEngine.canonicalCommit")
    if not _REPOSITORY.fullmatch(engine_repo):
        raise SystemSnapshotError("snapshot.fcrpEngine.repository has invalid format")
    if not _SHA40.fullmatch(engine_commit):
        raise SystemSnapshotError("snapshot.fcrpEngine.canonicalCommit must be a full lowercase SHA")
    if host_repo != engine_repo or host_base != engine_commit:
        raise SystemSnapshotError(
            "self-hosted snapshot must bind the host base to the canonical FCRP engine revision"
        )

    layers_raw = _list(snapshot.get("layers"), "snapshot.layers")
    if not layers_raw:
        raise SystemSnapshotError("snapshot.layers must not be empty")

    layers: dict[str, dict[str, Any]] = {}
    roles: set[str] = set()
    repository_commits: dict[str, str] = {}
    repositories_and_commits: set[tuple[str, str]] = set()
    host_layers = 0
    for index, item in enumerate(layers_raw):
        layer = _object(item, f"snapshot.layers[{index}]")
        layer_id = _text(layer.get("id"), f"snapshot.layers[{index}].id")
        if layer_id in layers:
            raise SystemSnapshotError(f"duplicate layer id {layer_id}")
        role = _text(layer.get("role"), f"snapshot.layers[{index}].role")
        repository = _text(layer.get("repository"), f"snapshot.layers[{index}].repository")
        commit = _text(layer.get("canonicalCommit"), f"snapshot.layers[{index}].canonicalCommit")
        _text(layer.get("capability"), f"snapshot.layers[{index}].capability")
        if not _REPOSITORY.fullmatch(repository):
            raise SystemSnapshotError(f"layer {layer_id} repository has invalid format")
        if not _SHA40.fullmatch(commit):
            raise SystemSnapshotError(f"layer {layer_id} canonicalCommit must be a full lowercase SHA")
        prior_commit = repository_commits.get(repository)
        if prior_commit is not None and prior_commit != commit:
            raise SystemSnapshotError(
                f"repository {repository} cannot be bound to multiple commits in one system snapshot"
            )
        repository_commits[repository] = commit
        if layer.get("status") != "CANONICAL":
            raise SystemSnapshotError(f"layer {layer_id} must be CANONICAL")
        if not _bool(layer.get("defaultConsumerAllowed"), f"snapshot.layers[{index}].defaultConsumerAllowed"):
            raise SystemSnapshotError(f"layer {layer_id} must be default-consumer eligible")
        if repository == host_repo:
            host_layers += 1
            if commit != host_base:
                raise SystemSnapshotError(
                    f"host layer {layer_id} must bind the exact pre-acceptance host base"
                )
        layers[layer_id] = layer
        roles.add(role)
        repositories_and_commits.add((repository, commit))

    if host_layers < 1:
        raise SystemSnapshotError("system snapshot must contain at least one host-repository layer")

    missing_roles = sorted(_REQUIRED_ROLES - roles)
    if missing_roles:
        raise SystemSnapshotError(f"missing required system roles: {missing_roles}")

    if (engine_repo, engine_commit) not in repositories_and_commits:
        raise SystemSnapshotError("FCRP engine identity must be one of the canonical system layers")

    chain = _text_list(snapshot.get("primaryChain"), "snapshot.primaryChain", non_empty=True)
    if len(chain) != len(set(chain)):
        raise SystemSnapshotError("snapshot.primaryChain must not repeat layers")
    unknown_chain = [layer_id for layer_id in chain if layer_id not in layers]
    if unknown_chain:
        raise SystemSnapshotError(f"snapshot.primaryChain references unknown layers {unknown_chain}")
    if set(chain) != set(layers):
        raise SystemSnapshotError("snapshot.primaryChain must contain every system layer exactly once")

    edges_raw = _list(snapshot.get("edges"), "snapshot.edges")
    if len(edges_raw) != len(chain):
        raise SystemSnapshotError("snapshot.edges must contain the full primary chain plus one feedback edge")

    edge_pairs: set[tuple[str, str]] = set()
    explicit_authority_edges = 0
    feedback_edges = 0
    expected_feedback_pair = (chain[-1], chain[0])
    for index, item in enumerate(edges_raw):
        edge = _object(item, f"snapshot.edges[{index}]")
        source = _text(edge.get("from"), f"snapshot.edges[{index}].from")
        target = _text(edge.get("to"), f"snapshot.edges[{index}].to")
        if source not in layers or target not in layers:
            raise SystemSnapshotError(f"edge {source}->{target} references unknown layer")
        pair = (source, target)
        if pair in edge_pairs:
            raise SystemSnapshotError(f"duplicate edge {source}->{target}")
        edge_pairs.add(pair)
        allowed = _text_list(
            edge.get("allowedFacts"),
            f"snapshot.edges[{index}].allowedFacts",
            non_empty=True,
        )
        forbidden = _text_list(
            edge.get("forbiddenInferences"),
            f"snapshot.edges[{index}].forbiddenInferences",
            non_empty=True,
        )
        if set(allowed) & set(forbidden):
            raise SystemSnapshotError(f"edge {source}->{target} allows and forbids the same semantic item")
        authority_mode = _text(
            edge.get("authorityMode"),
            f"snapshot.edges[{index}].authorityMode",
        )
        if authority_mode not in _AUTHORITY_MODES:
            raise SystemSnapshotError(f"edge {source}->{target} has unsupported authorityMode")
        if authority_mode == "EXPLICIT_CONTRACT_ONLY":
            explicit_authority_edges += 1
            if layers[source]["role"] != "AUTHORIZATION_GOVERNANCE" or layers[target]["role"] != "STATE_TRANSITION_VERIFICATION":
                raise SystemSnapshotError(
                    "explicit authority may flow only from AUTHORIZATION_GOVERNANCE to STATE_TRANSITION_VERIFICATION"
                )
            if "authorization_ref" not in allowed:
                raise SystemSnapshotError(
                    f"authority edge {source}->{target} must transfer authorization_ref explicitly"
                )
            if "evidence_as_authority" not in forbidden:
                raise SystemSnapshotError(
                    f"authority edge {source}->{target} must forbid evidence_as_authority"
                )
        else:
            if "authorization_ref" in allowed:
                raise SystemSnapshotError(
                    f"non-authority edge {source}->{target} may not transfer authorization_ref"
                )
            if "execution_authority" not in forbidden:
                raise SystemSnapshotError(
                    f"non-authority edge {source}->{target} must explicitly forbid execution_authority"
                )
        feedback = _bool(edge.get("feedback"), f"snapshot.edges[{index}].feedback")
        if feedback:
            feedback_edges += 1
            if pair != expected_feedback_pair:
                raise SystemSnapshotError(
                    "feedback may close only the REINTERPRETATION to INTENT_OBSERVATORY system edge"
                )
            if layers[source]["role"] != "REINTERPRETATION" or layers[target]["role"] != "INTENT_OBSERVATORY":
                raise SystemSnapshotError(
                    "feedback edge roles must be REINTERPRETATION to INTENT_OBSERVATORY"
                )

    expected_primary_pairs = set(zip(chain, chain[1:]))
    missing_primary = sorted(expected_primary_pairs - edge_pairs)
    if missing_primary:
        raise SystemSnapshotError(f"missing primary-chain edges: {missing_primary}")
    if expected_feedback_pair not in edge_pairs:
        raise SystemSnapshotError("system snapshot must close the RINSE-to-RESONANCE feedback loop")
    if explicit_authority_edges != 1:
        raise SystemSnapshotError("system snapshot must contain exactly one authority-transfer edge")
    if feedback_edges != 1:
        raise SystemSnapshotError("system snapshot must contain exactly one declared feedback edge")

    authority = _object(snapshot.get("authorityBoundary"), "snapshot.authorityBoundary")
    if _bool(
        authority.get("snapshotGrantsMutationAuthority"),
        "snapshot.authorityBoundary.snapshotGrantsMutationAuthority",
    ):
        raise SystemSnapshotError("a system snapshot may not itself grant mutation authority")
    if _bool(
        authority.get("evidenceMayGrantAuthority"),
        "snapshot.authorityBoundary.evidenceMayGrantAuthority",
    ):
        raise SystemSnapshotError("evidence may not grant authority at the system boundary")
    _text(authority.get("statement"), "snapshot.authorityBoundary.statement")

    return {
        "schema": "cgqa.neo-rezonans-system-snapshot-result.v0.1",
        "snapshotId": snapshot_id,
        "decision": "PASS",
        "snapshotDigest": snapshot_digest(snapshot),
        "layerCount": len(layers),
        "repositoryCount": len(repository_commits),
        "edgeCount": len(edge_pairs),
        "authorityTransferEdges": explicit_authority_edges,
        "feedbackEdges": feedback_edges,
        "fcrpEngineCommit": engine_commit,
        "hostRepository": host_repo,
        "hostBaseCommit": host_base,
        "hostAcceptanceMode": "BASE_PLUS_GOVERNANCE_SNAPSHOT",
    }
