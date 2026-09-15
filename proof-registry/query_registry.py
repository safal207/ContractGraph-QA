from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = "proof-registry/registry.v0.1.json"


def load_registry(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != "contractgraph.proof-registry.v0.1":
        raise SystemExit("unsupported registry schema")
    return data


def indexes(data: dict[str, Any]):
    nodes = {node["id"]: node for node in data["nodes"]}
    claim_owner: dict[str, str] = {}
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    consumers: dict[str, list[str]] = defaultdict(list)

    for node in data["nodes"]:
        for claim in node["claims"]:
            claim_owner[claim] = node["id"]

    for edge in data["edges"]:
        incoming[edge["to"]].append(edge)
        outgoing[edge["from"]].append(edge)
        for claim in edge["carries"]:
            consumers[claim].append(edge["to"])

    return nodes, claim_owner, incoming, outgoing, consumers


def upstream_nodes(start: str, incoming: dict[str, list[dict[str, Any]]]) -> list[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in incoming[current]:
            source = edge["from"]
            if source not in seen:
                seen.add(source)
                queue.append(source)
    return sorted(seen)


def downstream_nodes(start: str, outgoing: dict[str, list[dict[str, Any]]]) -> list[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in outgoing[current]:
            target = edge["to"]
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return sorted(seen)


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the ContractGraph proof registry")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--claim")
    group.add_argument("--node")
    args = parser.parse_args()

    data = load_registry(args.registry)
    nodes, claim_owner, incoming, outgoing, consumers = indexes(data)

    if args.claim:
        owner = claim_owner.get(args.claim)
        if owner is None:
            raise SystemExit(f"unknown claim: {args.claim}")
        result = {
            "claim": args.claim,
            "owner": owner,
            "owner_kind": nodes[owner]["kind"],
            "owner_artifact": nodes[owner]["artifact"],
            "claim_ceiling": nodes[owner]["claim_ceiling"],
            "direct_consumers": sorted(consumers.get(args.claim, [])),
            "upstream_of_owner": upstream_nodes(owner, incoming),
            "downstream_of_owner": downstream_nodes(owner, outgoing),
        }
    else:
        node_id = args.node
        if node_id not in nodes:
            raise SystemExit(f"unknown node: {node_id}")
        node = nodes[node_id]
        result = {
            "node": node_id,
            "kind": node["kind"],
            "artifact": node["artifact"],
            "claim_inputs": node["claim_inputs"],
            "claims": node["claims"],
            "non_claims": node["non_claims"],
            "claim_ceiling": node["claim_ceiling"],
            "direct_predecessors": sorted(edge["from"] for edge in incoming[node_id]),
            "direct_successors": sorted(edge["to"] for edge in outgoing[node_id]),
            "all_upstream": upstream_nodes(node_id, incoming),
            "all_downstream": downstream_nodes(node_id, outgoing),
        }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
