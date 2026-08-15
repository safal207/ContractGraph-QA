#!/usr/bin/env python3
"""Build a causal-temporal evidence graph from one Temporal Evidence Record.

Outputs:
- Graphviz DOT for visualization
- Markdown trace for human review

No network access and no execution of target-system actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


NODE_ORDER = (
    "pre_state",
    "request",
    "decision",
    "mutation",
    "post_state",
    "evidence",
    "verdict",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def compact(value: Any, limit: int = 180) -> str:
    text = canonical_json(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_nodes(record: dict[str, Any]) -> dict[str, str]:
    verdict = record.get("verdict", {})
    return {
        "pre_state": f"PRE-STATE\\n{compact(record.get('pre_state'))}",
        "request": f"REQUEST\\n{compact(record.get('request'))}",
        "decision": f"DECISION\\n{compact(record.get('decision'))}",
        "mutation": f"MUTATION\\n{compact(record.get('mutation'))}",
        "post_state": f"POST-STATE\\n{compact(record.get('post_state'))}",
        "evidence": f"EVIDENCE\\n{compact(record.get('evidence'))}",
        "verdict": (
            "VERDICT\\n"
            f"state={verdict.get('state')}\\n"
            f"forbidden={verdict.get('forbidden_state_reached')}"
        ),
    }


def build_dot(record: dict[str, Any]) -> str:
    nodes = build_nodes(record)
    lines = [
        "digraph temporal_evidence {",
        '  rankdir="LR";',
        '  node [shape="box"];',
    ]
    for node_id in NODE_ORDER:
        lines.append(f'  {node_id} [label="{dot_escape(nodes[node_id])}"];')
    for left, right in zip(NODE_ORDER, NODE_ORDER[1:]):
        lines.append(f"  {left} -> {right};")

    for i, invariant in enumerate(record.get("invariants", []), 1):
        inv_id = f"invariant_{i}"
        label = (
            f"INVARIANT {invariant.get('id')}\\n"
            f"{invariant.get('verdict')}\\n"
            f"{invariant.get('observed')}"
        )
        lines.append(f'  {inv_id} [shape="note", label="{dot_escape(label)}"];')
        lines.append(f"  post_state -> {inv_id};")
        lines.append(f"  {inv_id} -> verdict;")

    lines.append("}")
    return "\n".join(lines) + "\n"


def build_markdown(record: dict[str, Any]) -> str:
    digest = record_digest(record)
    verdict = record.get("verdict", {})
    out = [
        f"# Evidence Trace — {record.get('scenario_id', 'unknown')}",
        "",
        f"- Run: `{record.get('run_id', 'unknown')}`",
        f"- Record SHA-256: `{digest}`",
        f"- Verdict: **{verdict.get('state', 'unknown')}**",
        f"- Forbidden state reached: **{verdict.get('forbidden_state_reached', 'unknown')}**",
        "",
        "## Causal-temporal chain",
        "",
    ]
    for node_id in NODE_ORDER:
        out += [
            f"### {node_id.replace('_', ' ').title()}",
            "",
            "```json",
            json.dumps(record.get(node_id), indent=2, ensure_ascii=False, sort_keys=True),
            "```",
            "",
        ]
    out += ["## Invariants", ""]
    for invariant in record.get("invariants", []):
        out.append(
            f"- `{invariant.get('id')}` — **{invariant.get('verdict')}** — "
            f"{invariant.get('rule')} — observed: `{invariant.get('observed')}`"
        )
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("record", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("evidence-graph"))
    args = ap.parse_args()

    record = json.loads(args.record.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    dot_path = args.out_dir / "evidence.dot"
    md_path = args.out_dir / "evidence.md"
    digest_path = args.out_dir / "record.sha256"

    dot_path.write_text(build_dot(record), encoding="utf-8")
    md_path.write_text(build_markdown(record), encoding="utf-8")
    digest_path.write_text(record_digest(record) + "\n", encoding="utf-8")

    print(dot_path)
    print(md_path)
    print(digest_path)


if __name__ == "__main__":
    main()
