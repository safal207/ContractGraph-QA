#!/usr/bin/env python3
"""Automatic bounded path-to-finding search for Temporal Transition Field v0.4.

The engine explores model paths in breadth-first order. Each path is replayed
from an isolated adapter instance, every transition is captured as an evidence
record, and the v0.3 forbidden-state detector evaluates the observed post-state.
The first violated path is therefore a shortest path within the configured bound.

This module performs no network activity by itself. Real target interaction must
live behind an explicitly authorized adapter. The bundled CLI uses only the
in-memory synthetic adapters.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Protocol

from build_evidence_graph import build_dot, build_markdown, record_digest
from detect_forbidden_state import detect
from generate_paths import generate_paths
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
) -> dict[str, Any]:
    expected_from, event, expected_to = transition
    return {
        "schema_version": "0.2",
        "run_id": f"path-{path_index:04d}",
        "scenario_id": f"PATH-{path_index:04d}-STEP-{step_index:02d}",
        "scope": {
            "environment": "local",
            "authorized": True,
            "target": "temporal-transition-field-adapter",
            "notes": "Bounded path exploration; adapter controls target interaction.",
        },
        "model_transition": {
            "expected_from": expected_from,
            "event": event,
            "expected_to": expected_to,
        },
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
    transition: tuple[str, str, str], pre_state: dict[str, Any], post_state: dict[str, Any]
) -> dict[str, Any] | None:
    expected_from, event, expected_to = transition
    if pre_state.get("state_id") != expected_from:
        return {
            "kind": "model_pre_state_mismatch",
            "event": event,
            "expected": expected_from,
            "observed": pre_state.get("state_id"),
        }
    if post_state.get("state_id") != expected_to:
        return {
            "kind": "model_post_state_mismatch",
            "event": event,
            "expected": expected_to,
            "observed": post_state.get("state_id"),
        }
    return None


def search_paths(
    adapter_factory: AdapterFactory,
    rules_document: dict[str, Any],
    *,
    max_depth: int = 6,
    max_paths: int = 250,
) -> dict[str, Any]:
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_paths < 1:
        raise ValueError("max_paths must be >= 1")

    candidate_paths = generate_paths(max_depth=max_depth)[:max_paths]
    saw_inconclusive = False
    explored = 0

    for path_index, path in enumerate(candidate_paths, 1):
        explored += 1
        adapter = adapter_factory()
        path_records: list[dict[str, Any]] = []

        for step_index, transition in enumerate(path, 1):
            pre_state = adapter.snapshot()
            observation = adapter.apply(transition[1])
            post_state = adapter.snapshot()

            model_mismatch = _model_state_check(transition, pre_state, post_state)
            record = _make_record(
                path_index=path_index,
                step_index=step_index,
                transition=transition,
                pre_state=pre_state,
                observation=observation,
                post_state=post_state,
            )

            if model_mismatch is not None:
                record["verdict"] = {
                    "state": "inconclusive",
                    "forbidden_state_reached": False,
                    "finding_id": None,
                    "summary": "Observed adapter state diverged from the declared transition model.",
                }
                record["model_mismatch"] = model_mismatch
                path_records.append(record)
                saw_inconclusive = True
                break

            detector_result = detect(record, rules_document)
            record = _apply_detection(record, detector_result)
            path_records.append(record)

            if detector_result["overall"] == "inconclusive":
                saw_inconclusive = True

            if detector_result["overall"] == "violated":
                return {
                    "schema_version": "0.4",
                    "overall": "violated",
                    "search_semantics": "breadth_first_shortest_path_within_bound",
                    "max_depth": max_depth,
                    "max_paths": max_paths,
                    "paths_explored": explored,
                    "minimal_path": [
                        {"from": src, "event": event, "to": dst} for src, event, dst in path
                    ],
                    "violating_step": step_index,
                    "records": path_records,
                    "finding": detector_result["finding"],
                }

    return {
        "schema_version": "0.4",
        "overall": "inconclusive" if saw_inconclusive else "not_found_within_bound",
        "search_semantics": "breadth_first_shortest_path_within_bound",
        "max_depth": max_depth,
        "max_paths": max_paths,
        "paths_explored": explored,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, default=Path(__file__).with_name("forbidden_state_rules.example.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("path-to-finding"))
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-paths", type=int, default=250)
    parser.add_argument(
        "--adapter",
        choices=["synthetic-buggy", "synthetic-safe"],
        default="synthetic-buggy",
        help="Bundled offline adapter. Real integrations should provide an authorized adapter programmatically.",
    )
    args = parser.parse_args()

    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    factory: AdapterFactory = SyntheticBuggyAdapter if args.adapter == "synthetic-buggy" else SyntheticSafeAdapter
    result = search_paths(factory, rules, max_depth=args.max_depth, max_paths=args.max_paths)
    write_result(result, args.out_dir)
    print(json.dumps({
        "overall": result["overall"],
        "paths_explored": result["paths_explored"],
        "violating_step": result["violating_step"],
        "finding_id": result["finding"]["finding_id"] if result["finding"] else None,
    }, indent=2))
    return 1 if result["overall"] == "violated" else 2 if result["overall"] == "inconclusive" else 0


if __name__ == "__main__":
    raise SystemExit(main())
