#!/usr/bin/env python3
"""Fail-closed forbidden-state detector for Temporal Transition Field evidence.

Consumes:
- an evidence record JSON (v0.2-compatible shape)
- a rule file using the constrained v0.3 comparison DSL

No eval(), code execution, or arbitrary expression parsing is used.
Missing or malformed data produces `inconclusive`, never a synthetic pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MISSING = object()
SUPPORTED_OPS = {"eq", "neq", "lt", "lte", "gt", "gte", "nonempty"}
OBSERVED_FIELDS = (
    "scope",
    "model_transition",
    "pre_state",
    "request",
    "decision",
    "mutation",
    "post_state",
    "evidence",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def observation_projection(document: dict[str, Any]) -> dict[str, Any]:
    """Return only observed/model inputs, excluding generated verdict annotations."""
    return {field: document.get(field) for field in OBSERVED_FIELDS if field in document}


def get_path(document: Any, dotted_path: str) -> Any:
    current = document
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def resolve_operand(document: dict[str, Any], operand: dict[str, Any]) -> Any:
    if "value" in operand:
        return operand["value"]
    if "path" in operand:
        return get_path(document, operand["path"])
    return MISSING


def _nonempty(value: Any) -> bool:
    if value is MISSING or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_nonempty(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and any(_nonempty(item) for item in value.values())
    return bool(value)


def compare(left: Any, op: str, right: Any) -> bool:
    if op not in SUPPORTED_OPS:
        raise ValueError(f"Unsupported operator: {op}")
    if op == "nonempty":
        return _nonempty(left) is bool(right)
    if op == "eq":
        return left == right
    if op == "neq":
        return left != right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    raise AssertionError(op)


def _valid_operand(operand: Any) -> bool:
    if not isinstance(operand, dict):
        return False
    has_value = "value" in operand
    has_path = "path" in operand
    if has_value == has_path:
        return False
    if has_path:
        return isinstance(operand["path"], str) and bool(operand["path"].strip())
    return True


def _validate_clause(clause: Any, where: str) -> list[str]:
    if not isinstance(clause, dict):
        return [f"{where} must be an object"]
    errors: list[str] = []
    op = clause.get("op")
    if op not in SUPPORTED_OPS:
        errors.append(f"{where}.op must be one of {sorted(SUPPORTED_OPS)}")
    if not _valid_operand(clause.get("left")):
        errors.append(f"{where}.left must contain exactly one valid path or value operand")
    if not _valid_operand(clause.get("right")):
        errors.append(f"{where}.right must contain exactly one valid path or value operand")
    return errors


def validate_rules_document(rules_document: Any) -> list[str]:
    if not isinstance(rules_document, dict):
        return ["rules document must be an object"]
    rules = rules_document.get("rules")
    if not isinstance(rules, list) or not rules:
        return ["rules document must contain a non-empty rules list"]

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        prefix = f"rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix} must be an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        elif rule_id in seen_ids:
            errors.append(f"{prefix}.id duplicates {rule_id!r}")
        else:
            seen_ids.add(rule_id)

        when = rule.get("when", [])
        if not isinstance(when, list):
            errors.append(f"{prefix}.when must be a list when present")
        else:
            for clause_index, clause in enumerate(when):
                errors.extend(_validate_clause(clause, f"{prefix}.when[{clause_index}]"))
        errors.extend(_validate_clause(rule.get("assert"), f"{prefix}.assert"))
    return errors


def evaluate_clause(document: dict[str, Any], clause: dict[str, Any]) -> dict[str, Any]:
    op = clause.get("op")
    left = resolve_operand(document, clause.get("left", {}))
    right = resolve_operand(document, clause.get("right", {}))
    if left is MISSING or right is MISSING:
        return {
            "status": "inconclusive",
            "reason": "missing_operand",
            "op": op,
            "left": None if left is MISSING else left,
            "right": None if right is MISSING else right,
        }
    try:
        passed = compare(left, op, right)
    except (TypeError, ValueError) as exc:
        return {
            "status": "inconclusive",
            "reason": f"comparison_error:{type(exc).__name__}",
            "op": op,
            "left": left,
            "right": right,
        }
    return {"status": "pass" if passed else "fail", "op": op, "left": left, "right": right}


def evaluate_rule(document: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    condition_results = [evaluate_clause(document, clause) for clause in rule.get("when", [])]
    if any(item["status"] == "inconclusive" for item in condition_results):
        return {
            "id": rule["id"],
            "status": "inconclusive",
            "reason": "condition_inconclusive",
            "conditions": condition_results,
        }
    if any(item["status"] == "fail" for item in condition_results):
        return {
            "id": rule["id"],
            "status": "not_applicable",
            "conditions": condition_results,
        }

    assertion = evaluate_clause(document, rule["assert"])
    return {
        "id": rule["id"],
        "description": rule.get("description"),
        "status": assertion["status"],
        "assertion": assertion,
        "forbidden_state": rule.get("forbidden_state"),
        "severity_hint": rule.get("severity_hint"),
    }


def _inconclusive_result(document: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    evidence_fingerprint = digest(observation_projection(document))
    return {
        "schema_version": "0.3",
        "run_id": document.get("run_id"),
        "scenario_id": document.get("scenario_id"),
        "overall": "inconclusive",
        "forbidden_state_reached": False,
        "evidence_fingerprint": evidence_fingerprint,
        "evaluations": [
            {
                "id": None,
                "status": "inconclusive",
                "reason": "invalid_rule_document",
                "errors": errors,
            }
        ],
        "finding": None,
    }


def detect(document: dict[str, Any], rules_document: dict[str, Any]) -> dict[str, Any]:
    validation_errors = validate_rules_document(rules_document)
    if validation_errors:
        return _inconclusive_result(document, validation_errors)

    try:
        evaluations = [evaluate_rule(document, rule) for rule in rules_document["rules"]]
    except (KeyError, TypeError, ValueError) as exc:
        return _inconclusive_result(
            document,
            [f"rule evaluation failed closed: {type(exc).__name__}: {exc}"],
        )

    failed = [item for item in evaluations if item["status"] == "fail"]
    inconclusive = [item for item in evaluations if item["status"] == "inconclusive"]

    evidence_fingerprint = digest(observation_projection(document))
    if failed:
        finding_seed = {
            "evidence_fingerprint": evidence_fingerprint,
            "failed_rule_ids": sorted(item["id"] for item in failed),
        }
        finding_id = f"CGQA-TTF-{digest(finding_seed)[:12].upper()}"
        finding = {
            "finding_id": finding_id,
            "state": "violated",
            "forbidden_state_reached": True,
            "failed_rules": [item["id"] for item in failed],
            "forbidden_states": [item.get("forbidden_state") for item in failed],
            "severity_hints": [item.get("severity_hint") for item in failed],
            "evidence_fingerprint": evidence_fingerprint,
            "summary": "One or more explicit forbidden-state rules were violated.",
        }
        overall = "violated"
    elif inconclusive:
        finding = None
        overall = "inconclusive"
    else:
        finding = None
        overall = "not_found_within_observed_transition"

    return {
        "schema_version": "0.3",
        "run_id": document.get("run_id"),
        "scenario_id": document.get("scenario_id"),
        "overall": overall,
        "forbidden_state_reached": bool(failed),
        "evidence_fingerprint": evidence_fingerprint,
        "evaluations": evaluations,
        "finding": finding,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("rules", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    result = detect(evidence, rules)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if result["overall"] == "violated" else 2 if result["overall"] == "inconclusive" else 0


if __name__ == "__main__":
    raise SystemExit(main())
