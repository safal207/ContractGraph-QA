"""Fail-closed client engagement scaffold generation."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

SAFE_ENGAGEMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ScaffoldError(RuntimeError):
    """Expected engagement scaffold generation failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScaffoldError(message)


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _manifest(name: str) -> str:
    data = {
        "schemaVersion": 1,
        "adapterId": f"{name}-adapter",
        "contract": "TODO_Contract",
        "network": "TODO_authorized_network",
        "scope": {
            "scopeId": f"{name}-scope",
            "authorization": "TODO: record explicit authorization or safe-harbor scope before execution.",
            "authorizationReference": "TODO_authorization_reference",
            "target": "TODO_authorized_target",
        },
        "search": {"maxDepth": 4},
        "stateFields": ["TODO_future_relevant_state"],
        "actions": [
            {
                "id": "TODO_action",
                "display": "TODO_action()",
                "actor": "TODO_authorized_actor",
            }
        ],
        "invariants": [
            {
                "id": "TODO_invariant",
                "title": "TODO invariant title",
                "severity": "info",
                "summary": "TODO describe the property being checked.",
                "expression": "TODO_boolean_expression == true",
                "impact": "TODO describe the impact if this invariant is violated.",
                "recommendation": "TODO describe the remediation or regression expectation.",
            }
        ],
    }
    return _json(data)


def _config(working_directory: str) -> str:
    normalized = working_directory.replace("\\", "/")
    return f"""schemaVersion = 1
workingDirectory = "{normalized}"
manifest = "manifest.json"
result = "generated/engagement-result.json"
outputDirectory = "dist"
bundle = "dist/engagement.evidence.zip"

[capture]
profile = "capture"
test = "test_ClientEngagementCapture"
verbosity = 3
"""


def _capture_template(name: str) -> str:
    return f"""// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

// ContractGraph-QA engagement scaffold: {name}
//
// This file is intentionally named `.example`, so Foundry does not compile it.
// Copy or rename it to `ClientEngagementCapture.t.sol` only after the TODOs below
// are reviewed against an explicitly authorized target or repository-owned fixture.
//
// Implementation checklist:
// 1. Bind the authorized local/fork target and fixed block when applicable.
// 2. Define the finite action/parameter/time corpus.
// 3. Implement deterministic reset/replay semantics.
// 4. Define a complete future-relevant state hash for deduplication.
// 5. Implement every manifest invariant with Holds / Violated / Inconclusive semantics.
// 6. Run one MultiInvariantStateExplorerHarness search session.
// 7. Convert every outcome into EngagementCheckCapture evidence.
// 8. Write the result with DirectEngagementCaptureHarness.
//
// Reference repository examples:
// - capture-test/EngagementFixtureCapture.t.sol
// - src/harness/MultiInvariantStateExplorerHarness.sol
// - src/harness/DirectEngagementCaptureHarness.sol
// - src/harness/ForkAdapterTemplate.sol

contract ClientEngagementCaptureTest {{
    function test_ClientEngagementCapture() public pure {{
        revert("CGQA scaffold not configured");
    }}
}}
"""


def _readme(name: str) -> str:
    return f"""# ContractGraph-QA engagement: `{name}`

This directory is a **fail-closed scaffold**, not completed evidence.

## Causal objective

Reduce the time from an authorized client scope to the first reproducible QA engagement without weakening evidence semantics.

## Before the first run

1. Replace every `TODO` in `manifest.json` with reviewed engagement facts.
2. Record explicit authorization / safe-harbor scope and the exact target.
3. Define the action corpus, actors, parameters/time inputs, and all future-relevant state fields.
4. Define invariants as observable properties with clear impact and remediation.
5. Copy `capture/ClientEngagementCapture.t.sol.example` to `capture/ClientEngagementCapture.t.sol` and implement the adapter/search/capture hooks.
6. Review `_multiStateHash()` as carefully as the invariants; incomplete state equivalence can make pruning unsound.
7. Keep `not_found_within_bound` bounded and keep unresolved evidence `inconclusive`.

## Run

From the ContractGraph-QA project root, point `engagement-run` at this directory's config:

```bash
cgqa engagement-run --config <scaffold-directory>/cgqa.toml
```

## Generated evidence

`generated/` and `dist/` are ignored by Git. A successful run produces a fresh engagement result, coverage summary, zero or more findings, deterministic Markdown, and a deterministic evidence ZIP that is re-opened and independently verified before success is returned.

## Safety boundary

A public contract address is not authorization. Do not use this scaffold against third-party production targets unless the engagement is explicitly authorized or covered by a clearly applicable safe-harbor / bounty scope.
"""


def _gitignore() -> str:
    return "generated/\ndist/\n"


def init_engagement(name: str, directory: Path | None = None) -> dict[str, Any]:
    _require(
        isinstance(name, str) and bool(SAFE_ENGAGEMENT_NAME.fullmatch(name)),
        "engagement name must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}",
    )

    project_root = Path.cwd().resolve()
    destination = (
        directory.expanduser().resolve()
        if directory is not None
        else (project_root / "engagements" / name).resolve()
    )
    _require(
        _is_within(destination, project_root) and destination != project_root,
        "scaffold destination must be a new directory inside the current project root",
    )
    _require(not destination.exists(), f"scaffold destination already exists: {destination}")

    working_directory = os.path.relpath(project_root, destination)
    files = {
        "manifest.json": _manifest(name),
        "cgqa.toml": _config(working_directory),
        "capture/ClientEngagementCapture.t.sol.example": _capture_template(name),
        "README.md": _readme(name),
        ".gitignore": _gitignore(),
    }

    created = False
    try:
        destination.mkdir(parents=True, exist_ok=False)
        created = True
        for relative, content in files.items():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    except OSError as exc:
        if created:
            shutil.rmtree(destination, ignore_errors=True)
        raise ScaffoldError(f"failed to create engagement scaffold: {exc}") from exc

    return {
        "ok": True,
        "name": name,
        "directory": str(destination),
        "files": sorted(files),
        "executionReady": False,
        "next": "replace TODOs, implement the capture adapter, then run cgqa engagement-run",
    }
