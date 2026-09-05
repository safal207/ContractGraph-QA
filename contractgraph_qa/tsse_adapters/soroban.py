"""Strict Cargo/Soroban transition-receipt binding into a bounded TSSE trace."""

from __future__ import annotations

from typing import Any

from contractgraph_qa.tsse_adapters.common import (
    ENVIRONMENT_HASH_DOMAIN,
    STATE_HASH_DOMAIN,
    ToolCaptureError,
    _array,
    _digest,
    _integer,
    _strict_object,
    _text,
    adapt_dynamic_capture,
    build_native_bindings,
    canonical_result_hash,
    canonical_sha256,
    executable_basename,
    parse_json_bytes,
    primary_artifact,
    require_completed_run,
)


SOROBAN_RECEIPT_SCHEMA = "cgqa/cargo-soroban-transition-receipt/v0.1"
SOROBAN_RECEIPT_KEYS = {
    "schema",
    "status",
    "framework",
    "package",
    "test",
    "seed",
    "subjectBundleHash",
    "execution",
    "steps",
}
SOROBAN_EXECUTION_KEYS = {"matched", "passed", "failed", "ignored"}
SOROBAN_STEP_KEYS = {
    "observationId",
    "action",
    "time",
    "space",
    "state",
    "environmentHash",
    "actor",
    "authority",
    "value",
    "snapshotArtifactId",
    "snapshotDigest",
}
SOROBAN_TIME_KEYS = {"ledgerSequence", "ledgerTimestamp", "epoch"}
SOROBAN_SPACE_KEYS = {
    "network",
    "contract",
    "callFrame",
    "storageDomain",
    "protocolLocation",
}
SOROBAN_STATE_KEYS = {"phase", "stateHash"}
SOROBAN_ACTOR_KEYS = {"identity", "role"}
SOROBAN_AUTHORITY_KEYS = {"epoch", "status"}
SOROBAN_VALUE_KEYS = {"unit", "locked", "moved"}
SOROBAN_SNAPSHOT_KIND = "soroban-state-snapshot"
CARGO_EXECUTABLES = frozenset({"cargo", "cargo.exe"})

_CARGO_FLAG_OPTIONS = frozenset(
    {
        "--all-features",
        "--frozen",
        "--ignore-rust-version",
        "--lib",
        "--no-default-features",
        "--offline",
        "--quiet",
        "--release",
        "-q",
    }
)
_CARGO_VALUE_OPTIONS = frozenset(
    {
        "--color",
        "--features",
        "--jobs",
        "--manifest-path",
        "--profile",
        "--target",
        "-j",
    }
)
_HARNESS_FLAG_OPTIONS = frozenset(
    {"--exact", "--include-ignored", "--ignored", "--nocapture", "--show-output"}
)


def _command_value(value: object, field: str) -> str:
    text = _text(value, field)
    if text.startswith("-") or any(character.isspace() for character in text):
        raise ToolCaptureError(f"{field} must be one non-option command token")
    return text


