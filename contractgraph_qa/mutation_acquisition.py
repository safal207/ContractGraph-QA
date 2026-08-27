"""Source-bound Solidity mutation acquisition with Foundry execution.

This module turns a reviewed mutation plan into exact source mutations, executes a
narrow Foundry test selector against each compilable mutant in an isolated project
copy, and binds the resulting outcomes into CGQ-SPEC-001.

Important claim boundaries:
- mutations are exact reviewed text replacements, not inferred vulnerabilities;
- the original source SHA-256 must match before any mutation is applied;
- a compile failure is never counted as a detected fault;
- a Foundry test is considered detected/survived only when the named selector is
  observed in command output;
- activation/non-vacuity remains reviewed evidence and is not inferred from a
  passing test command.
"""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Mapping

from contractgraph_qa.spec_assurance import (
    run_spec_assurance_model,
    spec_assurance_model_from_dict,
)

SCHEMA_VERSION = "solidity-mutation-plan-v0.1"
RESULT_SCHEMA_VERSION = "solidity-mutation-result-v0.1"

_MODEL_KEYS = {
    "schemaVersion",
    "acquisitionId",
    "sourcePath",
    "sourceSha256",
    "propertyInvariantId",
    "propertyDescription",
    "activationWitness",
    "requiredFaultClasses",
    "foundry",
    "mutations",
    "scope",
}
_ACTIVATION_KEYS = {"observed", "evidenceSha256", "description"}
_FOUNDRY_KEYS = {"profile", "timeoutSeconds"}
_MUTATION_KEYS = {
    "mutationId",
    "faultClass",
    "description",
    "match",
    "replacement",
    "matchPath",
    "matchTest",
}
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class ActivationEvidence:
    observed: bool
    evidence_sha256: str
    description: str


@dataclass(frozen=True, slots=True)
class FoundryConfig:
    profile: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class MutationSpec:
    mutation_id: str
    fault_class: str
    description: str
    match: str
    replacement: str
    match_path: str
    match_test: str


@dataclass(frozen=True, slots=True)
class MutationPlan:
    acquisition_id: str
    source_path: str
    source_sha256: str
    property_invariant_id: str
    property_description: str
    activation_witness: ActivationEvidence
    required_fault_classes: tuple[str, ...]
    foundry: FoundryConfig
    mutations: tuple[MutationSpec, ...]
    scope: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _declared_sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    _require(
        len(text) == 64 and all(ch in "0123456789abcdef" for ch in text),
        f"{field} must be a 64-character hex sha256",
    )
    return text


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _reject_extra_keys(data: Mapping[str, Any], allowed: set[str], field: str) -> None:
    extras = sorted(set(data) - allowed)
    _require(not extras, f"{field} contains unexpected fields: {', '.join(extras)}")


def _safe_id(value: Any, field: str) -> str:
    text = _text(value, field)
    _require(bool(_SAFE_ID_RE.fullmatch(text)), f"{field} contains unsafe characters")
    return text


def _relative_path(value: Any, field: str) -> str:
    text = _text(value, field)
    path = Path(text)
    _require(not path.is_absolute(), f"{field} must be relative")
    _require(".." not in path.parts, f"{field} must not traverse parent directories")
    return path.as_posix()


def _unique_texts(value: Any, field: str) -> tuple[str, ...]:
    _require(isinstance(value, list) and value, f"{field} must be a non-empty array")
    items = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    _require(len(items) == len(set(items)), f"{field} must contain unique values")
    return items


