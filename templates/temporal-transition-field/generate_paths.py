#!/usr/bin/env python3
from collections import defaultdict, deque
from pathlib import Path
import re

SPEC = Path(__file__).with_name("transition_field.example.yaml")


def parse_transitions(text: str):
    pattern = re.compile(r"- \{from: ([^,]+), event: ([^,]+), to: ([^}]+)\}")
    return [m.groups() for m in pattern.finditer(text)]


def generate_paths(start="Q0_RESET", max_depth=6):
    text = SPEC.read_text(encoding="utf-8")
    transitions = parse_transitions(text)
    graph = defaultdict(list)
    for src, event, dst in transitions:
        graph[src].append((event, dst))

    queue = deque([(start, [])])
    paths = []

    while queue:
        state, path = queue.popleft()
        if path:
            paths.append(path)
        if len(path) >= max_depth:
            continue
        for event, dst in graph[state]:
            queue.append((dst, path + [(state, event, dst)]))

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