def _selected_package_and_test(argv: list[str]) -> tuple[str, str]:
    """Parse the one canonical Cargo package and exact test selection."""

    separators = [index for index, argument in enumerate(argv) if argument == "--"]
    if len(separators) != 1:
        raise ToolCaptureError("Cargo/Soroban argv must contain exactly one '--' separator")
    separator = separators[0]
    if separator < 4:
        raise ToolCaptureError("Cargo/Soroban argv is missing its package or test selection")

    packages: list[str] = []
    tests: list[str] = []
    locked_count = 0
    arguments = argv[2:separator]
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        field = f"capture.run.argv[{index + 2}]"
        if argument == "--locked":
            locked_count += 1
            index += 1
            continue
        if argument in {"-p", "--package"}:
            if index + 1 >= len(arguments):
                raise ToolCaptureError(f"{argument} requires a package value")
            packages.append(
                _command_value(arguments[index + 1], f"capture.run.argv[{index + 3}]")
            )
            index += 2
            continue
        if argument.startswith("--package="):
            packages.append(_command_value(argument.split("=", 1)[1], field))
            index += 1
            continue
        if argument in _CARGO_FLAG_OPTIONS:
            index += 1
            continue
        if argument in _CARGO_VALUE_OPTIONS:
            if index + 1 >= len(arguments):
                raise ToolCaptureError(f"{argument} requires a value")
            value = _text(arguments[index + 1], f"capture.run.argv[{index + 3}]")
            if argument in {"-j", "--jobs"} and value != "1":
                raise ToolCaptureError("Cargo/Soroban --jobs must equal 1")
            index += 2
            continue
        matched_value_option = next(
            (
                option
                for option in _CARGO_VALUE_OPTIONS
                if option.startswith("--") and argument.startswith(option + "=")
            ),
            None,
        )
        if matched_value_option is not None:
            value = _text(argument.split("=", 1)[1], field)
            if matched_value_option == "--jobs" and value != "1":
                raise ToolCaptureError("Cargo/Soroban --jobs must equal 1")
            index += 1
            continue
        if argument.startswith("-"):
            raise ToolCaptureError(
                f"Cargo/Soroban argv contains unsupported option {argument!r}"
            )
        tests.append(_command_value(argument, field))
        index += 1

    if locked_count != 1:
        raise ToolCaptureError("Cargo/Soroban argv must contain --locked exactly once")
    if len(packages) != 1:
        raise ToolCaptureError(
            "Cargo/Soroban argv must select exactly one package with -p or --package"
        )
    if len(tests) != 1:
        raise ToolCaptureError(
            "Cargo/Soroban argv must select exactly one positional test filter"
        )

    harness = argv[separator + 1 :]
    exact_count = 0
    index = 0
    while index < len(harness):
        argument = harness[index]
        field = f"capture.run.argv[{separator + 1 + index}]"
        if argument in _HARNESS_FLAG_OPTIONS:
            if argument == "--exact":
                exact_count += 1
            index += 1
            continue
        if argument == "--test-threads":
            if index + 1 >= len(harness):
                raise ToolCaptureError("--test-threads requires a value")
            value = _text(
                harness[index + 1],
                f"capture.run.argv[{separator + 2 + index}]",
            )
            if value != "1":
                raise ToolCaptureError("Cargo/Soroban --test-threads must equal 1")
            index += 2
            continue
        if argument.startswith("--test-threads="):
            if _text(argument.split("=", 1)[1], field) != "1":
                raise ToolCaptureError("Cargo/Soroban --test-threads must equal 1")
            index += 1
            continue
        raise ToolCaptureError(
            f"Cargo/Soroban test harness contains unsupported option {argument!r}"
        )
    if exact_count != 1:
        raise ToolCaptureError(
            "Cargo/Soroban test harness must contain --exact exactly once"
        )
    return packages[0], tests[0]


def _require_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected or type(actual) is not type(expected):
        raise ToolCaptureError(f"{field} does not match the reviewed observation")