def mutation_plan_from_dict(data: dict[str, Any]) -> MutationPlan:
    _require(isinstance(data, dict), "mutation plan must be a JSON object")
    _reject_extra_keys(data, _MODEL_KEYS, "mutation plan")
    required = _MODEL_KEYS - {"scope"}
    missing = sorted(required - set(data))
    _require(not missing, "mutation plan missing required fields: " + ", ".join(missing))
    _require(data["schemaVersion"] == SCHEMA_VERSION, f"schemaVersion must be {SCHEMA_VERSION}")

    raw_activation = data["activationWitness"]
    _require(isinstance(raw_activation, dict), "activationWitness must be an object")
    _reject_extra_keys(raw_activation, _ACTIVATION_KEYS, "activationWitness")
    missing_activation = sorted(_ACTIVATION_KEYS - set(raw_activation))
    _require(not missing_activation, "activationWitness missing required fields: " + ", ".join(missing_activation))
    observed = raw_activation["observed"]
    _require(isinstance(observed, bool), "activationWitness.observed must be a boolean")
    activation = ActivationEvidence(
        observed=observed,
        evidence_sha256=_declared_sha256(raw_activation["evidenceSha256"], "activationWitness.evidenceSha256"),
        description=_text(raw_activation["description"], "activationWitness.description"),
    )

    raw_foundry = data["foundry"]
    _require(isinstance(raw_foundry, dict), "foundry must be an object")
    _reject_extra_keys(raw_foundry, _FOUNDRY_KEYS, "foundry")
    missing_foundry = sorted(_FOUNDRY_KEYS - set(raw_foundry))
    _require(not missing_foundry, "foundry missing required fields: " + ", ".join(missing_foundry))
    timeout = raw_foundry["timeoutSeconds"]
    _require(isinstance(timeout, int) and not isinstance(timeout, bool) and 1 <= timeout <= 3600, "foundry.timeoutSeconds must be an integer from 1 to 3600")
    profile = _safe_id(raw_foundry["profile"], "foundry.profile")

    raw_mutations = data["mutations"]
    _require(isinstance(raw_mutations, list) and raw_mutations, "mutations must be a non-empty array")
    mutations: list[MutationSpec] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_mutations):
        field = f"mutations[{index}]"
        _require(isinstance(raw, dict), f"{field} must be an object")
        _reject_extra_keys(raw, _MUTATION_KEYS, field)
        missing_mutation = sorted(_MUTATION_KEYS - set(raw))
        _require(not missing_mutation, f"{field} missing required fields: {', '.join(missing_mutation)}")
        mutation_id = _safe_id(raw["mutationId"], f"{field}.mutationId")
        _require(mutation_id not in seen_ids, f"duplicate mutationId: {mutation_id}")
        seen_ids.add(mutation_id)
        match = raw["match"]
        replacement = raw["replacement"]
        _require(isinstance(match, str) and match, f"{field}.match must be a non-empty string")
        _require(isinstance(replacement, str), f"{field}.replacement must be a string")
        _require(match != replacement, f"{field}.replacement must change the source")
        mutations.append(
            MutationSpec(
                mutation_id=mutation_id,
                fault_class=_text(raw["faultClass"], f"{field}.faultClass"),
                description=_text(raw["description"], f"{field}.description"),
                match=match,
                replacement=replacement,
                match_path=_relative_path(raw["matchPath"], f"{field}.matchPath"),
                match_test=_text(raw["matchTest"], f"{field}.matchTest"),
            )
        )

    scope_raw = data.get("scope")
    return MutationPlan(
        acquisition_id=_safe_id(data["acquisitionId"], "acquisitionId"),
        source_path=_relative_path(data["sourcePath"], "sourcePath"),
        source_sha256=_declared_sha256(data["sourceSha256"], "sourceSha256"),
        property_invariant_id=_text(data["propertyInvariantId"], "propertyInvariantId"),
        property_description=_text(data["propertyDescription"], "propertyDescription"),
        activation_witness=activation,
        required_fault_classes=_unique_texts(data["requiredFaultClasses"], "requiredFaultClasses"),
        foundry=FoundryConfig(profile=profile, timeout_seconds=timeout),
        mutations=tuple(mutations),
        scope=None if scope_raw is None else _text(scope_raw, "scope"),
    )


def load_mutation_plan(path: Path) -> MutationPlan:
    with path.open("r", encoding="utf-8") as handle:
        return mutation_plan_from_dict(json.load(handle))


