#!/usr/bin/env python3
"""Guarded automatic path-to-finding search for Temporal Transition Field v0.6.

v0.6 adds a fail-closed adapter contract in front of the v0.5 guarded BFS.
When an adapter manifest is supplied, authorization, non-production scope,
model-event coverage, search bounds, snapshot shape, and evidence shape are
validated before/while adapter actions execute.

The engine itself performs no network activity. Real target interaction must
live behind a separately reviewed adapter and a validated manifest.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any, Callable, Protocol

from adapter_contract import (
    ContractBoundAdapter,
    evidence_scope,
    enforce_search_bounds,
    validate_manifest,
    validate_model_coverage,
)
from build_evidence_graph import build_dot, build_markdown, record_digest
from detect_forbidden_state import detect
from generate_paths import SPEC, parse_transitions
from guard_engine import evaluate_transition_guards
from synthetic_adapter import SyntheticBuggyAdapter, SyntheticSafeAdapter


class TransitionAdapter(Protocol):
    def snapshot(self) -> dict[str, Any]: ...
    def apply(self, event: str) -> dict[str, Any]: ...


AdapterFactory = Callable[[], TransitionAdapter]


def _make_record(
    *,
    path_index: int,
    step_index: int,
    transition: tuple[str, str, str],
    pre_state: dict[str, Any],
    observation: dict[str, Any],
    post_state: dict[str, Any],
    guard_result: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    expected_from, event, expected_to = transition
    return {
        "schema_version": "0.2",
        "run_id": f"path-{path_index:04d}",
        "scenario_id": f"PATH-{path_index:04d}-STEP-{step_index:02d}",
        "scope": scope,
        "model_transition": {
            "expected_from": expected_from,
            "event": event,
            "expected_to": expected_to,
        },
        "guard": guard_result,
        "pre_state": pre_state,
        "request": observation["request"],
        "decision": observation["decision"],
        "mutation": observation["mutation"],
        "post_state": post_state,
        "evidence": observation["evidence"],
        "invariants": [],
        "verdict": {
            "state": "inconclusive",
            "forbidden_state_reached": False,
            "finding_id": None,
            "summary": "Pending forbidden-state evaluation.",
        },
    }


def _apply_detection(record: dict[str, Any], detector_result: dict[str, Any]) -> dict[str, Any]:
    enriched = json.loads(json.dumps(record))
    enriched["invariants"] = [
        {
            "id": item["id"],
            "rule": item.get("description") or item["id"],
            "verdict": (
                "pass"
                if item["status"] in {"pass", "not_applicable"}
                else "fail"
                if item["status"] == "fail"
                else "inconclusive"
            ),
            "observed": json.dumps(item.get("assertion"), sort_keys=True),
        }
        for item in detector_result["evaluations"]
    ]

    if detector_result["overall"] == "violated":
        finding = detector_result["finding"]
        enriched["verdict"] = {
            "state": "fail",
            "forbidden_state_reached": True,
            "finding_id": finding["finding_id"],
            "summary": finding["summary"],
        }
    elif detector_result["overall"] == "inconclusive":
        enriched["verdict"] = {
            "state": "inconclusive",
            "forbidden_state_reached": False,
            "finding_id": None,
            "summary": "Required evidence was missing or not comparable.",
        }
    else:
        enriched["verdict"] = {
            "state": "pass",
            "forbidden_state_reached": False,
            "finding_id": None,
            "summary": "No forbidden state found in this observed transition.",
        }
    enriched["detector"] = detector_result
    return enriched


def _model_state_check(
    transition: tuple[str, str, str],
    pre_state: dict[str, Any],
    post_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    expected_from, event, expected_to = transition
    if pre_state.get("state_id") != expected_from:
        return {
            "kind": "model_pre_state_mismatch",
            "event": event,
            "expected": expected_from,
            "observed": pre_state.get("state_id"),
        }
    if post_state is not None and post_state.get("state_id") != expected_to:
        return {
            "kind": "model_post_state_mismatch",
            "event": event,
            "expected": expected_to,
            "observed": post_state.get("state_id"),
        }
    return None


def _load_transitions_and_graph() -> tuple[list[tuple[str, str, str]], dict[str, list[tuple[str, str, str]]]]:
    transitions = parse_transitions(SPEC.read_text(encoding="utf-8"))
    graph: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for src, event, dst in transitions:
        graph[src].append((src, event, dst))
    return transitions, graph


def _replay_candidate(
    adapter_factory: AdapterFactory,
    path: list[tuple[str, str, str]],
    rules_document: dict[str, Any],
    guards_document: dict[str, Any] | None,
    adapter_manifest: dict[str, Any] | None,
    *,
    path_index: int,
) -> dict[str, Any]:
    raw_adapter = adapter_factory()
    adapter: TransitionAdapter = (
        ContractBoundAdapter(raw_adapter, adapter_manifest)
        if adapter_manifest is not None
        else raw_adapter
    )
    scope = (
        evidence_scope(adapter_manifest)
        if adapter_manifest is not None
        else {
            "environment": "local",
            "authorized": True,
            "target": "temporal-transition-field-adapter",
            "notes": "Guarded bounded path exploration; adapter controls target interaction.",
        }
    )

    records: list[dict[str, Any]] = []
    guard_counts = {"checks": 0, "allowed": 0, "blocked": 0, "inconclusive": 0}

    for step_index, transition in enumerate(path, 1):
        pre_state = adapter.snapshot()
        pre_mismatch = _model_state_check(transition, pre_state)
        if pre_mismatch is not None:
            return {
                "status": "inconclusive",
                "records": records,
                "reason": pre_mismatch,
                "guard_counts": guard_counts,
            }

        guard_result = evaluate_transition_guards(pre_state, transition, guards_document)
        guard_counts["checks"] += 1
        guard_counts[guard_result["status"]] += 1

        if guard_result["status"] == "blocked":
            return {
                "status": "guard_blocked",
                "records": records,
                "guard": guard_result,
                "transition": transition,
                "step_index": step_index,
                "guard_counts": guard_counts,
            }
        if guard_result["status"] == "inconclusive":
            return {
                "status": "inconclusive",
                "records": records,
                "reason": {
                    "kind": "guard_inconclusive",
                    "transition": transition,
                    "guard": guard_result,
                },
                "guard_counts": guard_counts,
            }

        observation = adapter.apply(transition[1])
        post_state = adapter.snapshot()
        post_mismatch = _model_state_check(transition, pre_state, post_state)
        record = _make_record(
            path_index=path_index,
            step_index=step_index,
            transition=transition,
            pre_state=pre_state,
            observation=observation,
            post_state=post_state,
            guard_result=guard_result,
            scope=scope,
        )

        if post_mismatch is not None:
            record["verdict"] = {
                "state": "inconclusive",
                "forbidden_state_reached": False,
                "finding_id": None,
                "summary": "Observed adapter state diverged from the declared transition model.",
            }
            record["model_mismatch"] = post_mismatch
            records.append(record)
            return {
                "status": "inconclusive",
                "records": records,
                "reason": post_mismatch,
                "guard_counts": guard_counts,
            }

        detector_result = detect(record, rules_document)
        record = _apply_detection(record, detector_result)
        records.append(record)

        if detector_result["overall"] == "violated":
            return {
                "status": "violated",
                "records": records,
                "violating_step": step_index,
                "finding": detector_result["finding"],
                "guard_counts": guard_counts,
            }
        if detector_result["overall"] == "inconclusive":
            return {
                "status": "inconclusive",
                "records": records,
                "reason": {"kind": "detector_inconclusive", "step_index": step_index},
                "guard_counts": guard_counts,
            }

    return {"status": "complete", "records": records, "guard_counts": guard_counts}


def _add_counts(total: dict[str, int], current: dict[str, int]) -> None:
    for key, value in current.items():
        total[key] += value


def search_paths(
    adapter_factory: AdapterFactory,
    rules_document: dict[str, Any],
    *,
    guards_document: dict[str, Any] | None = None,
    adapter_manifest: dict[str, Any] | None = None,
    max_depth: int = 6,
    max_paths: int = 250,
) -> dict[str, Any]:
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_paths < 1:
        raise ValueError("max_paths must be >= 1")

    transitions, graph = _load_transitions_and_graph()
    if adapter_manifest is not None:
        validate_manifest(adapter_manifest)
        enforce_search_bounds(adapter_manifest, max_depth=max_depth, max_paths=max_paths)
        validate_model_coverage(adapter_manifest, transitions)

    queue: deque[list[tuple[str, str, str]]] = deque(
        [[transition] for transition in graph.get("Q0_RESET", [])]
    )
    saw_inconclusive = False
    explored = 0
    pruned = 0
    guard_counts = {"checks": 0, "allowed": 0, "blocked": 0, "inconclusive": 0}

    while queue and explored < max_paths:
        path = queue.popleft()
        explored += 1
        replay = _replay_candidate(
            adapter_factory,
            path,
            rules_document,
            guards_document,
            adapter_manifest,
            path_index=explored,
        )
        _add_counts(guard_counts, replay["guard_counts"])

        if replay["status"] == "violated":
            return {
                "schema_version": "0.6",
                "overall": "violated",
                "search_semantics": "contract_bound_guarded_breadth_first_shortest_path_within_bound",
                "guards_enabled": guards_document is not None,
                "adapter_contract_enabled": adapter_manifest is not None,
                "adapter_id": adapter_manifest.get("adapter_id") if adapter_manifest else None,
                "max_depth": max_depth,
                "max_paths": max_paths,
                "paths_explored": explored,
                "paths_pruned_by_guard": pruned,
                "guard_stats": guard_counts,
                "minimal_path": [
                    {"from": src, "event": event, "to": dst} for src, event, dst in path
                ],
                "violating_step": replay["violating_step"],
                "records": replay["records"],
                "finding": replay["finding"],
            }

        if replay["status"] == "guard_blocked":
            pruned += 1
            continue
        if replay["status"] == "inconclusive":
            saw_inconclusive = True
            continue

        if len(path) < max_depth:
            current_state = path[-1][2]
            for transition in graph.get(current_state, []):
                queue.append(path + [transition])

    return {
        "schema_version": "0.6",
        "overall": "inconclusive" if saw_inconclusive else "not_found_within_bound",
        "search_semantics": "contract_bound_guarded_breadth_first_shortest_path_within_bound",
        "guards_enabled": guards_document is not None,
        "adapter_contract_enabled": adapter_manifest is not None,
        "adapter_id": adapter_manifest.get("adapter_id") if adapter_manifest else None,
        "max_depth": max_depth,
        "max_paths": max_paths,
        "paths_explored": explored,
        "paths_pruned_by_guard": pruned,
        "guard_stats": guard_counts,
        "minimal_path": None,
        "violating_step": None,
        "records": [],
        "finding": None,
    }


def write_result(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "search_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if result["overall"] != "violated":
        return

    records_dir = out_dir / "evidence_records"
    records_dir.mkdir(exist_ok=True)
    for index, record in enumerate(result["records"], 1):
        (records_dir / f"step-{index:02d}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    violating_record = result["records"][result["violating_step"] - 1]
    graph_dir = out_dir / "violating_evidence_graph"
    graph_dir.mkdir(exist_ok=True)
    (graph_dir / "evidence.dot").write_text(build_dot(violating_record), encoding="utf-8")
    (graph_dir / "evidence.md").write_text(build_markdown(violating_record), encoding="utf-8")
    (graph_dir / "record.sha256").write_text(record_digest(violating_record) + "\n", encoding="utf-8")

    (out_dir / "minimal_path.json").write_text(
        json.dumps(result["minimal_path"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "finding.json").write_text(
        json.dumps(result["finding"], indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=here / "forbidden_state_rules.example.json")
    parser.add_argument("--guards", type=Path, default=here / "transition_guards.example.json")
    parser.add_argument("--no-guards", action="store_true")
    parser.add_argument("--adapter-manifest", type=Path, default=here / "adapter_manifest.synthetic.json")
    parser.add_argument("--no-adapter-contract", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("path-to-finding"))
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-paths", type=int, default=250)
    parser.add_argument(
        "--adapter",
        choices=["synthetic-buggy", "synthetic-safe"],
        default="synthetic-buggy",
        help="Bundled offline adapter. Real integrations must be supplied programmatically behind a reviewed manifest.",
    )
    args = parser.parse_args()

    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    guards = None if args.no_guards else json.loads(args.guards.read_text(encoding="utf-8"))
    manifest = None if args.no_adapter_contract else json.loads(args.adapter_manifest.read_text(encoding="utf-8"))
    factory: AdapterFactory = SyntheticBuggyAdapter if args.adapter == "synthetic-buggy" else SyntheticSafeAdapter
    result = search_paths(
        factory,
        rules,
        guards_document=guards,
        adapter_manifest=manifest,
        max_depth=args.max_depth,
        max_paths=args.max_paths,
    )
    write_result(result, args.out_dir)
    print(
        json.dumps(
            {
                "overall": result["overall"],
                "adapter_contract_enabled": result["adapter_contract_enabled"],
                "adapter_id": result["adapter_id"],
                "paths_explored": result["paths_explored"],
                "paths_pruned_by_guard": result["paths_pruned_by_guard"],
                "guard_stats": result["guard_stats"],
                "violating_step": result["violating_step"],
                "finding_id": result["finding"]["finding_id"] if result["finding"] else None,
            },
            indent=2,
        )
    )
    return 1 if result["overall"] == "violated" else 2 if result["overall"] == "inconclusive" else 0


if __name__ == "__main__":
    raise SystemExit(main())
