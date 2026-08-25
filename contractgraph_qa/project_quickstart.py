"""Safe zero-config discovery for smart-contract repositories.

The quickstart layer is a universal front door, not a universal semantic proof.
It inventories a local project, detects common contract ecosystems, surfaces
review signals, plans a native test command, and writes a deterministic starter
report without executing untrusted project code unless explicitly requested.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "cgqa/project-quickstart/v0.1"
MAX_SOURCE_FILES = 5000
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_SIGNAL_OCCURRENCES = 500
MAX_LOG_BYTES = 256 * 1024

EXCLUDED_DIRECTORIES = {
    ".git",
    ".cgqa",
    ".venv",
    "artifacts",
    "build",
    "cache",
    "coverage",
    "dist",
    "lib",
    "node_modules",
    "out",
    "target",
    "venv",
}

SOURCE_LANGUAGES = {
    ".cairo": "cairo",
    ".move": "move",
    ".rs": "rust",
    ".sol": "solidity",
    ".vy": "vyper",
}

SOLIDITY_DECLARATION = re.compile(
    r"\b(?:(abstract)\s+)?(contract|interface|library)\s+([A-Za-z_][A-Za-z0-9_]*)"
)
MOVE_MODULE = re.compile(r"\bmodule\s+(?:[A-Za-z0-9_]+::)?([A-Za-z_][A-Za-z0-9_]*)")
CAIRO_MODULE = re.compile(r"\bmod\s+([A-Za-z_][A-Za-z0-9_]*)")
RUST_SOROBAN_CONTRACT = re.compile(
    r"#\s*\[\s*contract\s*\]\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)
RUST_ANCHOR_PROGRAM = re.compile(
    r"#\s*\[\s*program\s*\]\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)

SOLIDITY_REVIEW_SIGNALS: tuple[tuple[str, str, str, re.Pattern[str]], ...] = (
    (
        "TX_ORIGIN",
        "high",
        "tx.origin participates in authorization or identity logic; review phishing and proxy-call behavior.",
        re.compile(r"\btx\s*\.\s*origin\b"),
    ),
    (
        "DELEGATECALL",
        "high",
        "delegatecall shares caller storage and authority context; review target control and storage layout.",
        re.compile(r"\.\s*delegatecall\s*\("),
    ),
    (
        "SELFDESTRUCT",
        "high",
        "selfdestruct/suicide changes code or balance lifecycle semantics; review chain-version behavior.",
        re.compile(r"\b(?:selfdestruct|suicide)\s*\("),
    ),
    (
        "LOW_LEVEL_CALL",
        "medium",
        "Low-level call requires explicit success, return-data, reentrancy, and value-flow review.",
        re.compile(r"\.\s*call\s*(?:\{|\()"),
    ),
    (
        "INLINE_ASSEMBLY",
        "medium",
        "Inline assembly bypasses parts of Solidity's safety model and needs dedicated review.",
        re.compile(r"\bassembly\b"),
    ),
    (
        "UNCHECKED_ARITHMETIC",
        "medium",
        "Unchecked arithmetic may be intentional but needs explicit invariant and boundary coverage.",
        re.compile(r"\bunchecked\s*\{"),
    ),
    (
        "TIMESTAMP_DEPENDENCE",
        "medium",
        "Timestamp-based transitions need before/exactly-at/after boundary tests.",
        re.compile(r"\bblock\s*\.\s*timestamp\b"),
    ),
    (
        "SIGNATURE_RECOVERY",
        "medium",
        "Signature recovery needs domain, nonce, chain, replay, and malleability checks.",
        re.compile(r"\becrecover\s*\("),
    ),
    (
        "CREATE2",
        "medium",
        "CREATE2 introduces address precomputation and redeployment/identity assumptions.",
        re.compile(r"\bcreate2\b"),
    ),
)


class ProjectQuickstartError(RuntimeError):
    """Expected project discovery or quickstart failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectQuickstartError(message)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _strip_comments_and_strings(source: str) -> str:
    """Replace comments and string contents while preserving newlines/offsets."""

    result = list(source)
    state = "code"
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        nxt = source[index + 1] if index + 1 < length else ""
        if state == "code":
            if char == "/" and nxt == "/":
                result[index] = result[index + 1] = " "
                state = "line_comment"
                index += 2
                continue
            if char == "/" and nxt == "*":
                result[index] = result[index + 1] = " "
                state = "block_comment"
                index += 2
                continue
            if char == '"':
                result[index] = " "
                state = "double_string"
                index += 1
                continue
            if char == "'":
                result[index] = " "
                state = "single_string"
                index += 1
                continue
            index += 1
            continue
        if state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                result[index] = result[index + 1] = " "
                state = "code"
                index += 2
                continue
            if char != "\n":
                result[index] = " "
            index += 1
            continue
        if char == "\\" and index + 1 < length:
            result[index] = " "
            if source[index + 1] != "\n":
                result[index + 1] = " "
            index += 2
            continue
        closing = '"' if state == "double_string" else "'"
        if char == closing:
            result[index] = " "
            state = "code"
        elif char != "\n":
            result[index] = " "
        index += 1
    return "".join(result)


