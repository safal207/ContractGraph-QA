"""Strict Echidna campaign binding into a bounded TSSE trace."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.tsse_adapters.common import (
    ToolCaptureError,
    _array,
    _integer,
    _json_value,
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


ECHIDNA_OUTPUT_KEYS = {"success", "error", "tests", "seed", "coverage"}
ECHIDNA_TEST_KEYS = {
    "contract",
    "name",
    "status",
    "error",
    "testType",
    "transactions",
}
ECHIDNA_TRANSACTION_KEYS = {
    "contract",
    "function",
    "arguments",
    "gas",
    "gasprice",
}
ECHIDNA_EXECUTABLES = frozenset({"echidna", "echidna.exe", "echidna-test"})


def _requests_json(argv: list[str]) -> bool:
    for index, argument in enumerate(argv):
        if argument == "--format" and index + 1 < len(argv):
            if argv[index + 1].lower() == "json":
                return True
        if argument.lower() == "--format=json":
            return True
    return False


def _seed_string(value: object, field: str) -> str:
    if isinstance(value, bool):
        raise ToolCaptureError(f"{field} must be a decimal integer or string")
    if isinstance(value, int):
        if value < 0:
            raise ToolCaptureError(f"{field} must be non-negative")
        return str(value)
    text = _text(value, field)
    if not text.isdecimal():
        raise ToolCaptureError(f"{field} must be a decimal seed")
    return text


def adapt_echidna_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Parse one completed official Echidna campaign with one solved path."""

    if capture["tool"] != "echidna":
        raise ToolCaptureError(
            f"Echidna adapter cannot process tool {capture['tool']!r}"
        )
    require_completed_run(capture, tool="Echidna")
    if executable_basename(capture) not in ECHIDNA_EXECUTABLES:
        raise ToolCaptureError("Echidna argv[0] must identify the Echidna executable")
    if not _requests_json(capture["run"]["argv"]):
        raise ToolCaptureError("Echidna argv must request JSON output with --format json")

    artifact, raw = primary_artifact(capture, verified)
    campaign = _strict_object(
        parse_json_bytes(raw, f"Echidna artifact {artifact['path']}"),
        "echidnaCampaign",
        keys=ECHIDNA_OUTPUT_KEYS,
    )
    if campaign["success"] is not True:
        raise ToolCaptureError("Echidna campaign success must be true")
    if campaign["error"] is not None:
        raise ToolCaptureError("Echidna campaign error must be null")
    campaign_seed = _seed_string(campaign["seed"], "echidnaCampaign.seed")
    if capture["run"]["seed"] != campaign_seed:
        raise ToolCaptureError(
            "Echidna campaign seed does not match the recorded run seed"
        )
    _json_value(campaign["coverage"], "echidnaCampaign.coverage")

    raw_tests = _array(campaign["tests"], "echidnaCampaign.tests", non_empty=True)
    parsed_tests: list[dict[str, Any]] = []
    solved: list[tuple[int, dict[str, Any]]] = []
    for test_index, raw_test in enumerate(raw_tests):
        field = f"echidnaCampaign.tests[{test_index}]"
        test = _strict_object(raw_test, field, keys=ECHIDNA_TEST_KEYS)
        for key in ("contract", "name", "status", "testType"):
            _text(test[key], f"{field}.{key}")
        if test["error"] is not None:
            _text(test["error"], f"{field}.error")
        transactions = test["transactions"]
        if transactions is not None and not isinstance(transactions, list):
            raise ToolCaptureError(f"{field}.transactions must be an array or null")
        parsed_tests.append(test)
        if test["status"] == "solved":
            solved.append((test_index, test))
    if len(solved) != 1:
        raise ToolCaptureError(
            "Echidna campaign must contain exactly one solved test"
        )

    solved_index, solved_test = solved[0]
    if solved_test["error"] is not None:
        raise ToolCaptureError("the solved Echidna test error must be null")
    transactions = _array(
        solved_test["transactions"],
        f"echidnaCampaign.tests[{solved_index}].transactions",
        non_empty=True,
    )
    functions: list[str] = []
    for transaction_index, raw_transaction in enumerate(transactions):
        field = (
            f"echidnaCampaign.tests[{solved_index}].transactions"
            f"[{transaction_index}]"
        )
        transaction = _strict_object(
            raw_transaction,
            field,
            keys=ECHIDNA_TRANSACTION_KEYS,
        )
        contract = _text(transaction["contract"], f"{field}.contract")
        observed_contract = capture["observations"][transaction_index + 1]["space"][
            "contract"
        ]
        if contract != observed_contract:
            raise ToolCaptureError(
                f"{field}.contract does not match the reviewed observation space"
            )
        functions.append(function_base(transaction["function"], f"{field}.function"))
        raw_arguments = transaction["arguments"]
        arguments = (
            []
            if raw_arguments is None
            else _array(raw_arguments, f"{field}.arguments")
        )
        for argument_index, argument in enumerate(arguments):
            _text(argument, f"{field}.arguments[{argument_index}]")
        _integer(transaction["gas"], f"{field}.gas", non_negative=True)
        _integer(transaction["gasprice"], f"{field}.gasprice", non_negative=True)

    actions = incoming_actions(capture)
    if functions != actions:
        raise ToolCaptureError(
            "Echidna solved transaction functions do not match observation actions"
        )
    maximum = capture["run"]["bounds"]["maxSequenceLength"]
    if maximum is None:
        raise ToolCaptureError(
            "Echidna native binding requires maxSequenceLength"
        )
    if len(transactions) > maximum:
        raise ToolCaptureError(
            "Echidna solved transaction sequence exceeds maxSequenceLength"
        )
    for observation in capture["observations"][1:]:
        if artifact["id"] not in observation["incoming"]["evidenceRefs"]:
            raise ToolCaptureError(
                "every Echidna transition must reference the primary campaign artifact"
            )

    bindings = build_native_bindings(
        capture,
        artifact_id=artifact["id"],
        locators=[
            f"/tests/{solved_index}/transactions/{index}"
            for index in range(len(transactions))
        ],
    )
    native_evidence = {
        "status": "bound",
        "parser": "echidna-campaign-json/v0.1",
        "artifactId": artifact["id"],
        "artifactDigest": artifact["digest"],
        "campaignHash": canonical_sha256(campaign),
        "seed": campaign_seed,
        "test": {
            "contract": solved_test["contract"],
            "name": solved_test["name"],
            "testType": solved_test["testType"],
        },
        "transactions": len(transactions),
    }
    return adapt_dynamic_capture(
        capture,
        profile,
        verified,
        expected_tool="echidna",
        native_bindings=bindings,
        native_evidence=native_evidence,
    )


adapt_capture = adapt_echidna_capture

__all__ = [
    "ECHIDNA_EXECUTABLES",
    "ECHIDNA_OUTPUT_KEYS",
    "ECHIDNA_TEST_KEYS",
    "ECHIDNA_TRANSACTION_KEYS",
    "adapt_capture",
    "adapt_echidna_capture",
]
