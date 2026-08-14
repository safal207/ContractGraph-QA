"""Dependency-free credential-boundary scanner for repository CI.

The scanner intentionally enforces a narrow, high-signal contract:

* runtime ``.env`` variants must not be tracked;
* provider/private-key token shapes must not be present in tracked text;
* non-empty literal values assigned to credential-shaped keys must be supplied
  through an environment/secret reference or an explicit placeholder.

It is a boundary guard, not a replacement for provider-side revocation or a
full historical secret-remediation tool.  It never prints matched values.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "cgqa.credential-boundary-result.v0.1"
_ALLOWED_ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template"}
_RUNTIME_ENV_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.test",
    ".env.production",
    ".env.staging",
}
_BINARY_SUFFIXES = {
    ".a",
    ".bin",
    ".class",
    ".dll",
    ".dylib",
    ".eot",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".o",
    ".pdf",
    ".pyd",
    ".so",
    ".wasm",
    ".woff",
    ".woff2",
    ".zip",
}
_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key-header", re.compile(r"-----BEGIN [A-Z0-9 ]+ PRIVATE KEY-----")),
    ("openai-token-shape", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws-access-key-shape", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token-shape", re.compile(r"\b(?:ghp|gho|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("slack-token-shape", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)
_CREDENTIAL_KEY = (
    r"(?:"
    r"[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|PRIVATE_KEY)"
    r"|(?:JUPYTER|GRAFANA|MINIO|OPENAI|ANTHROPIC|STRIPE|AWS|AZURE|GOOGLE)"
    r"[A-Z0-9_]*TOKEN"
    r"|(?:DATABASE|DB|POSTGRES|MYSQL|REDIS|NEO4J|MONGO|GRAFANA|MINIO|AWS|AZURE|GOOGLE)"
    r"[A-Z0-9_]*AUTH"
    r")"
)
_PY_ASSIGNMENT_PATTERN = re.compile(
    rf"^\s*(?:export\s+)?(?P<key>{_CREDENTIAL_KEY})(?:\s*:\s*[^=]+)?\s*=\s*(?P<value>.+?)\s*$",
)
_CONFIG_ASSIGNMENT_PATTERN = re.compile(
    rf"^\s*(?:[-]\s*)?(?P<key>{_CREDENTIAL_KEY})\s*:\s*(?P<value>.+?)\s*$",
)
_PLACEHOLDER_PATTERNS = (
    re.compile(r"^$"),
    re.compile(r"^<[^>]+>$"),
    re.compile(r"^\$\{[^}]+\}$"),
    re.compile(r"^\$\([^)]*\)$"),
    re.compile(r"^(?:your|replace|change|set)[-_ ]", re.IGNORECASE),
    re.compile(r"^(?:example|placeholder|redacted|dummy|changeme|change_me)$", re.IGNORECASE),
    re.compile(r"^(?:none|null|false)$", re.IGNORECASE),
)


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return [Path(item) for item in output.decode().split("\0") if item]


def _is_binary(path: Path, raw: bytes) -> bool:
    return path.suffix.lower() in _BINARY_SUFFIXES or b"\0" in raw[:8192]


def _clean_assignment_value(value: str) -> str:
    value = value.strip().rstrip(",")
    if value.startswith(("\"", "'")) and value.endswith(value[0]):
        value = value[1:-1].strip()
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return value


def _is_placeholder(value: str) -> bool:
    return any(pattern.search(value) for pattern in _PLACEHOLDER_PATTERNS)


def _scan_assignment(path: Path, line_number: int, line: str) -> Iterable[dict[str, Any]]:
    match = _PY_ASSIGNMENT_PATTERN.match(line) or _CONFIG_ASSIGNMENT_PATTERN.match(line)
    if not match:
        return
    key = match.group("key").upper()
    value = _clean_assignment_value(match.group("value"))
    if not value or _is_placeholder(value):
        return
    if value.startswith(
        (
            "os.getenv(",
            "os.Getenv(",
            "getenv(",
            "process.env.",
            "os.environ",
            "secrets.",
            "env(",
            "${",
            "$env:",
        )
    ):
        return
    if key.endswith(("_URL", "_URI")) and not re.search(
        r"(?:@|password|secret|token)", value, re.IGNORECASE
    ):
        return
    yield {
        "path": str(path),
        "line": line_number,
        "rule": "literal-credential-assignment",
        "key": key,
    }


def _iter_violation(path: Path, line_number: int, line: str) -> Iterable[dict[str, Any]]:
    for rule, pattern in _TOKEN_PATTERNS:
        if pattern.search(line):
            yield {"path": str(path), "line": line_number, "rule": rule}

    parts = {part.lower() for part in path.parts}
    if path.suffix.lower() == ".md" or path.name.lower().startswith("test_") or parts.intersection(
        {"docs", "test", "tests", "benchmarks", "fixtures", "examples", "example"}
    ):
        return
    yield from _scan_assignment(path, line_number, line)


def scan_repository(root: Path) -> dict[str, Any]:
    root = root.resolve()
    files = tracked_files(root)
    violations: list[dict[str, Any]] = []
    for relative_path in files:
        if relative_path.name in _RUNTIME_ENV_NAMES:
            violations.append(
                {
                    "path": str(relative_path),
                    "line": None,
                    "rule": "tracked-runtime-environment-file",
                }
            )
            continue
        if relative_path.name in _ALLOWED_ENV_EXAMPLES:
            continue
        path = root / relative_path
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if _is_binary(relative_path, raw):
            continue
        text = raw.decode("utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            violations.extend(_iter_violation(relative_path, line_number, line))

    return {
        "schema": SCHEMA,
        "trackedFiles": len(files),
        "violations": violations,
        "decision": "PASS" if not violations else "BLOCK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    result = scan_repository(args.root)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"{result['decision']} tracked_files={result['trackedFiles']} violations={len(result['violations'])}")
        for violation in result["violations"]:
            location = violation["path"]
            if violation["line"] is not None:
                location += f":{violation['line']}"
            suffix = f" key={violation['key']}" if "key" in violation else ""
            print(f"{location} rule={violation['rule']}{suffix}")
    return 0 if result["decision"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