def _walk_source_files(root: Path, output_directory: Path | None) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    skipped: list[str] = []
    output_resolved = output_directory.resolve() if output_directory is not None else None
    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directories):
            candidate = (current_path / name).resolve()
            if name in EXCLUDED_DIRECTORIES:
                continue
            if output_resolved is not None and (
                candidate == output_resolved or output_resolved.is_relative_to(candidate)
            ):
                continue
            if (current_path / name).is_symlink():
                continue
            kept_directories.append(name)
        directories[:] = kept_directories

        for name in sorted(names):
            path = current_path / name
            if path.is_symlink() or SOURCE_LANGUAGES.get(path.suffix.lower()) is None:
                continue
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                skipped.append(_relative(path, root))
                continue
            if size > MAX_SOURCE_BYTES:
                skipped.append(_relative(path, root))
                continue
            files.append(path)
            if len(files) > MAX_SOURCE_FILES:
                raise ProjectQuickstartError(
                    f"source file limit exceeded ({MAX_SOURCE_FILES}); narrow the target project"
                )
    return files, skipped


def _read_package_json(root: Path) -> dict[str, Any]:
    source = root / "package.json"
    if not source.is_file() or source.stat().st_size > MAX_SOURCE_BYTES:
        return {}
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _cargo_text(root: Path) -> str:
    source = root / "Cargo.toml"
    if not source.is_file() or source.stat().st_size > MAX_SOURCE_BYTES:
        return ""
    try:
        return source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_frameworks(root: Path, source_languages: set[str]) -> list[dict[str, str]]:
    detections: list[dict[str, str]] = []

    def add(framework: str, ecosystem: str, marker: str) -> None:
        row = {"framework": framework, "ecosystem": ecosystem, "marker": marker}
        if row not in detections:
            detections.append(row)

    if (root / "foundry.toml").is_file():
        add("foundry", "evm", "foundry.toml")
    for pattern in ("hardhat.config.js", "hardhat.config.cjs", "hardhat.config.mjs", "hardhat.config.ts"):
        if (root / pattern).is_file():
            add("hardhat", "evm", pattern)
            break
    for pattern in ("truffle-config.js", "truffle.js"):
        if (root / pattern).is_file():
            add("truffle", "evm", pattern)
            break
    if (root / "brownie-config.yaml").is_file():
        add("brownie", "evm", "brownie-config.yaml")
    if (root / "ape-config.yaml").is_file():
        add("ape", "evm", "ape-config.yaml")
    if (root / "Anchor.toml").is_file():
        add("anchor", "solana", "Anchor.toml")
    if (root / "Move.toml").is_file():
        add("move", "move", "Move.toml")
    if (root / "Scarb.toml").is_file():
        add("scarb", "starknet", "Scarb.toml")

    package = _read_package_json(root)
    dependencies: dict[str, object] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = package.get(key, {})
        if isinstance(value, dict):
            dependencies.update(value)
    if "hardhat" in dependencies:
        add("hardhat", "evm", "package.json:hardhat")
    if "truffle" in dependencies or "@truffle/contract" in dependencies:
        add("truffle", "evm", "package.json:truffle")

    cargo = _cargo_text(root)
    if "soroban-sdk" in cargo:
        add("soroban", "stellar", "Cargo.toml:soroban-sdk")
    if "anchor-lang" in cargo:
        add("anchor", "solana", "Cargo.toml:anchor-lang")

    if "solidity" in source_languages and not any(
        row["ecosystem"] == "evm" for row in detections
    ):
        add("standalone-solidity", "evm", "*.sol")
    if "vyper" in source_languages and not any(
        row["framework"] in {"brownie", "ape"} for row in detections
    ):
        add("standalone-vyper", "evm", "*.vy")
    if "move" in source_languages and not any(row["ecosystem"] == "move" for row in detections):
        add("move", "move", "*.move")
    if "cairo" in source_languages and not any(row["ecosystem"] == "starknet" for row in detections):
        add("standalone-cairo", "starknet", "*.cairo")

    priority = {
        "foundry": 0,
        "hardhat": 1,
        "truffle": 2,
        "ape": 3,
        "brownie": 4,
        "soroban": 5,
        "anchor": 6,
        "move": 7,
        "scarb": 8,
        "standalone-solidity": 9,
        "standalone-vyper": 10,
        "standalone-cairo": 11,
    }
    return sorted(detections, key=lambda row: (priority.get(row["framework"], 100), row["marker"]))


