from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCHEMA = "contractgraph.proof-registry.v0.1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_KINDS = {
    "external_admission",
    "framework_neutral_contract",
    "runtime_proof",
    "cross_runtime_profile",
}


class RegistryError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise RegistryError(message)


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        fail(
            f"git {' '.join(args)} failed: "
            f"{proc.stderr.strip() or proc.stdout.strip() or 'unknown error'}"
        )
    return proc.stdout.strip()


def expect_string_list(value: Any, where: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        fail(f"{where} must be a list of non-empty strings")
    if not allow_empty and not value:
        fail(f"{where} must not be empty")
    if len(value) != len(set(value)):
        fail(f"{where} contains duplicates")
    return value


def verify_artifact(node_id: str, artifact: Any) -> dict[str, str]:
    if not isinstance(artifact, dict):
        fail(f"node {node_id}: artifact must be an object")

    required = {"merge_commit", "path", "blob_sha"}
    if set(artifact) != required:
        fail(f"node {node_id}: artifact keys must be exactly {sorted(required)}")

    commit = artifact["merge_commit"]
    path = artifact["path"]
    blob_sha = artifact["blob_sha"]
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        fail(f"node {node_id}: merge_commit must be a 40-char lowercase SHA")
    if not isinstance(blob_sha, str) or not HEX40.fullmatch(blob_sha):
        fail(f"node {node_id}: blob_sha must be a 40-char lowercase SHA")
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
        fail(f"node {node_id}: artifact path must be a safe repository-relative path")

    git("cat-file", "-e", f"{commit}^{{commit}}")
    actual_blob = git("rev-parse", f"{commit}:{path}")
    if actual_blob != blob_sha:
        fail(
            f"node {node_id}: immutable blob mismatch for {commit}:{path}; "
            f"expected {blob_sha}, got {actual_blob}"
        )

    raw = git("show", f"{commit}:{path}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"node {node_id}: historical artifact is not valid JSON: {exc}")
    if not isinstance(parsed, dict):
        fail(f"node {node_id}: historical artifact must be a JSON object")

    return {"merge_commit": commit, "path": path, "blob_sha": blob_sha}


def verify_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        fail("registry root must be an object")
    if data.get("schema") != SCHEMA:
        fail(f"registry schema must be {SCHEMA}")
    if not isinstance(data.get("title"), str) or not data["title"]:
        fail("registry title is required")
    if not isinstance(data.get("principle"), str) or not data["principle"]:
        fail("registry principle is required")

    nodes_raw = data.get("nodes")
    edges_raw = data.get("edges")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        fail("nodes must be a non-empty list")
    if not isinstance(edges_raw, list):
        fail("edges must be a list")

    nodes: dict[str, dict[str, Any]] = {}
    claim_owner: dict[str, str] = {}
    verified_artifacts: list[dict[str, str]] = []

    for index, node in enumerate(nodes_raw):
        if not isinstance(node, dict):
            fail(f"nodes[{index}] must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            fail(f"nodes[{index}].id must be a non-empty string")
        if node_id in nodes:
            fail(f"duplicate node id: {node_id}")
        if node.get("kind") not in ALLOWED_KINDS:
            fail(f"node {node_id}: unsupported kind {node.get('kind')!r}")
        if node.get("status") != "frozen":
            fail(f"node {node_id}: v0.1 registry accepts only frozen nodes")

        claims = expect_string_list(node.get("claims"), f"node {node_id}.claims", allow_empty=False)
        inputs = expect_string_list(node.get("claim_inputs"), f"node {node_id}.claim_inputs")
        non_claims = expect_string_list(
            node.get("non_claims"), f"node {node_id}.non_claims", allow_empty=False
        )
        if set(claims) & set(inputs):
            fail(f"node {node_id}: own claims and claim_inputs must be disjoint")
        ceiling = node.get("claim_ceiling")
        if not isinstance(ceiling, str) or not ceiling.strip():
            fail(f"node {node_id}: claim_ceiling is required")

        for claim in claims:
            previous = claim_owner.get(claim)
            if previous is not None:
                fail(f"claim {claim!r} is owned by both {previous} and {node_id}")
            claim_owner[claim] = node_id

        artifact = verify_artifact(node_id, node.get("artifact"))
        verified_artifacts.append({"node": node_id, **artifact})
        nodes[node_id] = node

    edges_seen: set[str] = set()
    incoming_claims: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {node_id: 0 for node_id in nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for index, edge in enumerate(edges_raw):
        if not isinstance(edge, dict):
            fail(f"edges[{index}] must be an object")
        edge_id = edge.get("id")
        source = edge.get("from")
        target = edge.get("to")
        relation = edge.get("relation")
        if not isinstance(edge_id, str) or not edge_id:
            fail(f"edges[{index}].id must be a non-empty string")
        if edge_id in edges_seen:
            fail(f"duplicate edge id: {edge_id}")
        edges_seen.add(edge_id)
        if source not in nodes or target not in nodes:
            fail(f"edge {edge_id}: unknown source or target")
        if source == target:
            fail(f"edge {edge_id}: self edges are not allowed")
        if not isinstance(relation, str) or not relation:
            fail(f"edge {edge_id}: relation is required")

        carries = expect_string_list(edge.get("carries"), f"edge {edge_id}.carries", allow_empty=False)
        source_claims = set(nodes[source]["claims"])
        target_inputs = set(nodes[target]["claim_inputs"])
        unknown_source = set(carries) - source_claims
        if unknown_source:
            fail(
                f"edge {edge_id}: attempts to carry claims not owned by {source}: "
                f"{sorted(unknown_source)}"
            )
        undeclared_target = set(carries) - target_inputs
        if undeclared_target:
            fail(
                f"edge {edge_id}: target {target} did not declare carried claims as inputs: "
                f"{sorted(undeclared_target)}"
            )

        overlap = incoming_claims[target] & set(carries)
        if overlap:
            fail(f"edge {edge_id}: target {target} receives duplicate claim inputs {sorted(overlap)}")
        incoming_claims[target].update(carries)
        adjacency[source].append(target)
        indegree[target] += 1

    for node_id, node in nodes.items():
        expected = set(node["claim_inputs"])
        received = incoming_claims[node_id]
        if expected != received:
            missing = sorted(expected - received)
            extra = sorted(received - expected)
            fail(
                f"node {node_id}: claim handoff mismatch; missing={missing}, extra={extra}"
            )

    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    work_degree = dict(indegree)
    while queue:
        node_id = queue.popleft()
        visited.append(node_id)
        for target in adjacency[node_id]:
            work_degree[target] -= 1
            if work_degree[target] == 0:
                queue.append(target)

    if len(visited) != len(nodes):
        cyclic = sorted(node_id for node_id, degree in work_degree.items() if degree > 0)
        fail(f"proof registry must be acyclic; cycle involves {cyclic}")

    roots = sorted(node_id for node_id in nodes if indegree[node_id] == 0)
    leaves = sorted(node_id for node_id in nodes if not adjacency[node_id])
    return {
        "schema": SCHEMA,
        "verified": True,
        "nodes": len(nodes),
        "edges": len(edges_raw),
        "claims": len(claim_owner),
        "roots": roots,
        "leaves": leaves,
        "topological_order": visited,
        "immutable_artifacts": verified_artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry",
        nargs="?",
        default="proof-registry/registry.v0.1.json",
    )
    parser.add_argument("--write-summary")
    args = parser.parse_args()

    try:
        summary = verify_registry(Path(args.registry))
    except (RegistryError, json.JSONDecodeError, OSError) as exc:
        print(f"PROOF_REGISTRY_FAIL: {exc}")
        return 1

    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print("PROOF_REGISTRY_PASS")
    print(rendered, end="")
    if args.write_summary:
        Path(args.write_summary).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