def _bind_step(
    raw_step: object,
    *,
    index: int,
    observation: dict[str, Any],
    primary_id: str,
    artifact_by_id: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    field = f"sorobanReceipt.steps[{index}]"
    step = _strict_object(raw_step, field, keys=SOROBAN_STEP_KEYS)
    observation_id = _text(step["observationId"], f"{field}.observationId")
    _require_equal(observation_id, observation["id"], f"{field}.observationId")
    action = _text(step["action"], f"{field}.action")
    _require_equal(action, observation["incoming"]["action"], f"{field}.action")

    step_time = _strict_object(step["time"], f"{field}.time", keys=SOROBAN_TIME_KEYS)
    for receipt_key, observation_key in (
        ("ledgerSequence", "block"),
        ("ledgerTimestamp", "timestamp"),
        ("epoch", "epoch"),
    ):
        value = _integer(
            step_time[receipt_key],
            f"{field}.time.{receipt_key}",
            non_negative=True,
        )
        _require_equal(value, observation["time"][observation_key], f"{field}.time.{receipt_key}")

    step_space = _strict_object(
        step["space"], f"{field}.space", keys=SOROBAN_SPACE_KEYS
    )
    for receipt_key, observation_key in (
        ("network", "chainId"),
        ("contract", "contract"),
        ("callFrame", "callFrame"),
        ("storageDomain", "storageDomain"),
        ("protocolLocation", "protocolLocation"),
    ):
        value = _text(step_space[receipt_key], f"{field}.space.{receipt_key}")
        _require_equal(value, observation["space"][observation_key], f"{field}.space.{receipt_key}")

    step_state = _strict_object(
        step["state"], f"{field}.state", keys=SOROBAN_STATE_KEYS
    )
    phase = _text(step_state["phase"], f"{field}.state.phase")
    _require_equal(phase, observation["state"]["phase"], f"{field}.state.phase")
    state_hash = _digest(step_state["stateHash"], f"{field}.state.stateHash")
    expected_state_hash = canonical_sha256(
        {
            "domain": STATE_HASH_DOMAIN,
            "phase": observation["state"]["phase"],
            "values": observation["state"]["values"],
        }
    )
    _require_equal(state_hash, expected_state_hash, f"{field}.state.stateHash")

    environment_hash = _digest(step["environmentHash"], f"{field}.environmentHash")
    expected_environment_hash = canonical_sha256(
        {
            "domain": ENVIRONMENT_HASH_DOMAIN,
            "environment": observation["environment"],
        }
    )
    _require_equal(
        environment_hash,
        expected_environment_hash,
        f"{field}.environmentHash",
    )

    step_actor = _strict_object(
        step["actor"], f"{field}.actor", keys=SOROBAN_ACTOR_KEYS
    )
    for key in sorted(SOROBAN_ACTOR_KEYS):
        value = _text(step_actor[key], f"{field}.actor.{key}")
        _require_equal(value, observation["actor"][key], f"{field}.actor.{key}")

    step_authority = _strict_object(
        step["authority"], f"{field}.authority", keys=SOROBAN_AUTHORITY_KEYS
    )
    authority_epoch = _integer(
        step_authority["epoch"], f"{field}.authority.epoch", non_negative=True
    )
    _require_equal(
        authority_epoch,
        observation["authority"]["epoch"],
        f"{field}.authority.epoch",
    )
    authority_status = _text(
        step_authority["status"], f"{field}.authority.status"
    )
    _require_equal(
        authority_status,
        observation["authority"]["status"],
        f"{field}.authority.status",
    )

    step_value = _strict_object(
        step["value"], f"{field}.value", keys=SOROBAN_VALUE_KEYS
    )
    unit = _text(step_value["unit"], f"{field}.value.unit")
    _require_equal(unit, observation["value"]["unit"], f"{field}.value.unit")
    for key in ("locked", "moved"):
        value = _integer(step_value[key], f"{field}.value.{key}", non_negative=True)
        _require_equal(value, observation["value"][key], f"{field}.value.{key}")

    snapshot_id = _text(step["snapshotArtifactId"], f"{field}.snapshotArtifactId")
    snapshot_digest = _digest(step["snapshotDigest"], f"{field}.snapshotDigest")
    snapshot = artifact_by_id.get(snapshot_id)
    if snapshot is None:
        raise ToolCaptureError(
            f"{field}.snapshotArtifactId references an unknown verified artifact"
        )
    if snapshot["kind"] != SOROBAN_SNAPSHOT_KIND:
        raise ToolCaptureError(
            f"{field}.snapshotArtifactId must reference kind {SOROBAN_SNAPSHOT_KIND!r}"
        )
    if snapshot["digest"] != snapshot_digest:
        raise ToolCaptureError(f"{field}.snapshotDigest does not match the verified artifact")
    evidence_refs = set(observation["incoming"]["evidenceRefs"])
    if primary_id not in evidence_refs or snapshot_id not in evidence_refs:
        raise ToolCaptureError(
            f"{field} transition must reference both its receipt and state snapshot"
        )
    return snapshot_id, snapshot_digest


def adapt_soroban_capture(
    capture: dict[str, Any],
    profile: dict[str, Any],
    verified: dict[str, Any],
) -> dict[str, Any]:
    """Parse and bind one stable Cargo/Soroban transition receipt."""

    if capture["tool"] != "cargo-soroban":
        raise ToolCaptureError(
            f"Cargo/Soroban adapter cannot process tool {capture['tool']!r}"
        )
    require_completed_run(capture, tool="Cargo/Soroban")
    if capture["run"]["exitCode"] != 0:
        raise ToolCaptureError("Cargo/Soroban native binding requires exitCode 0")
    if executable_basename(capture) not in CARGO_EXECUTABLES:
        raise ToolCaptureError("Cargo/Soroban argv[0] must be cargo or cargo.exe")
    argv = capture["run"]["argv"]
    if len(argv) < 2 or argv[1] != "test":
        raise ToolCaptureError("Cargo/Soroban argv must invoke the cargo test subcommand")
    selected_package, selected_test = _selected_package_and_test(argv)

    bounds = capture["run"]["bounds"]
    if bounds["testLimit"] != 1:
        raise ToolCaptureError("Cargo/Soroban run.bounds.testLimit must equal 1")
    if bounds["workers"] != 1:
        raise ToolCaptureError("Cargo/Soroban run.bounds.workers must equal 1")

    artifact, raw = primary_artifact(capture, verified)
    receipt = _strict_object(
        parse_json_bytes(raw, f"Cargo/Soroban artifact {artifact['path']}"),
        "sorobanReceipt",
        keys=SOROBAN_RECEIPT_KEYS,
    )
    if receipt["schema"] != SOROBAN_RECEIPT_SCHEMA:
        raise ToolCaptureError(
            f"sorobanReceipt.schema must equal {SOROBAN_RECEIPT_SCHEMA!r}"
        )
    if receipt["status"] != "observed":
        raise ToolCaptureError("sorobanReceipt.status must equal 'observed'")
    if receipt["framework"] != "soroban":
        raise ToolCaptureError("sorobanReceipt.framework must equal 'soroban'")
    receipt_package = _command_value(receipt["package"], "sorobanReceipt.package")
    receipt_test = _command_value(receipt["test"], "sorobanReceipt.test")
    if receipt_package != selected_package:
        raise ToolCaptureError(
            "Cargo/Soroban receipt package does not match the recorded argv package"
        )
    if receipt_test != selected_test:
        raise ToolCaptureError(
            "Cargo/Soroban receipt test does not match the recorded argv test selection"
        )
    receipt_seed = receipt["seed"]
    if receipt_seed is not None:
        receipt_seed = _text(receipt_seed, "sorobanReceipt.seed")
    if receipt_seed != capture["run"]["seed"]:
        raise ToolCaptureError(
            "Cargo/Soroban receipt seed does not match the recorded run seed"
        )
    receipt_subject_bundle_hash = _digest(
        receipt["subjectBundleHash"], "sorobanReceipt.subjectBundleHash"
    )
    if receipt_subject_bundle_hash != verified["subjectBundleHash"]:
        raise ToolCaptureError(
            "Cargo/Soroban receipt subjectBundleHash does not match the "
            "independently verified subject bundle"
        )
    execution = _strict_object(
        receipt["execution"],
        "sorobanReceipt.execution",
        keys=SOROBAN_EXECUTION_KEYS,
    )
    execution_counts = {
        key: _integer(
            execution[key], f"sorobanReceipt.execution.{key}", non_negative=True
        )
        for key in sorted(SOROBAN_EXECUTION_KEYS)
    }
    if execution_counts != {"matched": 1, "passed": 1, "failed": 0, "ignored": 0}:
        raise ToolCaptureError(
            "Cargo/Soroban receipt must attest exactly one matched and passed test with no failed or ignored tests"
        )

    raw_steps = _array(receipt["steps"], "sorobanReceipt.steps", non_empty=True)
    observations = capture["observations"][1:]
    if len(raw_steps) != len(observations):
        raise ToolCaptureError(
            "Cargo/Soroban receipt steps must cover every transition exactly once"
        )
    if len(raw_steps) > bounds["maxSequenceLength"]:
        raise ToolCaptureError(
            "Cargo/Soroban receipt steps exceed run.bounds.maxSequenceLength"
        )

    artifact_by_id = {item["id"]: item for item in verified["toolArtifacts"]}
    snapshot_bindings: list[dict[str, str]] = []
    seen_snapshots: set[str] = set()
    for index, (raw_step, observation) in enumerate(zip(raw_steps, observations)):
        snapshot_id, snapshot_digest = _bind_step(
            raw_step,
            index=index,
            observation=observation,
            primary_id=artifact["id"],
            artifact_by_id=artifact_by_id,
        )
        if snapshot_id in seen_snapshots:
            raise ToolCaptureError(
                "Cargo/Soroban receipt must use a distinct snapshot artifact per step"
            )
        seen_snapshots.add(snapshot_id)
        snapshot_bindings.append(
            {"artifactId": snapshot_id, "digest": snapshot_digest}
        )

    non_primary = {
        item["id"]
        for item in verified["toolArtifacts"]
        if item["id"] != artifact["id"]
    }
    if non_primary != seen_snapshots:
        raise ToolCaptureError(
            "Cargo/Soroban tool artifacts must be exactly the receipt-bound state snapshots"
        )
    if any(
        item["kind"] != SOROBAN_SNAPSHOT_KIND
        for item in verified["toolArtifacts"]
        if item["id"] != artifact["id"]
    ):
        raise ToolCaptureError(
            f"Cargo/Soroban non-primary artifacts must use kind {SOROBAN_SNAPSHOT_KIND!r}"
        )

    bindings = build_native_bindings(
        capture,
        artifact_id=artifact["id"],
        locators=[f"/steps/{index}" for index in range(len(raw_steps))],
    )
    native_evidence = {
        "status": "bound",
        "parser": SOROBAN_RECEIPT_SCHEMA,
        "artifactId": artifact["id"],
        "artifactDigest": artifact["digest"],
        "receiptHash": canonical_sha256(receipt),
        "framework": "soroban",
        "package": receipt_package,
        "test": receipt_test,
        "seed": receipt_seed,
        "subjectBundleHash": receipt_subject_bundle_hash,
        "execution": execution_counts,
        "steps": len(raw_steps),
        "snapshots": snapshot_bindings,
    }
    result = adapt_dynamic_capture(
        capture,
        profile,
        verified,
        expected_tool="cargo-soroban",
        native_bindings=bindings,
        native_evidence=native_evidence,
    )
    result["claimBoundary"] = (
        "The adapter verified the reviewed subject artifacts, parsed one successful exact Cargo "
        "test receipt, independently reopened every referenced Soroban state snapshot, and bound "
        "each recorded post-transition ledger/state/environment/actor/authority/value coordinate to "
        "a TSSE transition. The receipt also binds one matched and passed test to the independently "
        "verified subject bundle. "
        "It did not execute Cargo, attest the receipt producer or Soroban host, establish snapshot "
        "semantic completeness, discover omitted paths, or assess system security. READY means only "
        "that this bounded evidence is suitable for review; scanVerdict remains NOT_ASSESSED."
    )
    result["verificationDebt"] = [
        "The receipt and Soroban snapshots may share the same producer and failure domain.",
        "No independent ledger, event, or state witness is bound to this adapter result.",
        "The initial pre-state has no native receipt step or state snapshot and remains "
        "capture-author supplied.",
        "Transition identifiers and causal descriptions remain reviewed capture fields rather "
        "than native receipt fields.",
        "workers=1 is reviewed capture metadata; argv does not force Cargo jobs or test-harness "
        "threads to one.",
        "Snapshot bytes are integrity-bound but remain supporting evidence, not the sole semantic oracle.",
        "Soroban host, dependency, runtime, and compiled-Wasm authenticity are not attested.",
        "Dynamic coverage, omitted reachable states, and behavior outside the recorded exact test remain unassessed.",
    ]
    result["resultHash"] = canonical_result_hash(result)
    return result


adapt_capture = adapt_soroban_capture

__all__ = [
    "CARGO_EXECUTABLES",
    "SOROBAN_ACTOR_KEYS",
    "SOROBAN_AUTHORITY_KEYS",
    "SOROBAN_EXECUTION_KEYS",
    "SOROBAN_RECEIPT_KEYS",
    "SOROBAN_RECEIPT_SCHEMA",
    "SOROBAN_SNAPSHOT_KIND",
    "SOROBAN_SPACE_KEYS",
    "SOROBAN_STATE_KEYS",
    "SOROBAN_STEP_KEYS",
    "SOROBAN_TIME_KEYS",
    "SOROBAN_VALUE_KEYS",
    "adapt_capture",
    "adapt_soroban_capture",
]
