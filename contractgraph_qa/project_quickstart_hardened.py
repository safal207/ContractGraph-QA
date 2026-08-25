"""Hardened universal smart-contract project quickstart.

This module strengthens the v0.1 discovery layer with exact configuration
binding, nested-workspace discovery, secret-safe native execution, post-run
subject re-freezing, incomplete-inventory fail-closed semantics, and atomic
report replacement.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any

from contractgraph_qa import project_quickstart as base

SCHEMA = "cgqa/project-quickstart/v0.2"
ProjectQuickstartError = base.ProjectQuickstartError

MAX_SOURCE_FILES = base.MAX_SOURCE_FILES
MAX_SOURCE_BYTES = base.MAX_SOURCE_BYTES
MAX_CONFIG_FILES = 1000
MAX_LOG_BYTES = base.MAX_LOG_BYTES
MAX_WORKSPACE_DEPTH = 6

SOURCE_LANGUAGES = {
    **base.SOURCE_LANGUAGES,
    ".sw": "sway",
    ".tact": "tact",
    ".fc": "func",
    ".func": "func",
    ".ligo": "ligo",
    ".mligo": "ligo",
    ".jsligo": "ligo",
}

ALWAYS_EXCLUDED_DIRECTORIES = {
    ".git",
    ".cgqa",
    ".venv",
    "artifacts",
    "build",
    "cache",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "venv",
}

CONFIG_NAMES = {
    "foundry.toml",
    "remappings.txt",
    "hardhat.config.js",
    "hardhat.config.cjs",
    "hardhat.config.mjs",
    "hardhat.config.ts",
    "truffle-config.js",
    "truffle.js",
    "brownie-config.yaml",
    "ape-config.yaml",
    "Anchor.toml",
    "Move.toml",
    "Scarb.toml",
    "Forc.toml",
    "Tact.config.ts",
    "tact.config.ts",
    "Cargo.toml",
    "Cargo.lock",
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "sui.lock",
    "Move.lock",
}

FRAMEWORK_PRIORITY = {
    "foundry": 0,
    "hardhat": 1,
    "truffle": 2,
    "ape": 3,
    "brownie": 4,
    "soroban": 5,
    "anchor": 6,
    "cosmwasm": 7,
    "near": 8,
    "ink": 9,
    "stylus": 10,
    "solana-rust": 11,
    "move": 12,
    "scarb": 13,
    "fuel": 14,
    "tact": 15,
    "ligo": 16,
    "standalone-solidity": 17,
    "standalone-vyper": 18,
    "standalone-cairo": 19,
    "unknown": 100,
}

SENSITIVE_ENV_TOKENS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSPHRASE",
    "MNEMONIC",
    "SEED",
    "PRIVATE",
    "RPC_URL",
    "WEB3",
    "INFURA",
    "ALCHEMY",
    "ETHERSCAN",
    "API_URL",
)

ENV_ALLOWLIST = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "RUSTUP_HOME",
    "COMSPEC",
    "PATHEXT",
}

TACT_CONTRACT = re.compile(r"\bcontract\s+([A-Za-z_][A-Za-z0-9_]*)")
LIGO_MODULE = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)")
RUST_INK_CONTRACT = re.compile(r"#\s*\[\s*ink::contract\s*\]\s*mod\s+([A-Za-z_][A-Za-z0-9_]*)")
RUST_NEAR_CONTRACT = re.compile(
    r"#\s*\[\s*near(?:_sdk)?::near\s*\]\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)"
)


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


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _depth(relative: str) -> int:
    return 0 if relative in {"", "."} else len(Path(relative).parts)


def _foundry_root(path: Path) -> bool:
    return (path / "foundry.toml").is_file()


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _walk_candidate_files(
    root: Path,
    output_directory: Path | None,
) -> tuple[list[Path], list[Path], list[dict[str, str]]]:
    sources: list[Path] = []
    configs: list[Path] = []
    skipped: list[dict[str, str]] = []
    output_resolved = output_directory.resolve() if output_directory is not None else None

    for current, directories, names in os.walk(root, followlinks=False):
        current_path = Path(current)
        try:
            current_relative = current_path.relative_to(root)
        except ValueError:
            continue
        if len(current_relative.parts) > MAX_WORKSPACE_DEPTH + 4:
            directories[:] = []
            continue

        kept: list[str] = []
        for name in sorted(directories):
            child = current_path / name
            if name in ALWAYS_EXCLUDED_DIRECTORIES:
                continue
            if name == "lib" and _foundry_root(current_path):
                continue
            try:
                resolved = child.resolve()
            except OSError:
                skipped.append({"path": _relative(child, root), "reason": "DIRECTORY_UNREADABLE"})
                continue
            if output_resolved is not None and resolved == output_resolved:
                continue
            if child.is_symlink():
                continue
            kept.append(name)
        directories[:] = kept

        for name in sorted(names):
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            relative = _relative(path, root)
            suffix = path.suffix.lower()
            is_source = suffix in SOURCE_LANGUAGES
            is_config = name in CONFIG_NAMES
            if not is_source and not is_config:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                skipped.append({"path": relative, "reason": "STAT_FAILED"})
                continue
            if size > MAX_SOURCE_BYTES:
                skipped.append(
                    {
                        "path": relative,
                        "reason": "SOURCE_TOO_LARGE" if is_source else "CONFIG_TOO_LARGE",
                    }
                )
                continue
            if is_source:
                sources.append(path)
                if len(sources) > MAX_SOURCE_FILES:
                    raise ProjectQuickstartError(
                        f"source file limit exceeded ({MAX_SOURCE_FILES}); narrow the target project"
                    )
            if is_config:
                configs.append(path)
                if len(configs) > MAX_CONFIG_FILES:
                    raise ProjectQuickstartError(
                        f"configuration file limit exceeded ({MAX_CONFIG_FILES}); narrow the target project"
                    )
    return sources, configs, skipped


def _inventory(
    root: Path,
    files: list[Path],
    *,
    source: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    text_by_path: dict[str, str] = {}
    for path in sorted(set(files), key=lambda item: _relative(item, root)):
        relative = _relative(path, root)
        try:
            data = _read_bytes(path)
        except OSError as exc:
            skipped.append(
                {
                    "path": relative,
                    "reason": "READ_FAILED",
                    "detail": type(exc).__name__,
                }
            )
            continue
        row: dict[str, Any] = {
            "path": relative,
            "bytes": len(data),
            "sha256": _sha256_bytes(data),
        }
        if source:
            row["language"] = SOURCE_LANGUAGES[path.suffix.lower()]
        rows.append(row)
        if source:
            text_by_path[relative] = data.decode("utf-8", errors="replace")
    return rows, skipped, text_by_path


def _declarations_and_signals(
    root: Path,
    source_inventory: list[dict[str, Any]],
    text_by_path: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    declarations: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []

    for row in source_inventory:
        relative = str(row["path"])
        language = str(row["language"])
        text = text_by_path[relative]
        cleaned = base._strip_comments_and_strings(text)

        if language == "solidity":
            for match in base.SOLIDITY_DECLARATION.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": base._line_number(cleaned, match.start()),
                        "kind": "abstract contract" if match.group(1) else match.group(2),
                        "name": match.group(3),
                    }
                )
            for signal_id, severity, description, pattern in base.SOLIDITY_REVIEW_SIGNALS:
                for match in pattern.finditer(cleaned):
                    if len(signals) >= base.MAX_SIGNAL_OCCURRENCES:
                        break
                    signals.append(
                        {
                            "id": signal_id,
                            "severity": severity,
                            "path": relative,
                            "line": base._line_number(cleaned, match.start()),
                            "description": description,
                        }
                    )
        elif language == "vyper":
            declarations.append(
                {"path": relative, "line": 1, "kind": "vyper contract", "name": Path(relative).stem}
            )
        elif language == "move":
            for match in base.MOVE_MODULE.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": base._line_number(cleaned, match.start()),
                        "kind": "move module",
                        "name": match.group(1),
                    }
                )
        elif language == "cairo":
            for match in base.CAIRO_MODULE.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": base._line_number(cleaned, match.start()),
                        "kind": "cairo module",
                        "name": match.group(1),
                    }
                )
        elif language == "rust":
            patterns = (
                ("soroban contract", base.RUST_SOROBAN_CONTRACT),
                ("anchor program", base.RUST_ANCHOR_PROGRAM),
                ("ink contract", RUST_INK_CONTRACT),
                ("near contract", RUST_NEAR_CONTRACT),
            )
            for kind, pattern in patterns:
                for match in pattern.finditer(cleaned):
                    declarations.append(
                        {
                            "path": relative,
                            "line": base._line_number(cleaned, match.start()),
                            "kind": kind,
                            "name": match.group(1),
                        }
                    )
        elif language == "sway":
            declarations.append(
                {
                    "path": relative,
                    "line": 1,
                    "kind": "sway contract/program",
                    "name": Path(relative).parent.name or Path(relative).stem,
                }
            )
        elif language == "tact":
            for match in TACT_CONTRACT.finditer(cleaned):
                declarations.append(
                    {
                        "path": relative,
                        "line": base._line_number(cleaned, match.start()),
                        "kind": "tact contract",
                        "name": match.group(1),
                    }
                )
        elif language == "ligo":
            found = False
            for match in LIGO_MODULE.finditer(cleaned):
                found = True
                declarations.append(
                    {
                        "path": relative,
                        "line": base._line_number(cleaned, match.start()),
                        "kind": "ligo module",
                        "name": match.group(1),
                    }
                )
            if not found:
                declarations.append(
                    {
                        "path": relative,
                        "line": 1,
                        "kind": "ligo contract/module",
                        "name": Path(relative).stem,
                    }
                )

    declarations.sort(key=lambda row: (row["path"], row["line"], row["name"]))
    severity_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(
        key=lambda row: (
            severity_order.get(str(row["severity"]), 9),
            row["path"],
            row["line"],
            row["id"],
        )
    )
    return declarations, signals


def _parse_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_toml(path: Path) -> dict[str, Any]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _cargo_dependencies(path: Path) -> set[str]:
    data = _parse_toml(path)
    names: set[str] = set()
    for section_name in ("dependencies", "dev-dependencies", "build-dependencies"):
        section = data.get(section_name, {})
        if isinstance(section, dict):
            names.update(str(key) for key in section)
    workspace = data.get("workspace", {})
    if isinstance(workspace, dict):
        section = workspace.get("dependencies", {})
        if isinstance(section, dict):
            names.update(str(key) for key in section)
    return names


def _package_dependencies(path: Path) -> set[str]:
    data = _parse_json(path)
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key, {})
        if isinstance(section, dict):
            names.update(str(name) for name in section)
    return names


def _package_has_test(path: Path) -> bool:
    data = _parse_json(path)
    scripts = data.get("scripts", {})
    return isinstance(scripts, dict) and isinstance(scripts.get("test"), str) and bool(
        scripts["test"].strip()
    )


def _project_roots(root: Path, config_inventory: list[dict[str, Any]]) -> list[Path]:
    roots = {root}
    marker_names = {
        "foundry.toml",
        "hardhat.config.js",
        "hardhat.config.cjs",
        "hardhat.config.mjs",
        "hardhat.config.ts",
        "truffle-config.js",
        "truffle.js",
        "brownie-config.yaml",
        "ape-config.yaml",
        "Anchor.toml",
        "Move.toml",
        "Scarb.toml",
        "Forc.toml",
        "Tact.config.ts",
        "tact.config.ts",
        "Cargo.toml",
        "package.json",
    }
    for row in config_inventory:
        path = root / str(row["path"])
        if path.name in marker_names:
            relative_parent = path.parent.relative_to(root)
            if len(relative_parent.parts) <= MAX_WORKSPACE_DEPTH:
                roots.add(path.parent)
    return sorted(roots, key=lambda path: (_depth(_relative(path, root)), _relative(path, root)))


def _languages_under(project_root: Path, root: Path, source_inventory: list[dict[str, Any]]) -> set[str]:
    project_relative = _relative(project_root, root)
    prefix = "" if project_relative == "." else f"{project_relative}/"
    return {
        str(row["language"])
        for row in source_inventory
        if project_relative == "." or str(row["path"]).startswith(prefix)
    }


def _detect_at(project_root: Path, root: Path, languages: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(framework: str, ecosystem: str, marker: str) -> None:
        rows.append(
            {
                "framework": framework,
                "ecosystem": ecosystem,
                "marker": marker,
                "projectRoot": _relative(project_root, root),
            }
        )

    if (project_root / "foundry.toml").is_file():
        add("foundry", "evm", "foundry.toml")
    for name in (
        "hardhat.config.js",
        "hardhat.config.cjs",
        "hardhat.config.mjs",
        "hardhat.config.ts",
    ):
        if (project_root / name).is_file():
            add("hardhat", "evm", name)
            break
    for name in ("truffle-config.js", "truffle.js"):
        if (project_root / name).is_file():
            add("truffle", "evm", name)
            break
    if (project_root / "brownie-config.yaml").is_file():
        add("brownie", "evm", "brownie-config.yaml")
    if (project_root / "ape-config.yaml").is_file():
        add("ape", "evm", "ape-config.yaml")
    if (project_root / "Anchor.toml").is_file():
        add("anchor", "solana", "Anchor.toml")
    if (project_root / "Move.toml").is_file():
        add("move", "move", "Move.toml")
    if (project_root / "Scarb.toml").is_file():
        add("scarb", "starknet", "Scarb.toml")
    if (project_root / "Forc.toml").is_file():
        add("fuel", "fuel", "Forc.toml")
    if (project_root / "Tact.config.ts").is_file() or (project_root / "tact.config.ts").is_file():
        add("tact", "ton", "Tact.config.ts")

    package_path = project_root / "package.json"
    package_deps = _package_dependencies(package_path) if package_path.is_file() else set()
    if "hardhat" in package_deps:
        add("hardhat", "evm", "package.json:hardhat")
    if "truffle" in package_deps or "@truffle/contract" in package_deps:
        add("truffle", "evm", "package.json:truffle")
    if "@tact-lang/compiler" in package_deps:
        add("tact", "ton", "package.json:@tact-lang/compiler")

    cargo_path = project_root / "Cargo.toml"
    cargo_deps = _cargo_dependencies(cargo_path) if cargo_path.is_file() else set()
    if "soroban-sdk" in cargo_deps:
        add("soroban", "stellar", "Cargo.toml:soroban-sdk")
    if "anchor-lang" in cargo_deps:
        add("anchor", "solana", "Cargo.toml:anchor-lang")
    if "cosmwasm-std" in cargo_deps:
        add("cosmwasm", "cosmos", "Cargo.toml:cosmwasm-std")
    if "near-sdk" in cargo_deps:
        add("near", "near", "Cargo.toml:near-sdk")
    if "ink" in cargo_deps or "ink_lang" in cargo_deps:
        add("ink", "polkadot", "Cargo.toml:ink")
    if "stylus-sdk" in cargo_deps:
        add("stylus", "arbitrum", "Cargo.toml:stylus-sdk")
    if "solana-program" in cargo_deps and "anchor-lang" not in cargo_deps:
        add("solana-rust", "solana", "Cargo.toml:solana-program")

    if "solidity" in languages and not any(row["ecosystem"] == "evm" for row in rows):
        add("standalone-solidity", "evm", "*.sol")
    if "vyper" in languages and not any(
        row["framework"] in {"brownie", "ape"} for row in rows
    ):
        add("standalone-vyper", "evm", "*.vy")
    if "move" in languages and not any(row["ecosystem"] == "move" for row in rows):
        add("move", "move", "*.move")
    if "cairo" in languages and not any(row["ecosystem"] == "starknet" for row in rows):
        add("standalone-cairo", "starknet", "*.cairo")
    if "sway" in languages and not any(row["framework"] == "fuel" for row in rows):
        add("fuel", "fuel", "*.sw")
    if "tact" in languages and not any(row["framework"] == "tact" for row in rows):
        add("tact", "ton", "*.tact")
    if "ligo" in languages:
        add("ligo", "tezos", "*.ligo")
    return rows


def _detect_frameworks(
    root: Path,
    source_inventory: list[dict[str, Any]],
    config_inventory: list[dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for project_root in _project_roots(root, config_inventory):
        rows.extend(_detect_at(project_root, root, _languages_under(project_root, root, source_inventory)))

    deduped: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["framework"], row["projectRoot"], row["marker"])
        deduped[key] = row
    return sorted(
        deduped.values(),
        key=lambda row: (
            FRAMEWORK_PRIORITY.get(row["framework"], 100),
            _depth(row["projectRoot"]),
            row["projectRoot"],
            row["marker"],
        ),
    )


def _tool_path(project_root: Path, name: str) -> str | None:
    candidates = [
        project_root / "node_modules" / ".bin" / name,
        project_root / "node_modules" / ".bin" / f"{name}.cmd",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(name)


def _native_plan(root: Path, detections: list[dict[str, str]]) -> dict[str, Any]:
    primary = detections[0] if detections else {
        "framework": "unknown",
        "projectRoot": ".",
    }
    framework = primary["framework"]
    relative_root = primary.get("projectRoot", ".")
    project_root = root if relative_root == "." else root / relative_root
    command: list[str] | None = None
    required_tool: str | None = None

    def executable(name: str) -> str | None:
        return _tool_path(project_root, name)

    if framework == "foundry":
        required_tool = "forge"
        if tool := executable("forge"):
            command = [tool, "test"]
    elif framework == "hardhat":
        required_tool = "local hardhat"
        if tool := executable("hardhat"):
            command = [tool, "test"]
    elif framework == "truffle":
        required_tool = "local truffle"
        if tool := executable("truffle"):
            command = [tool, "test"]
    elif framework == "ape":
        required_tool = "ape"
        if tool := executable("ape"):
            command = [tool, "test"]
    elif framework == "brownie":
        required_tool = "brownie"
        if tool := executable("brownie"):
            command = [tool, "test"]
    elif framework == "standalone-vyper":
        required_tool = "project-specific Vyper test runner"
    elif framework in {"soroban", "cosmwasm", "near", "ink", "stylus", "solana-rust"}:
        required_tool = "cargo"
        if tool := executable("cargo"):
            command = [tool, "test"]
    elif framework == "anchor":
        required_tool = "anchor"
        if tool := executable("anchor"):
            command = [tool, "test"]
    elif framework == "move":
        required_tool = "aptos or sui"
        if tool := executable("aptos"):
            command = [tool, "move", "test"]
        elif tool := executable("sui"):
            command = [tool, "move", "test"]
    elif framework in {"scarb", "standalone-cairo"}:
        required_tool = "scarb"
        if tool := executable("scarb"):
            command = [tool, "test"]
    elif framework == "fuel":
        required_tool = "forc"
        if tool := executable("forc"):
            command = [tool, "test"]
    elif framework == "tact":
        required_tool = "project-defined package.json test script"
        package = project_root / "package.json"
        if package.is_file() and _package_has_test(package):
            if tool := executable("npm"):
                command = [tool, "test"]
    elif framework == "ligo":
        required_tool = "project-specific LIGO test command"
    elif framework == "standalone-solidity":
        required_tool = "Foundry/Hardhat/another native test runner"

    return {
        "framework": framework,
        "projectRoot": relative_root,
        "requiredTool": required_tool,
        "available": command is not None,
        "command": command,
        "executionPolicy": "NOT_RUN_BY_DEFAULT",
    }


def _safe_environment(*, inherit_environment: bool) -> tuple[dict[str, str], list[str], list[str]]:
    if inherit_environment:
        env = dict(os.environ)
        inherited = sorted(env)
        stripped: list[str] = []
    else:
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in ENV_ALLOWLIST
        }
        inherited = sorted(env)
        stripped = sorted(
            key
            for key in os.environ
            if key not in env
            and any(token in key.upper() for token in SENSITIVE_ENV_TOKENS)
        )
    env["NO_COLOR"] = "1"
    env["CI"] = "1"
    return env, inherited, stripped


def _run_command(
    project_root: Path,
    plan: dict[str, Any],
    timeout_seconds: int,
    *,
    inherit_environment: bool,
) -> dict[str, Any]:
    command = plan.get("command")
    if not isinstance(command, list) or not command:
        return {
            "requested": True,
            "status": "not_available",
            "returnCode": None,
            "durationSeconds": None,
            "stdout": "",
            "stderr": "",
            "environmentPolicy": "INHERITED" if inherit_environment else "SANITIZED",
            "inheritedEnvironmentNames": [],
            "strippedSensitiveEnvironmentNames": [],
        }

    env, inherited, stripped = _safe_environment(inherit_environment=inherit_environment)
    isolated_home: str | None = None
    if not inherit_environment:
        isolated_home = tempfile.mkdtemp(prefix="cgqa-native-home-")
        env["HOME"] = isolated_home
        env["USERPROFILE"] = isolated_home
        null_config = "NUL" if os.name == "nt" else "/dev/null"
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = null_config
        env["NPM_CONFIG_USERCONFIG"] = null_config
    started = time.monotonic()
    kwargs: dict[str, Any] = {
        "cwd": project_root,
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True

    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen([str(part) for part in command], **kwargs)
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
        return_code = process.returncode
        status = "pass" if return_code == 0 else "fail"
    except subprocess.TimeoutExpired as exc:
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        if process is not None:
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
            trailing_out, trailing_err = process.communicate()
            stdout_bytes += trailing_out or b""
            stderr_bytes += trailing_err or b""
        return_code = None
        status = "timeout"
    except OSError as exc:
        stdout_bytes = b""
        stderr_bytes = str(exc).encode("utf-8", errors="replace")
        return_code = None
        status = "error"
    except BaseException:
        if isolated_home is not None:
            shutil.rmtree(isolated_home, ignore_errors=True)
        raise

    result = {
        "requested": True,
        "status": status,
        "returnCode": return_code,
        "durationSeconds": round(time.monotonic() - started, 3),
        "stdout": stdout_bytes[-MAX_LOG_BYTES:].decode("utf-8", errors="replace"),
        "stderr": stderr_bytes[-MAX_LOG_BYTES:].decode("utf-8", errors="replace"),
        "environmentPolicy": "INHERITED" if inherit_environment else "SANITIZED_ISOLATED_HOME",
        "inheritedEnvironmentNames": inherited,
        "strippedSensitiveEnvironmentNames": stripped,
        "isolatedHomeUsed": isolated_home is not None,
    }
    if isolated_home is not None:
        shutil.rmtree(isolated_home, ignore_errors=True)
    return result


def _git_command(git: str, root: Path, args: list[str]) -> str:
    null_path = "NUL" if os.name == "nt" else "/dev/null"
    command = [
        git,
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={null_path}",
        *args,
    ]
    env, _, _ = _safe_environment(inherit_environment=False)
    return subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()


def _git_subject(root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if git is None:
        return {
            "available": False,
            "repositoryRoot": None,
            "commit": None,
            "dirty": None,
            "statusHash": None,
            "inspectionPolicy": "HOOKS_AND_FSMONITOR_DISABLED",
        }
    try:
        repository_root = _git_command(git, root, ["rev-parse", "--show-toplevel"])
        commit = _git_command(git, root, ["rev-parse", "HEAD"])
        status_text = _git_command(
            git,
            root,
            ["status", "--porcelain", "--untracked-files=normal", "--", "."],
        )
        return {
            "available": True,
            "repositoryRoot": repository_root,
            "commit": commit,
            "dirty": bool(status_text),
            "statusHash": _sha256_bytes(status_text.encode("utf-8")),
            "inspectionPolicy": "HOOKS_AND_FSMONITOR_DISABLED",
        }
    except (OSError, subprocess.SubprocessError):
        return {
            "available": False,
            "repositoryRoot": None,
            "commit": None,
            "dirty": None,
            "statusHash": None,
            "inspectionPolicy": "HOOKS_AND_FSMONITOR_DISABLED",
        }


def _fingerprints(
    source_inventory: list[dict[str, Any]],
    config_inventory: list[dict[str, Any]],
) -> tuple[str, str, str]:
    source_material = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in source_inventory
    ]
    config_material = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in config_inventory
    ]
    source_hash = _sha256(source_material)
    config_hash = _sha256(config_material)
    project_hash = _sha256({"sources": source_material, "configuration": config_material})
    return source_hash, config_hash, project_hash


def _scan_project(
    root: Path,
    output_directory: Path | None,
) -> dict[str, Any]:
    source_paths, config_paths, walk_skipped = _walk_candidate_files(root, output_directory)
    sources, source_skipped, text_by_path = _inventory(root, source_paths, source=True)
    configs, config_skipped, _ = _inventory(root, config_paths, source=False)
    declarations, signals = _declarations_and_signals(root, sources, text_by_path)
    detections = _detect_frameworks(root, sources, configs)
    source_hash, config_hash, project_hash = _fingerprints(sources, configs)
    return {
        "sourceFiles": sources,
        "configurationFiles": configs,
        "skippedFiles": sorted(
            [*walk_skipped, *source_skipped, *config_skipped],
            key=lambda row: (row["path"], row["reason"]),
        ),
        "declarations": declarations,
        "reviewSignals": signals,
        "detections": detections,
        "sourceFingerprint": source_hash,
        "configurationFingerprint": config_hash,
        "projectFingerprint": project_hash,
    }


def _next_steps(framework: str, native_plan: dict[str, Any], has_declarations: bool) -> list[str]:
    steps: list[str] = []
    if native_plan.get("command") is None:
        tool = native_plan.get("requiredTool") or "native project test runner"
        steps.append(f"Install or configure {tool}, then re-run with --run-native.")
    else:
        steps.append("Review the detected command, then re-run with --run-native.")
    if framework == "foundry":
        steps.extend(
            [
                "Select the exact target contract from the discovered declarations.",
                "Create a fail-closed deep engagement with cgqa init-engagement <name>.",
                "Implement and review the action/state/invariant adapter before engagement-run.",
            ]
        )
    elif has_declarations:
        steps.append(
            "Use native framework tests now; deep stateful CGQA requires a reviewed adapter for this ecosystem."
        )
    else:
        steps.append("Confirm the project root or add recognized smart-contract source files.")
    steps.append("Treat reviewSignals as investigation prompts, not confirmed defects.")
    return steps


def inspect_project(
    target: Path,
    *,
    output_directory: Path | None = None,
    run_native: bool = False,
    timeout_seconds: int = 300,
    inherit_environment: bool = False,
) -> dict[str, Any]:
    root = target.expanduser().resolve()
    _require(root.is_dir(), f"target project directory not found: {root}")
    _require(1 <= timeout_seconds <= 3600, "timeout must be between 1 and 3600 seconds")

    pre = _scan_project(root, output_directory)
    git_before = _git_subject(root)
    languages = sorted({str(row["language"]) for row in pre["sourceFiles"]})
    detections = pre["detections"]
    primary = detections[0] if detections else {
        "framework": "unknown",
        "ecosystem": "unknown",
        "marker": "none",
        "projectRoot": ".",
    }
    native_plan = _native_plan(root, detections)
    project_root = root if native_plan["projectRoot"] == "." else root / native_plan["projectRoot"]
    native_result = (
        _run_command(
            project_root,
            native_plan,
            timeout_seconds,
            inherit_environment=inherit_environment,
        )
        if run_native
        else {
            "requested": False,
            "status": "not_requested",
            "returnCode": None,
            "durationSeconds": None,
            "stdout": "",
            "stderr": "",
            "environmentPolicy": "NOT_USED",
            "inheritedEnvironmentNames": [],
            "strippedSensitiveEnvironmentNames": [],
        }
    )

    post = _scan_project(root, output_directory) if run_native else pre
    git_after = _git_subject(root) if run_native else git_before
    fingerprint_changed = pre["projectFingerprint"] != post["projectFingerprint"]
    git_changed = (
        bool(git_before.get("available"))
        and bool(git_after.get("available"))
        and (
            git_before.get("commit") != git_after.get("commit")
            or git_before.get("statusHash") != git_after.get("statusHash")
        )
    )
    subject_changed = fingerprint_changed or git_changed

    if not pre["sourceFiles"]:
        status = "hold"
        readiness = "BLOCKED_NO_CONTRACT_SOURCES"
    elif pre["skippedFiles"]:
        status = "hold"
        readiness = "INCOMPLETE_PROJECT_INVENTORY"
    elif run_native and native_result["status"] == "not_available":
        status = "hold"
        readiness = "BLOCKED_NATIVE_TOOL_MISSING"
    elif native_result["status"] in {"fail", "timeout", "error"}:
        status = "fail"
        readiness = "NATIVE_TESTS_FAILED"
    elif subject_changed:
        status = "hold"
        readiness = "STALE_SUBJECT_AFTER_NATIVE_TESTS"
    elif detections and native_plan["available"]:
        status = "pass"
        readiness = "READY_FOR_NATIVE_AND_CGQA_REVIEW"
    else:
        status = "pass"
        readiness = "READY_FOR_REVIEW_ADAPTER_REQUIRED"

    subject = {
        "rootName": root.name,
        "projectFingerprint": pre["projectFingerprint"],
        "sourceFingerprint": pre["sourceFingerprint"],
        "configurationFingerprint": pre["configurationFingerprint"],
        "git": git_before,
    }
    post_subject = {
        "projectFingerprint": post["projectFingerprint"],
        "sourceFingerprint": post["sourceFingerprint"],
        "configurationFingerprint": post["configurationFingerprint"],
        "changed": subject_changed,
        "git": git_after,
        "gitChanged": git_changed,
        "fingerprintChanged": fingerprint_changed,
    }

    capabilities = [
        {
            "capability": "Native project tests",
            "applicable": native_plan["command"] is not None,
            "status": native_result["status"],
        },
        {
            "capability": "Exact source/config subject",
            "applicable": True,
            "status": "stale" if subject_changed else "bound",
        },
        {
            "capability": "Source inventory",
            "applicable": bool(pre["sourceFiles"]),
            "status": "incomplete" if pre["skippedFiles"] else ("pass" if pre["sourceFiles"] else "blocked"),
        },
        {
            "capability": "Static review signals",
            "applicable": "solidity" in languages,
            "status": "review" if pre["reviewSignals"] else "no_signals_observed",
        },
        {
            "capability": "Deep stateful ContractGraph-QA",
            "applicable": bool(detections),
            "status": "adapter_required",
        },
    ]

    return {
        "schema": SCHEMA,
        "status": status,
        "readiness": readiness,
        "subject": subject,
        "postNativeSubject": post_subject,
        "targetRoot": str(root),
        "primary": primary,
        "detections": detections,
        "languages": languages,
        "sourceFiles": pre["sourceFiles"],
        "configurationFiles": pre["configurationFiles"],
        "skippedOversizedOrUnreadable": pre["skippedFiles"],
        "declarations": pre["declarations"],
        "reviewSignals": pre["reviewSignals"],
        "nativePlan": native_plan,
        "nativeResult": native_result,
        "capabilityPlan": capabilities,
        "nextSteps": _next_steps(primary["framework"], native_plan, bool(pre["declarations"])),
        "securityVerdictAuthorized": False,
        "claimBoundary": (
            "Quickstart performs local project/config discovery, exact-subject binding, review-signal "
            "extraction, and optional native tests. Review signals are not vulnerabilities, native "
            "test success is not a security proof, and deep stateful CGQA still requires a reviewed "
            "model/adapter. Native tests use a sanitized environment unless --inherit-env is explicit."
        ),
    }


def _render_markdown(result: dict[str, Any]) -> str:
    primary = result["primary"]
    lines = [
        "# ContractGraph-QA Quickstart",
        "",
        f"- Status: `{result['status']}`",
        f"- Readiness: `{result['readiness']}`",
        f"- Framework: `{primary['framework']}`",
        f"- Ecosystem: `{primary['ecosystem']}`",
        f"- Project root: `{primary.get('projectRoot', '.')}`",
        f"- Project fingerprint: `{result['subject']['projectFingerprint']}`",
        f"- Source fingerprint: `{result['subject']['sourceFingerprint']}`",
        f"- Configuration fingerprint: `{result['subject']['configurationFingerprint']}`",
        f"- Source files: `{len(result['sourceFiles'])}`",
        f"- Configuration files: `{len(result['configurationFiles'])}`",
        f"- Contract/program declarations: `{len(result['declarations'])}`",
        f"- Review signals: `{len(result['reviewSignals'])}`",
        "",
        "## Exact subject",
        "",
        f"- Post-native changed: `{result['postNativeSubject']['changed']}`",
        f"- Post-native project fingerprint: `{result['postNativeSubject']['projectFingerprint']}`",
        f"- Git commit: `{result['subject']['git'].get('commit')}`",
        f"- Git dirty: `{result['subject']['git'].get('dirty')}`",
        "",
        "## Detected declarations",
        "",
    ]
    if result["declarations"]:
        for row in result["declarations"]:
            lines.append(f"- `{row['kind']} {row['name']}` — `{row['path']}:{row['line']}`")
    else:
        lines.append("- None detected.")

    lines.extend(["", "## Review signals", ""])
    if result["reviewSignals"]:
        for row in result["reviewSignals"]:
            lines.append(
                f"- **{row['id']}** ({row['severity']}) — "
                f"`{row['path']}:{row['line']}` — {row['description']}"
            )
    else:
        lines.append("- No configured source review signals were observed.")

    lines.extend(["", "## Native test plan", ""])
    command = result["nativePlan"].get("command")
    lines.append(f"- Available: `{result['nativePlan']['available']}`")
    lines.append(f"- Working directory: `{result['nativePlan'].get('projectRoot', '.')}`")
    lines.append(f"- Command: `{command if command is not None else 'not available'}`")
    lines.append(f"- Environment policy: `{result['nativeResult']['environmentPolicy']}`")
    lines.append(f"- Execution result: `{result['nativeResult']['status']}`")

    if result["skippedOversizedOrUnreadable"]:
        lines.extend(["", "## Incomplete inventory", ""])
        for row in result["skippedOversizedOrUnreadable"]:
            lines.append(f"- `{row['path']}` — `{row['reason']}`")

    lines.extend(["", "## Next steps", ""])
    for step in result["nextSteps"]:
        lines.append(f"1. {step}")
    lines.extend(["", "## Claim boundary", "", result["claimBoundary"], ""])
    return "\n".join(lines)


def _write_stage(destination: Path, result: dict[str, Any]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.cgqa-stage-",
            dir=str(destination.parent),
        )
    )
    try:
        native = result["nativeResult"]
        stdout = str(native.pop("stdout", ""))
        stderr = str(native.pop("stderr", ""))
        if native["requested"]:
            stdout_path = stage / "native.stdout.log"
            stderr_path = stage / "native.stderr.log"
            stdout_path.write_text(stdout, encoding="utf-8")
            stderr_path.write_text(stderr, encoding="utf-8")
            native["stdoutLog"] = stdout_path.name
            native["stderrLog"] = stderr_path.name
            native["stdoutSha256"] = _sha256_bytes(stdout.encode("utf-8"))
            native["stderrSha256"] = _sha256_bytes(stderr.encode("utf-8"))
        result["outputDirectory"] = str(destination)
        (stage / "quickstart.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (stage / "REPORT.md").write_text(_render_markdown(result), encoding="utf-8")
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _install_stage(stage: Path, destination: Path, *, force: bool, root: Path) -> None:
    if not destination.exists():
        stage.rename(destination)
        return
    _require(force, f"output directory already exists: {destination}; use --force to replace it")
    _require(
        _is_inside(destination, root),
        "--force may only replace an output directory inside the target project",
    )
    backup = destination.with_name(f".{destination.name}.cgqa-backup")
    _require(not backup.exists(), f"temporary backup path already exists: {backup}")
    destination.rename(backup)
    try:
        stage.rename(destination)
    except Exception:
        backup.rename(destination)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def write_quickstart(
    target: Path,
    *,
    output_directory: Path | None = None,
    run_native: bool = False,
    force: bool = False,
    timeout_seconds: int = 300,
    inherit_environment: bool = False,
) -> dict[str, Any]:
    root = target.expanduser().resolve()
    destination = (
        output_directory.expanduser().resolve()
        if output_directory is not None
        else (root / ".cgqa" / "quickstart").resolve()
    )
    _require(destination != root, "output directory must not equal the target project root")
    if destination.exists() and not force:
        raise ProjectQuickstartError(
            f"output directory already exists: {destination}; use --force to replace it"
        )
    if destination.exists() and force:
        _require(
            _is_inside(destination, root),
            "--force may only replace an output directory inside the target project",
        )

    result = inspect_project(
        root,
        output_directory=destination,
        run_native=run_native,
        timeout_seconds=timeout_seconds,
        inherit_environment=inherit_environment,
    )
    stage = _write_stage(destination, result)
    try:
        _install_stage(stage, destination, force=force, root=root)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    return {
        "ok": result["status"] == "pass",
        "status": result["status"],
        "readiness": result["readiness"],
        "projectFingerprint": result["subject"]["projectFingerprint"],
        "sourceFingerprint": result["subject"]["sourceFingerprint"],
        "configurationFingerprint": result["subject"]["configurationFingerprint"],
        "subjectChangedAfterNative": result["postNativeSubject"]["changed"],
        "framework": result["primary"]["framework"],
        "projectRoot": result["primary"].get("projectRoot", "."),
        "sourceFiles": len(result["sourceFiles"]),
        "configurationFiles": len(result["configurationFiles"]),
        "declarations": len(result["declarations"]),
        "reviewSignals": len(result["reviewSignals"]),
        "nativeTestStatus": result["nativeResult"]["status"],
        "outputDirectory": str(destination),
        "result": str(destination / "quickstart.json"),
        "report": str(destination / "REPORT.md"),
    }
