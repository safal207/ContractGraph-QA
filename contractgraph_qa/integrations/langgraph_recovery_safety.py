from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

LANGGRAPH_ISSUE_REPOSITORY = "langchain-ai/langgraph"
LANGGRAPH_ISSUE_NUMBER = 8039
LANGGRAPH_BASELINE_VERSION = "1.2.4"
LANGGRAPH_SQLITE_BASELINE_VERSION = "3.1.0"
RECOVERY_SAFETY_PROPERTY_REPOSITORY = (
    "vasilisnasopoulos/recovery-safety-property"
)
RECOVERY_SAFETY_PROPERTY_COMMIT = "22e34841226c41d80c8646b33f1439a87e8549af"
RECOVERY_SAFETY_PROPERTY_LICENSE = "CC BY 4.0"
OBSERVATION_SCHEMA = "cgqa.langgraph.recovery-safety-observation/v0.1"
REPORT_SCHEMA = "cgqa.langgraph.recovery-safety-report/v0.1"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


@dataclass(frozen=True)
class PropertyCheck:
    property_id: str
    name: str
    status: CheckStatus
    rationale: str
    evidence: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "property": self.property_id,
            "name": self.name,
            "status": self.status.value,
            "rationale": self.rationale,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class RecoverySafetyReport:
    subject: dict[str, Any]
    checks: tuple[PropertyCheck, ...]
    receiver_control: PropertyCheck | None

    @property
    def conformant(self) -> bool:
        return all(check.status is CheckStatus.PASS for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": REPORT_SCHEMA,
            "subject": self.subject,
            "conformant": self.conformant,
            "checks": [check.to_dict() for check in self.checks],
        }
        if self.receiver_control is not None:
            payload["receiver_control"] = self.receiver_control.to_dict()
        return payload


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def semantic_action_identity(action: Mapping[str, Any]) -> str:
    """Derive identity from what the action is, not runtime position."""

    return canonical_digest({"action": dict(action)})