def _tool_path(root: Path, name: str) -> str | None:
    candidates = [
        root / "node_modules" / ".bin" / name,
        root / "node_modules" / ".bin" / f"{name}.cmd",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def _native_plan(root: Path, detections: list[dict[str, str]]) -> dict[str, Any]:
    framework = detections[0]["framework"] if detections else "unknown"
    command: list[str] | None = None
    required_tool: str | None = None
    if framework == "foundry":
        required_tool = "forge"
        executable = _tool_path(root, "forge")
        if executable:
            command = [executable, "test"]
    elif framework == "hardhat":
        required_tool = "local hardhat"
        executable = _tool_path(root, "hardhat")
        if executable:
            command = [executable, "test"]
    elif framework == "truffle":
        required_tool = "local truffle"
        executable = _tool_path(root, "truffle")
        if executable:
            command = [executable, "test"]
    elif framework in {"ape", "brownie", "standalone-vyper"}:
        required_tool = "pytest"
        executable = _tool_path(root, "pytest")
        if executable:
            command = [executable]
    elif framework == "soroban":
        required_tool = "cargo"
        executable = _tool_path(root, "cargo")
        if executable:
            command = [executable, "test"]
    elif framework == "anchor":
        required_tool = "anchor"
        executable = _tool_path(root, "anchor")
        if executable:
            command = [executable, "test"]
    elif framework == "move":
        aptos = _tool_path(root, "aptos")
        sui = _tool_path(root, "sui")
        required_tool = "aptos or sui"
        if aptos:
            command = [aptos, "move", "test"]
        elif sui:
            command = [sui, "move", "test"]
    elif framework in {"scarb", "standalone-cairo"}:
        required_tool = "scarb"
        executable = _tool_path(root, "scarb")
        if executable:
            command = [executable, "test"]
    elif framework == "standalone-solidity":
        required_tool = "Foundry/Hardhat/another native test runner"

    return {
        "framework": framework,
        "requiredTool": required_tool,
        "available": command is not None,
        "command": command,
        "executionPolicy": "NOT_RUN_BY_DEFAULT",
    }


def _git_subject(root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None or not (root / ".git").exists():
        return {"available": False, "commit": None, "dirty": None}
    try:
        commit = subprocess.run(
            [git, "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                [git, "status", "--porcelain", "--untracked-files=no"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            ).stdout.strip()
        )
        return {"available": True, "commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "commit": None, "dirty": None}


def _declarations_and_signals(
    root: Path,
    source_files: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    inventory: list[dict[str, Any]] = []
    declarations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for path in source_files:
        relative = _relative(path, root)
        data = path.read_bytes()
        language = SOURCE_LANGUAGES[path.suffix.lower()]
        inventory.append(
            {
                "path": relative,
                "language": language,
                "bytes": len(data),
                "sha256": _sha256_bytes(data),
            }
        )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        cleaned = _strip_comments_and_strings(text)

        if language == "solidity":
            for match in SOLIDITY_DECLARATION.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": _line_number(cleaned, match.start()),
                        "kind": "abstract contract" if match.group(1) else match.group(2),
                        "name": match.group(3),
                    }
                )
            for signal_id, severity, description, pattern in SOLIDITY_REVIEW_SIGNALS:
                for match in pattern.finditer(cleaned):
                    if len(signals) >= MAX_SIGNAL_OCCURRENCES:
                        break
                    signals.append(
                        {
                            "id": signal_id,
                            "severity": severity,
                            "path": relative,
                            "line": _line_number(cleaned, match.start()),
                            "description": description,
                        }
                    )
        elif language == "vyper":
            declarations.append(
                {"path": relative, "line": 1, "kind": "vyper contract", "name": path.stem}
            )
        elif language == "move":
            for match in MOVE_MODULE.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": _line_number(cleaned, match.start()),
                        "kind": "move module",
                        "name": match.group(1),
                    }
                )
        elif language == "cairo":
            for match in CAIRO_MODULE.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": _line_number(cleaned, match.start()),
                        "kind": "cairo module",
                        "name": match.group(1),
                    }
                )
        elif language == "rust":
            for kind, pattern in (
                ("soroban contract", RUST_SOROBAN_CONTRACT),
                ("anchor program", RUST_ANCHOR_PROGRAM),
            ):
                for match in pattern.finditer(cleaned):
                    declarations.append(
                        {
                            "path": relative,
                            "line": _line_number(cleaned, match.start()),
                            "kind": kind,
                            "name": match.group(1),
                        }
                    )
    inventory.sort(key=lambda row: row["path"])
    declarations.sort(key=lambda row: (row["path"], row["line"], row["name"]))
    signals.sort(key=lambda row: (row["severity"], row["path"], row["line"], row["id"]))
    return inventory, declarations, signals


