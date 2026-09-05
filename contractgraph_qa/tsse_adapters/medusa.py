"""Strict Medusa counterexample binding into a bounded TSSE trace."""

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
    function_base,
    incoming_actions,
    parse_json_bytes,
    primary_artifact,
    require_completed_run,
)


MEDUSA_RECEIPT_SCHEMA = "cgqa/medusa-counterexample/v0.1"
MEDUSA_RECEIPT_KEYS = {"schema", "status", "test", "seed", "sequence"}
MEDUSA_SEQUENCE_KEYS = {"contract", "function", "sender", "value"}
MEDUSA_EXECUTABLES = frozenset({"medusa", "medusa.exe"})


def _transaction_value(value: object, field: str) -> str | int:
    if isinstance(value, bool):
        raise ToolCaptureError(f"{field} must be a non-negative integer or string")
    if isinstance(value, int):
        if value < 0:
            raise ToolCaptureError(f"{field} must be non-negative")
        return value
    return _text(value, field)


def adapt_medusa_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Parse and bind one stable CGQA Medusa corpus counterexample receipt."""

    if capture["tool"] != "medusa":
        raise ToolCaptureError(
            f"Medusa adapter cannot process tool {capture['tool']!r}"
        )
    require_completed_run(capture, tool="Medusa")
    if executable_basename(capture) not in MEDUSA_EXECUTABLES:
        raise ToolCaptureError("Medusa argv[0] must be medusa or medusa.exe")
    if len(capture["run"]["argv"]) < 2 or capture["run"]["argv"][1] != "fuzz":
        raise ToolCaptureError("Medusa argv must invoke the fuzz subcommand")

    artifact, raw = primary_artifact(capture, verified)
    receipt = _strict_object(
        parse_json_bytes(raw, f"Medusa artifact {artifact['path']}"),
        "medusaReceipt",
        keys=MEDUSA_RECEIPT_KEYS,
    )
    if receipt["schema"] != MEDUSA_RECEIPT_SCHEMA:
        raise ToolCaptureError(
            f"medusaReceipt.schema must equal {MEDUSA_RECEIPT_SCHEMA!r}"
        )
    if receipt["status"] != "failed":
        raise ToolCaptureError("medusaReceipt.status must equal 'failed'")
    test = _text(receipt["test"], "medusaReceipt.test")
    seed = receipt["seed"]
    if seed is None:
        raise ToolCaptureError("medusaReceipt.seed must be recorded")
    seed = _text(seed, "medusaReceipt.seed")
    if seed != capture["run"]["seed"]:
        raise ToolCaptureError(
            "Medusa counterexample seed does not match the recorded run seed"
        )

    sequence = _array(receipt["sequence"], "medusaReceipt.sequence", non_empty=True)
    functions: list[str] = []
    for index, raw_transaction in enumerate(sequence):
        field = f"medusaReceipt.sequence[{index}]"
        transaction = _strict_object(
            raw_transaction,
            field,
            keys=MEDUSA_SEQUENCE_KEYS,
        )
        contract = _text(transaction["contract"], f"{field}.contract")
        observed_contract = capture["observations"][index + 1]["space"]["contract"]
        if contract != observed_contract:
            raise ToolCaptureError(
                f"{field}.contract does not match the reviewed observation space"
            )
        functions.append(function_base(transaction["function"], f"{field}.function"))
        _text(transaction["sender"], f"{field}.sender")
        _transaction_value(transaction["value"], f"{field}.value")

    actions = incoming_actions(capture)
    if functions != actions:
        raise ToolCaptureError(
            "Medusa counterexample functions do not match observation actions"
        )
    maximum = capture["run"]["bounds"]["maxSequenceLength"]
    if maximum is not None and len(sequence) > maximum:
        raise ToolCaptureError(
            "Medusa counterexample sequence exceeds maxSequenceLength"
        )
    for observation in capture["observations"][1:]:
        if artifact["id"] not in observation["incoming"]["evidenceRefs"]:
            raise ToolCaptureError(
                "every Medusa transition must reference the primary counterexample artifact"
            )

    bindings = build_native_bindings(
        capture,
        artifact_id=artifact["id"],
        locators=[f"/sequence/{index}" for index in range(len(sequence))],
    )
    native_evidence = {
        "status": "bound",
        "parser": MEDUSA_RECEIPT_SCHEMA,
        "artifactId": artifact["id"],
        "artifactDigest": artifact["digest"],
        "receiptHash": canonical_sha256(receipt),
        "seed": seed,
        "test": test,
        "transactions": len(sequence),
    }
    return adapt_dynamic_capture(
        capture,
        profile,
        verified,
        expected_tool="medusa",
        native_bindings=bindings,
        native_evidence=native_evidence,
    )


adapt_capture = adapt_medusa_capture

__all__ = [
    "MEDUSA_EXECUTABLES",
    "MEDUSA_RECEIPT_KEYS",
    "MEDUSA_RECEIPT_SCHEMA",
    "MEDUSA_SEQUENCE_KEYS",
    "adapt_capture",
    "adapt_medusa_capture",
]
