"""Strict Foundry harness-receipt binding into a bounded TSSE trace."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.tsse_adapters.common import (
    ToolCaptureError,
    _array,
    _strict_object,
    _text,
    adapt_dynamic_capture,
    build_native_bindings,
    canonical_sha256,
    executable_basename,
    incoming_actions,
    parse_json_bytes,
    primary_artifact,
    require_completed_run,
)


FOUNDRY_RECEIPT_SCHEMA = "cgqa/foundry-replay-observation/v0.1"
FOUNDRY_RECEIPT_KEYS = {"schema", "status", "test", "steps"}
FOUNDRY_EXECUTABLES = frozenset({"forge", "forge.exe"})


def _selected_test(argv: list[str]) -> str:
    selections: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in {"--match-test", "--mt"}:
            if index + 1 >= len(argv):
                raise ToolCaptureError(f"{argument} requires a test value")
            selections.append(_text(argv[index + 1], f"argv[{index + 1}]"))
            index += 2
            continue
        for prefix in ("--match-test=", "--mt="):
            if argument.startswith(prefix):
                selections.append(_text(argument[len(prefix) :], f"argv[{index}]"))
                break
        index += 1
    if len(selections) != 1:
        raise ToolCaptureError(
            "Foundry argv must select exactly one test with --match-test or --mt"
        )
    return selections[0]


def adapt_foundry_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Parse and bind one stable CGQA Foundry replay receipt."""

    if capture["tool"] != "foundry":
        raise ToolCaptureError(
            f"Foundry adapter cannot process tool {capture['tool']!r}"
        )
    require_completed_run(capture, tool="Foundry")
    if capture["run"]["exitCode"] != 0:
        raise ToolCaptureError("Foundry replay binding requires exitCode 0")
    executable = executable_basename(capture)
    if executable not in FOUNDRY_EXECUTABLES:
        raise ToolCaptureError("Foundry argv[0] must be forge or forge.exe")
    if len(capture["run"]["argv"]) < 2 or capture["run"]["argv"][1] != "test":
        raise ToolCaptureError("Foundry argv must invoke the forge test subcommand")

    artifact, raw = primary_artifact(capture, verified)
    receipt = _strict_object(
        parse_json_bytes(raw, f"Foundry artifact {artifact['path']}"),
        "foundryReceipt",
        keys=FOUNDRY_RECEIPT_KEYS,
    )
    if receipt["schema"] != FOUNDRY_RECEIPT_SCHEMA:
        raise ToolCaptureError(
            f"foundryReceipt.schema must equal {FOUNDRY_RECEIPT_SCHEMA!r}"
        )
    if receipt["status"] != "observed":
        raise ToolCaptureError("foundryReceipt.status must equal 'observed'")
    receipt_test = _text(receipt["test"], "foundryReceipt.test")
    if receipt_test != _selected_test(capture["run"]["argv"]):
        raise ToolCaptureError(
            "Foundry receipt test does not match the recorded argv test selection"
        )
    raw_steps = _array(receipt["steps"], "foundryReceipt.steps", non_empty=True)
    steps = [
        _text(item, f"foundryReceipt.steps[{index}]")
        for index, item in enumerate(raw_steps)
    ]
    actions = incoming_actions(capture)
    if steps != actions:
        raise ToolCaptureError(
            "Foundry receipt steps do not exactly match reviewed observation actions"
        )
    for observation in capture["observations"][1:]:
        if artifact["id"] not in observation["incoming"]["evidenceRefs"]:
            raise ToolCaptureError(
                "every Foundry transition must reference the primary replay artifact"
            )

    bindings = build_native_bindings(
        capture,
        artifact_id=artifact["id"],
        locators=[f"/steps/{index}" for index in range(len(steps))],
    )
    native_evidence = {
        "status": "bound",
        "parser": FOUNDRY_RECEIPT_SCHEMA,
        "artifactId": artifact["id"],
        "artifactDigest": artifact["digest"],
        "receiptHash": canonical_sha256(receipt),
        "test": receipt_test,
        "steps": len(steps),
    }
    return adapt_dynamic_capture(
        capture,
        profile,
        verified,
        expected_tool="foundry",
        native_bindings=bindings,
        native_evidence=native_evidence,
    )


adapt_capture = adapt_foundry_capture

__all__ = [
    "FOUNDRY_EXECUTABLES",
    "FOUNDRY_RECEIPT_KEYS",
    "FOUNDRY_RECEIPT_SCHEMA",
    "adapt_capture",
    "adapt_foundry_capture",
]