def mutation_plan_to_dict(plan: MutationPlan) -> dict[str, object]:
    document: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "acquisitionId": plan.acquisition_id,
        "sourcePath": plan.source_path,
        "sourceSha256": plan.source_sha256,
        "propertyInvariantId": plan.property_invariant_id,
        "propertyDescription": plan.property_description,
        "activationWitness": {
            "observed": plan.activation_witness.observed,
            "evidenceSha256": plan.activation_witness.evidence_sha256,
            "description": plan.activation_witness.description,
        },
        "requiredFaultClasses": list(plan.required_fault_classes),
        "foundry": {
            "profile": plan.foundry.profile,
            "timeoutSeconds": plan.foundry.timeout_seconds,
        },
        "mutations": [
            {
                "mutationId": item.mutation_id,
                "faultClass": item.fault_class,
                "description": item.description,
                "match": item.match,
                "replacement": item.replacement,
                "matchPath": item.match_path,
                "matchTest": item.match_test,
            }
            for item in plan.mutations
        ],
    }
    if plan.scope is not None:
        document["scope"] = plan.scope
    return document


def mutation_plan_sha256(plan: MutationPlan) -> str:
    return _canonical_sha256(mutation_plan_to_dict(plan))


def _resolve_under(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {relative}") from exc
    return target


def apply_exact_mutation(source: str, mutation: MutationSpec) -> tuple[str, dict[str, int]]:
    count = source.count(mutation.match)
    _require(count == 1, f"mutation {mutation.mutation_id} match must occur exactly once; found {count}")
    start = source.index(mutation.match)
    end = start + len(mutation.match)
    start_line = source.count("\n", 0, start) + 1
    start_column = start - source.rfind("\n", 0, start)
    end_line = source.count("\n", 0, end) + 1
    last_newline = source.rfind("\n", 0, end)
    end_column = end + 1 if last_newline < 0 else end - last_newline
    mutated = source[:start] + mutation.replacement + source[end:]
    return mutated, {
        "startOffset": start,
        "endOffset": end,
        "startLine": start_line,
        "startColumn": start_column,
        "endLine": end_line,
        "endColumn": end_column,
    }


def _command_record(args: list[str], cwd: Path, timeout_seconds: int, profile: str) -> dict[str, object]:
    env = dict(__import__("os").environ)
    env["FOUNDRY_PROFILE"] = profile
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        return {
            "args": args,
            "returnCode": completed.returncode,
            "timedOut": False,
            "stdoutSha256": _sha256_bytes(stdout),
            "stderrSha256": _sha256_bytes(stderr),
            "selectorObserved": None,
            "combinedOutput": (stdout + b"\n" + stderr).decode("utf-8", errors="replace"),
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8")
        return {
            "args": args,
            "returnCode": None,
            "timedOut": True,
            "stdoutSha256": _sha256_bytes(stdout),
            "stderrSha256": _sha256_bytes(stderr),
            "selectorObserved": None,
            "combinedOutput": (stdout + b"\n" + stderr).decode("utf-8", errors="replace"),
        }


def _public_command_record(record: Mapping[str, object], selector: str | None = None) -> dict[str, object]:
    output = str(record.get("combinedOutput", ""))
    observed = None if selector is None else selector in output
    return {
        "args": list(record["args"]),  # type: ignore[arg-type]
        "returnCode": record["returnCode"],
        "timedOut": record["timedOut"],
        "stdoutSha256": record["stdoutSha256"],
        "stderrSha256": record["stderrSha256"],
        "selectorObserved": observed,
    }


def _copy_project(source_root: Path, destination: Path, output_dir: Path | None) -> None:
    ignored = {".git", "out", "cache", "broadcast", "dist", ".venv", "__pycache__", ".pytest_cache"}
    if output_dir is not None:
        try:
            relative = output_dir.resolve().relative_to(source_root.resolve())
            if len(relative.parts) == 1:
                ignored.add(relative.parts[0])
        except ValueError:
            pass

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(source_root, destination, ignore=ignore)


def _run_selector(project_root: Path, mutation: MutationSpec, config: FoundryConfig) -> dict[str, object]:
    raw = _command_record(
        [
            "forge",
            "test",
            "--match-path",
            mutation.match_path,
            "--match-test",
            mutation.match_test,
        ],
        project_root,
        config.timeout_seconds,
        config.profile,
    )
    return _public_command_record(raw, mutation.match_test)


def _run_build(project_root: Path, config: FoundryConfig) -> dict[str, object]:
    raw = _command_record(["forge", "build"], project_root, config.timeout_seconds, config.profile)
    return _public_command_record(raw)


def _baseline_status(records: list[dict[str, object]]) -> str:
    if any(record["timedOut"] or record["returnCode"] not in {0, 1} for record in records):
        return "inconclusive"
    if any(record["returnCode"] != 0 for record in records):
        return "fail"
    if any(record["selectorObserved"] is not True for record in records):
        return "inconclusive"
    return "pass"


def run_mutation_acquisition(
    plan: MutationPlan,
    project_root: Path,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    """Generate exact mutants, run Foundry selectors, and evaluate CGQ-SPEC-001."""

    root = project_root.resolve()
    _require(root.is_dir(), "project root must be a directory")
    source_path = _resolve_under(root, plan.source_path)
    _require(source_path.is_file(), f"source file not found: {plan.source_path}")
    source_bytes = source_path.read_bytes()
    actual_source_sha = _sha256_bytes(source_bytes)
    _require(actual_source_sha == plan.source_sha256, "sourceSha256 does not match the exact source bytes")
    try:
        source_text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("source file must be UTF-8") from exc

    generated: list[tuple[MutationSpec, str, dict[str, int], str, str]] = []
    for mutation in plan.mutations:
        mutated, span = apply_exact_mutation(source_text, mutation)
        diff = "".join(
            difflib.unified_diff(
                source_text.splitlines(keepends=True),
                mutated.splitlines(keepends=True),
                fromfile=plan.source_path,
                tofile=f"{plan.source_path}::{mutation.mutation_id}",
            )
        )
        generated.append((mutation, mutated, span, _sha256_text(mutated), diff))

    unique_selectors: dict[tuple[str, str], MutationSpec] = {}
    for mutation in plan.mutations:
        unique_selectors[(mutation.match_path, mutation.match_test)] = mutation

    baseline_records: list[dict[str, object]] = []
    for selector in sorted(unique_selectors):
        baseline_records.append(_run_selector(root, unique_selectors[selector], plan.foundry))
    baseline_status = _baseline_status(baseline_records)
    baseline_evidence = {
        "profile": plan.foundry.profile,
        "records": baseline_records,
        "sourceSha256": actual_source_sha,
    }
    baseline_evidence_sha = _canonical_sha256(baseline_evidence)

    mutation_results: list[dict[str, object]] = []
    spec_mutations: list[dict[str, object]] = []
    output_resolved = None if output_dir is None else output_dir.resolve()

    for mutation, mutated, span, mutant_sha, diff in generated:
        with tempfile.TemporaryDirectory(prefix="cgqa-mutant-") as temp_name:
            temp_root = Path(temp_name) / "project"
            _copy_project(root, temp_root, output_resolved)
            temp_source = _resolve_under(temp_root, plan.source_path)
            temp_source.write_text(mutated, encoding="utf-8")

            build = _run_build(temp_root, plan.foundry)
            build_valid = build["returnCode"] == 0 and build["timedOut"] is False
            test: dict[str, object] | None = None
            if build_valid:
                test = _run_selector(temp_root, mutation, plan.foundry)

            if not build_valid:
                spec_result = "inconclusive"
                execution_classification = "invalid_or_unbuilt_mutant"
            elif test is None or test["timedOut"] or test["returnCode"] not in {0, 1} or test["selectorObserved"] is not True:
                spec_result = "inconclusive"
                execution_classification = "inconclusive_execution"
            elif test["returnCode"] == 1:
                spec_result = "detected"
                execution_classification = "detected"
            else:
                spec_result = "survived"
                execution_classification = "survived"

            evidence_core = {
                "mutationId": mutation.mutation_id,
                "faultClass": mutation.fault_class,
                "sourceSha256": actual_source_sha,
                "mutantSha256": mutant_sha,
                "span": span,
                "build": build,
                "test": test,
                "classification": execution_classification,
            }
            evidence_sha = _canonical_sha256(evidence_core)
            mutation_results.append(
                {
                    "mutationId": mutation.mutation_id,
                    "faultClass": mutation.fault_class,
                    "description": mutation.description,
                    "sourceSha256": actual_source_sha,
                    "mutantSha256": mutant_sha,
                    "sourceSpan": span,
                    "diffSha256": _sha256_text(diff),
                    "build": build,
                    "test": test,
                    "classification": execution_classification,
                    "specAssuranceResult": spec_result,
                    "evidenceSha256": evidence_sha,
                }
            )
            spec_mutations.append(
                {
                    "mutationId": mutation.mutation_id,
                    "description": mutation.description,
                    "faultClass": mutation.fault_class,
                    "evidenceSha256": evidence_sha,
                    "result": spec_result,
                }
            )

    spec_document = {
        "schemaVersion": "spec-assurance-v0.1",
        "assuranceId": f"{plan.acquisition_id}.spec",
        "assuranceInvariantId": "CGQ-SPEC-001",
        "propertyInvariantId": plan.property_invariant_id,
        "propertyDescription": plan.property_description,
        "baseline": {
            "assessmentId": f"{plan.acquisition_id}.baseline",
            "evidenceSha256": baseline_evidence_sha,
            "status": baseline_status,
        },
        "activationWitness": {
            "observed": plan.activation_witness.observed,
            "evidenceSha256": plan.activation_witness.evidence_sha256,
            "description": plan.activation_witness.description,
        },
        "requiredFaultClasses": list(plan.required_fault_classes),
        "mutations": spec_mutations,
    }
    if plan.scope is not None:
        spec_document["scope"] = plan.scope
    spec_model = spec_assurance_model_from_dict(spec_document)
    spec_result = run_spec_assurance_model(spec_model)

    acquisition_complete = baseline_status == "pass" and all(
        item["specAssuranceResult"] in {"detected", "survived"} for item in mutation_results
    )
    result: dict[str, object] = {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "status": "pass" if acquisition_complete else "inconclusive",
        "acquisitionId": plan.acquisition_id,
        "planSha256": mutation_plan_sha256(plan),
        "sourcePath": plan.source_path,
        "sourceSha256": actual_source_sha,
        "foundryProfile": plan.foundry.profile,
        "baseline": {
            "status": baseline_status,
            "evidenceSha256": baseline_evidence_sha,
            "records": baseline_records,
        },
        "mutations": mutation_results,
        "specAssuranceModel": spec_document,
        "specAssurance": spec_result,
        "claimBoundary": (
            "Exact over the declared source SHA-256, unique reviewed text replacements, isolated Foundry build/test "
            "runs, and named test selectors. Compile-invalid mutants are INCONCLUSIVE rather than counted as detected. "
            "The adapter does not infer that the mutation operators or fault classes are complete, and it does not infer "
            "property activation; activation remains reviewed evidence consumed by CGQ-SPEC-001."
        ),
    }

    if output_resolved is not None:
        output_resolved.mkdir(parents=True, exist_ok=True)
        mutants_root = output_resolved / "mutants"
        for mutation, mutated, span, mutant_sha, diff in generated:
            mutant_source = mutants_root / mutation.mutation_id / plan.source_path
            mutant_source.parent.mkdir(parents=True, exist_ok=True)
            mutant_source.write_text(mutated, encoding="utf-8")
            metadata = {
                "mutationId": mutation.mutation_id,
                "faultClass": mutation.fault_class,
                "description": mutation.description,
                "sourcePath": plan.source_path,
                "sourceSha256": actual_source_sha,
                "mutantSha256": mutant_sha,
                "sourceSpan": span,
                "diffSha256": _sha256_text(diff),
                "diff": diff,
            }
            (mutants_root / mutation.mutation_id / "mutation.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        (output_resolved / "mutation-result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_resolved / "spec-assurance-model.json").write_text(
            json.dumps(spec_document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_resolved / "spec-assurance-result.json").write_text(
            json.dumps(spec_result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return result