def _project_fingerprint(inventory: list[dict[str, Any]]) -> str:
    material = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in inventory
    ]
    return _sha256(material)


def _run_native(root: Path, plan: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    command = plan.get("command")
    if not isinstance(command, list) or not command:
        return {
            "requested": True,
            "status": "not_available",
            "returnCode": None,
            "durationSeconds": None,
            "stdout": "",
            "stderr": "",
        }
    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    try:
        completed = subprocess.run(
            [str(part) for part in command],
            cwd=root,
            env=env,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout[-MAX_LOG_BYTES:].decode("utf-8", errors="replace")
        stderr = completed.stderr[-MAX_LOG_BYTES:].decode("utf-8", errors="replace")
        return {
            "requested": True,
            "status": "pass" if completed.returncode == 0 else "fail",
            "returnCode": completed.returncode,
            "durationSeconds": None,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or b"")[-MAX_LOG_BYTES:].decode("utf-8", errors="replace")
        stderr = (exc.stderr or b"")[-MAX_LOG_BYTES:].decode("utf-8", errors="replace")
        return {
            "requested": True,
            "status": "timeout",
            "returnCode": None,
            "durationSeconds": timeout_seconds,
            "stdout": stdout,
            "stderr": stderr,
        }
    except OSError as exc:
        return {
            "requested": True,
            "status": "error",
            "returnCode": None,
            "durationSeconds": None,
            "stdout": "",
            "stderr": str(exc),
        }


def inspect_project(
    target: Path,
    *,
    output_directory: Path | None = None,
    run_native: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    root = target.expanduser().resolve()
    _require(root.is_dir(), f"target project directory not found: {root}")
    _require(1 <= timeout_seconds <= 3600, "timeout must be between 1 and 3600 seconds")

    source_files, skipped = _walk_source_files(root, output_directory)
    inventory, declarations, signals = _declarations_and_signals(root, source_files)
    languages = sorted({row["language"] for row in inventory})
    detections = _detect_frameworks(root, set(languages))
    native_plan = _native_plan(root, detections)
    native_result = (
        _run_native(root, native_plan, timeout_seconds)
        if run_native
        else {
            "requested": False,
            "status": "not_requested",
            "returnCode": None,
            "durationSeconds": None,
            "stdout": "",
            "stderr": "",
        }
    )

    if not inventory:
        readiness = "BLOCKED_NO_CONTRACT_SOURCES"
        status = "hold"
    elif native_result["status"] in {"fail", "timeout", "error"}:
        readiness = "NATIVE_TESTS_FAILED"
        status = "fail"
    elif detections and native_plan["available"]:
        readiness = "READY_FOR_NATIVE_AND_CGQA_REVIEW"
        status = "pass"
    else:
        readiness = "READY_FOR_REVIEW_ADAPTER_REQUIRED"
        status = "pass"

    primary = detections[0] if detections else {
        "framework": "unknown",
        "ecosystem": "unknown",
        "marker": "none",
    }
    fingerprint = _project_fingerprint(inventory)
    subject = {
        "rootName": root.name,
        "projectFingerprint": fingerprint,
        "git": _git_subject(root),
    }
    capabilities = [
        {
            "capability": "Native project tests",
            "applicable": native_plan["command"] is not None,
            "status": native_result["status"],
        },
        {
            "capability": "Source inventory",
            "applicable": bool(inventory),
            "status": "pass" if inventory else "blocked",
        },
        {
            "capability": "Static review signals",
            "applicable": "solidity" in languages,
            "status": "review" if signals else "no_signals_observed",
        },
        {
            "capability": "Deep stateful ContractGraph-QA",
            "applicable": primary["framework"] == "foundry",
            "status": "adapter_required",
        },
    ]
    return {
        "schema": SCHEMA,
        "status": status,
        "readiness": readiness,
        "subject": subject,
        "targetRoot": str(root),
        "primary": primary,
        "detections": detections,
        "languages": languages,
        "sourceFiles": inventory,
        "skippedOversizedOrUnreadable": sorted(skipped),
        "declarations": declarations,
        "reviewSignals": signals,
        "nativePlan": native_plan,
        "nativeResult": native_result,
        "capabilityPlan": capabilities,
        "nextSteps": _next_steps(primary["framework"], native_plan, bool(declarations)),
        "securityVerdictAuthorized": False,
        "claimBoundary": (
            "Quickstart performs local project discovery, source inventory, review-signal extraction, "
            "and optional native tests. Review signals are not vulnerabilities, native test success is "
            "not a security proof, and deep stateful CGQA still requires a reviewed model/adapter."
        ),
    }


def _next_steps(framework: str, native_plan: dict[str, Any], has_declarations: bool) -> list[str]:
    steps: list[str] = []
    if native_plan.get("command") is None:
        tool = native_plan.get("requiredTool") or "native project test runner"
        steps.append(f"Install or expose {tool}, then re-run with --run-native.")
    else:
        steps.append("Run cgqa quickstart with --run-native to execute the detected local test command.")
    if framework == "foundry":
        steps.extend(
            [
                "Review the discovered contracts and select the exact target contract.",
                "Create a fail-closed deep engagement with cgqa init-engagement <name>.",
                "Implement the reviewed action/state/invariant adapter before engagement-run.",
            ]
        )
    elif has_declarations:
        steps.append(
            "Use the native framework tests now; deep CGQA requires a reviewed adapter for this ecosystem."
        )
    else:
        steps.append("Confirm the project root or add recognized smart-contract source files.")
    steps.append("Treat reviewSignals as investigation prompts, not confirmed defects.")
    return steps


def _render_markdown(result: dict[str, Any]) -> str:
    primary = result["primary"]
    lines = [
        "# ContractGraph-QA Quickstart",
        "",
        f"- Status: `{result['status']}`",
        f"- Readiness: `{result['readiness']}`",
        f"- Framework: `{primary['framework']}`",
        f"- Ecosystem: `{primary['ecosystem']}`",
        f"- Project fingerprint: `{result['subject']['projectFingerprint']}`",
        f"- Source files: `{len(result['sourceFiles'])}`",
        f"- Contract/program declarations: `{len(result['declarations'])}`",
        f"- Review signals: `{len(result['reviewSignals'])}`",
        "",
        "## Detected declarations",
        "",
    ]
    if result["declarations"]:
        for row in result["declarations"]:
            lines.append(
                f"- `{row['kind']} {row['name']}` — `{row['path']}:{row['line']}`"
            )
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Review signals", ""])
    if result["reviewSignals"]:
        for row in result["reviewSignals"]:
            lines.append(
                f"- **{row['id']}** ({row['severity']}) — `{row['path']}:{row['line']}` — {row['description']}"
            )
    else:
        lines.append("- No configured source review signals were observed.")

    lines.extend(["", "## Native test plan", ""])
    command = result["nativePlan"].get("command")
    lines.append(f"- Available: `{result['nativePlan']['available']}`")
    lines.append(f"- Command: `{command if command is not None else 'not available'}`")
    lines.append(f"- Execution result: `{result['nativeResult']['status']}`")

    lines.extend(["", "## Next steps", ""])
    for step in result["nextSteps"]:
        lines.append(f"1. {step}")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            result["claimBoundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_quickstart(
    target: Path,
    *,
    output_directory: Path | None = None,
    run_native: bool = False,
    force: bool = False,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    root = target.expanduser().resolve()
    destination = (
        output_directory.expanduser().resolve()
        if output_directory is not None
        else (root / ".cgqa" / "quickstart").resolve()
    )
    _require(destination != root, "output directory must not equal the target project root")
    if destination.exists():
        _require(force, f"output directory already exists: {destination}; use --force to replace it")
        _require(
            destination.is_relative_to(root),
            "--force may only replace an output directory inside the target project",
        )
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=False)

    try:
        result = inspect_project(
            root,
            output_directory=destination,
            run_native=run_native,
            timeout_seconds=timeout_seconds,
        )
        native = result["nativeResult"]
        stdout = native.pop("stdout", "")
        stderr = native.pop("stderr", "")
        if native["requested"]:
            (destination / "native.stdout.log").write_text(stdout, encoding="utf-8")
            (destination / "native.stderr.log").write_text(stderr, encoding="utf-8")
            native["stdoutLog"] = "native.stdout.log"
            native["stderrLog"] = "native.stderr.log"
        result["outputDirectory"] = str(destination)
        result_path = destination / "quickstart.json"
        report_path = destination / "REPORT.md"
        result_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(_render_markdown(result), encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return {
        "ok": result["status"] != "fail",
        "status": result["status"],
        "readiness": result["readiness"],
        "projectFingerprint": result["subject"]["projectFingerprint"],
        "framework": result["primary"]["framework"],
        "sourceFiles": len(result["sourceFiles"]),
        "declarations": len(result["declarations"]),
        "reviewSignals": len(result["reviewSignals"]),
        "nativeTestStatus": result["nativeResult"]["status"],
        "outputDirectory": str(destination),
        "result": str(result_path),
        "report": str(report_path),
    }