def logical_action_set_digest(actions: Sequence[Mapping[str, Any]]) -> str:
    """Bind the declared ordered logical actions used by a fixture."""

    return canonical_digest({"logical_actions": [dict(action) for action in actions]})


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_records(
    records: Any,
    *,
    label: str,
    declared_action_ids: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise ValueError(f"{label} must be a list")

    result: list[dict[str, Any]] = []
    for index, raw_record in enumerate(records):
        record = dict(_require_mapping(raw_record, f"{label}[{index}]"))
        action = dict(_require_mapping(record.get("action"), f"{label}[{index}].action"))
        action_id = record.get("action_id")
        if not isinstance(action_id, str) or not action_id:
            raise ValueError("every attempt/admission must carry action_id")
        expected_id = semantic_action_identity(action)
        if action_id != expected_id:
            raise ValueError(f"{label}[{index}] action_id does not bind its action")
        if action_id not in declared_action_ids:
            raise ValueError(f"{label}[{index}] action is outside logical_actions")
        record["action"] = action
        result.append(record)
    return result


def _validated_observations(
    observations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        item = dict(_require_mapping(observation, f"observation {index}"))
        if item.get("schema") != OBSERVATION_SCHEMA:
            raise ValueError(f"observation {index} has unsupported schema")

        for required in (
            "source",
            "scenario",
            "receiver",
            "received",
            "received_digest",
            "logical_actions",
            "logical_action_set_digest",
            "crash_boundary",
            "observable_state",
            "recovered_state_digest",
            "attempts",
            "admissions",
        ):
            if required not in item:
                raise ValueError(f"observation {index} missing {required}")

        source = dict(_require_mapping(item["source"], f"observation {index}.source"))
        if source.get("repository") != LANGGRAPH_ISSUE_REPOSITORY:
            raise ValueError(f"observation {index} has unexpected source repository")
        if source.get("issue") != LANGGRAPH_ISSUE_NUMBER:
            raise ValueError(f"observation {index} has unexpected source issue")
        for version_key in ("langgraph_version", "sqlite_checkpointer_version"):
            if not isinstance(source.get(version_key), str) or not source[version_key]:
                raise ValueError(f"observation {index} missing source {version_key}")

        receiver = item["receiver"]
        if receiver not in {"append", "dedup"}:
            raise ValueError(f"observation {index} has unsupported receiver")

        received = dict(_require_mapping(item["received"], f"observation {index}.received"))
        if item["received_digest"] != canonical_digest(received):
            raise ValueError(f"observation {index} received_digest mismatch")

        logical_actions_raw = item["logical_actions"]
        if not isinstance(logical_actions_raw, list) or not logical_actions_raw:
            raise ValueError(f"observation {index} logical_actions must be a non-empty list")
        logical_actions = [
            dict(_require_mapping(action, f"observation {index}.logical_actions"))
            for action in logical_actions_raw
        ]
        expected_action_set_digest = logical_action_set_digest(logical_actions)
        if item["logical_action_set_digest"] != expected_action_set_digest:
            raise ValueError(f"observation {index} logical_action_set_digest mismatch")
        declared_action_ids = {
            semantic_action_identity(action) for action in logical_actions
        }
        if len(declared_action_ids) != len(logical_actions):
            raise ValueError(f"observation {index} declares duplicate logical actions")

        observable_state = dict(
            _require_mapping(item["observable_state"], f"observation {index}.observable_state")
        )
        if item["recovered_state_digest"] != canonical_digest(observable_state):
            raise ValueError(f"observation {index} recovered_state_digest mismatch")

        attempts = _validate_records(
            item["attempts"],
            label=f"observation {index}.attempts",
            declared_action_ids=declared_action_ids,
        )
        admissions = _validate_records(
            item["admissions"],
            label=f"observation {index}.admissions",
            declared_action_ids=declared_action_ids,
        )
        attempt_counts = _action_id_counts(attempts)
        admission_counts = _action_id_counts(admissions)
        for action_id, admission_count in admission_counts.items():
            if admission_count > attempt_counts[action_id]:
                raise ValueError(
                    f"observation {index} admits action more often than attempted"
                )

        item["source"] = source
        item["received"] = received
        item["logical_actions"] = logical_actions
        item["observable_state"] = observable_state
        item["attempts"] = attempts
        item["admissions"] = admissions
        result.append(item)

    if not result:
        raise ValueError("at least one observation is required")
    return result


def _action_id_counts(records: Sequence[Mapping[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        action_id = record.get("action_id")
        if not isinstance(action_id, str) or not action_id:
            raise ValueError("every attempt/admission must carry action_id")
        counts[action_id] += 1
    return counts


def _observed_profiles(items: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    profiles = {
        (
            str(item["source"]["langgraph_version"]),
            str(item["source"]["sqlite_checkpointer_version"]),
        )
        for item in items
    }
    return [
        {
            "langgraph_version": langgraph_version,
            "sqlite_checkpointer_version": sqlite_version,
        }
        for langgraph_version, sqlite_version in sorted(profiles)
    ]


def evaluate_recovery_safety(
    observations: Sequence[Mapping[str, Any]],
) -> RecoverySafetyReport:
    """Evaluate RS1-RS3 against bounded crash/recovery observations.

    A comparable pair must bind the same explicit durable input, ordered logical
    action set, and crash boundary while varying only the forced persistence
    interleaving. This maps ``received[n]`` to the graph input durably supplied
    before the worker runs. Derived checkpointer outcomes are intentionally not
    treated as new inputs; doing so would erase the persist-input-versus-persist-
    outcome distinction the property is designed to test.
    """

    items = _validated_observations(observations)
    append_items = [item for item in items if item["receiver"] == "append"]
    dedup_items = [item for item in items if item["receiver"] == "dedup"]

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in append_items:
        groups[
            (
                item["received_digest"],
                item["logical_action_set_digest"],
                item["crash_boundary"],
            )
        ].append(item)

    comparable = [group for group in groups.values() if len(group) >= 2]
    if comparable:
        violating_groups = [
            group
            for group in comparable
            if len({item["recovered_state_digest"] for item in group}) != 1
        ]
        equal_state = not violating_groups
        all_scenarios = tuple(
            sorted({str(item["scenario"]) for group in comparable for item in group})
        )
        violating_scenarios = tuple(
            sorted(
                {
                    str(item["scenario"])
                    for group in violating_groups
                    for item in group
                }
            )
        )
        evidence = all_scenarios if equal_state else violating_scenarios
        rs1 = PropertyCheck(
            property_id="RS1",
            name="Input determinism",
            status=CheckStatus.PASS if equal_state else CheckStatus.FAIL,
            rationale=(
                "Equal mapped durable inputs and logical actions recovered to one observable state."
                if equal_state
                else "Equal mapped durable inputs and logical actions recovered to different observable states."
            ),
            evidence=evidence,
        )
        rs2 = PropertyCheck(
            property_id="RS2",
            name="Crash independence",
            status=CheckStatus.PASS if equal_state else CheckStatus.FAIL,
            rationale=(
                "Changing only the forced crash/persistence timing did not change recovery."
                if equal_state
                else "Changing only the forced persistence interleaving changed recovery."
            ),
            evidence=evidence,
        )
    else:
        rs1 = PropertyCheck(
            property_id="RS1",
            name="Input determinism",
            status=CheckStatus.NOT_ESTABLISHED,
            rationale=(
                "No comparable pair shared the mapped durable input, logical action set, "
                "and crash boundary."
            ),
            evidence=(),
        )
        rs2 = PropertyCheck(
            property_id="RS2",
            name="Crash independence",
            status=CheckStatus.NOT_ESTABLISHED,
            rationale="No forced-timing pair was available for one bound fixture subject.",
            evidence=(),
        )

    if append_items:
        duplicate_evidence: list[str] = []
        for item in append_items:
            counts = _action_id_counts(item["admissions"])
            if any(count > 1 for count in counts.values()):
                duplicate_evidence.append(str(item["scenario"]))
        rs3 = PropertyCheck(
            property_id="RS3",
            name="At-most-once identity",
            status=CheckStatus.FAIL if duplicate_evidence else CheckStatus.PASS,
            rationale=(
                "At least one stable logical-action identity was admitted more than once."
                if duplicate_evidence
                else "No stable logical-action identity was admitted more than once."
            ),
            evidence=tuple(
                sorted(
                    duplicate_evidence
                    or [str(item["scenario"]) for item in append_items]
                )
            ),
        )
    else:
        rs3 = PropertyCheck(
            property_id="RS3",
            name="At-most-once identity",
            status=CheckStatus.NOT_ESTABLISHED,
            rationale="No append-receiver observation exposed raw admission multiplicity.",
            evidence=(),
        )

    receiver_control: PropertyCheck | None = None
    if dedup_items:
        failures: list[str] = []
        controls: list[str] = []
        for item in dedup_items:
            controls.append(str(item["scenario"]))
            attempt_counts = _action_id_counts(item["attempts"])
            admission_counts = _action_id_counts(item["admissions"])
            reexecution_seen = any(count > 1 for count in attempt_counts.values())
            duplicate_admission = any(count > 1 for count in admission_counts.values())
            if not reexecution_seen or duplicate_admission:
                failures.append(str(item["scenario"]))
        receiver_control = PropertyCheck(
            property_id="RS3-CONTROL",
            name="Receiver-honoured stable identity",
            status=CheckStatus.FAIL if failures else CheckStatus.PASS,
            rationale=(
                "The control did not show re-execution safely collapsed to one admission."
                if failures
                else "The node re-executed, but the receiver admitted the stable identity once."
            ),
            evidence=tuple(sorted(failures or controls)),
        )

    profiles = _observed_profiles(items)
    subject = {
        "runtime": LANGGRAPH_ISSUE_REPOSITORY,
        "issue": LANGGRAPH_ISSUE_NUMBER,
        "langgraph_version": (
            profiles[0]["langgraph_version"] if len(profiles) == 1 else None
        ),
        "sqlite_checkpointer_version": (
            profiles[0]["sqlite_checkpointer_version"] if len(profiles) == 1 else None
        ),
        "observed_profiles": profiles,
        "property_source": RECOVERY_SAFETY_PROPERTY_REPOSITORY,
        "property_commit": RECOVERY_SAFETY_PROPERTY_COMMIT,
        "property_license": RECOVERY_SAFETY_PROPERTY_LICENSE,
        "mapping": (
            "received[n] = explicit graph input durable before worker execution; "
            "State(n) = recovered graph state plus worker attempt counts and externally admitted action counts"
        ),
    }
    return RecoverySafetyReport(
        subject=subject,
        checks=(rs1, rs2, rs3),
        receiver_control=receiver_control,
    )
