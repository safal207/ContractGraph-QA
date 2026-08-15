#!/usr/bin/env python3
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml

SPEC = Path(__file__).with_name("transition_field.example.yaml")


def parse_transitions(text: str):
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid transition YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError("transition document root must be a mapping")
    transitions = document.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        raise ValueError("transition document must contain a non-empty transitions list")

    parsed: list[tuple[str, str, str]] = []
    for index, item in enumerate(transitions):
        if not isinstance(item, dict):
            raise ValueError(f"transitions[{index}] must be a mapping")
        values: list[str] = []
        for field in ("from", "event", "to"):
            value: Any = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"transitions[{index}].{field} must be a non-empty string")
            values.append(value.strip())
        parsed.append((values[0], values[1], values[2]))
    return parsed


def generate_paths(start="Q0_RESET", max_depth=6, max_paths=None):
    if max_depth < 1:
        raise ValueError("max_depth must be >= 1")
    if max_paths is not None and max_paths < 1:
        raise ValueError("max_paths must be >= 1 when provided")

    text = SPEC.read_text(encoding="utf-8")
    transitions = parse_transitions(text)
    graph = defaultdict(list)
    for src, event, dst in transitions:
        graph[src].append((event, dst))

    queue = deque([(start, [])])
    paths = []

    while queue and (max_paths is None or len(paths) < max_paths):
        state, path = queue.popleft()
        if path:
            paths.append(path)
            if max_paths is not None and len(paths) >= max_paths:
                break
        if len(path) >= max_depth:
            continue
        for event, dst in graph[state]:
            queue.append((dst, [*path, (state, event, dst)]))

    return paths


def main():
    paths = generate_paths()
    print(f"Generated {len(paths)} bounded transition paths")
    for index, path in enumerate(paths, 1):
        print(f"\nPATH-{index:03d}")
        for src, event, dst in path:
            print(f"  {src} --{event}--> {dst}")


if __name__ == "__main__":
    main()
