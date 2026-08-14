from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contractgraph_qa.fcrp_v02 import FCRPV02Error, evaluate_fcrp_v02_case


CASE_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "fcrp-v0.2"
    / "FCRP-V02-PORT-001-liminalosai-authority.json"
)


def load_case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def test_v02_portability_case_passes_without_granting_mutation_authority() -> None:
    case = load_case()
    result = evaluate_fcrp_v02_case(case)

    assert result["schema"] == "cgqa.fcrp-result.v0.2"
    assert result["caseId"] == "FCRP-V02-PORT-001"
    assert result["decision"] == "PASS"
    assert result["firstMeaningfulDivergence"] == "N1"
    assert result["causePoint"] == "N1"
    assert result["refactorPoint"] == "N3"
    assert result["navigationDirection"] == "UP"
    assert result["primaryTimeDomain"] == "CAUSAL_SEQUENCE"
    assert result["simulationStatus"] == "PASS"
    assert result["mutationAuthorized"] is False
    assert result["causalPropagationStopped"] is True
    assert result["stopConditionsSatisfied"] is True
    assert result["evidenceStrengths"]["E-LIMINAL-SELF009"] == "RECOMPUTABLE"
    assert result["decision"] == case["expectedProtocolDecision"]


def test_evidence_cannot_grant_authority() -> None:
    case = load_case()
    case["evidence"][0]["mayGrantAuthority"] = True

    with pytest.raises(FCRPV02Error, match="may not itself grant authority"):
        evaluate_fcrp_v02_case(case)


def test_authorization_boundary_cannot_promote_evidence_to_authority() -> None:
    case = load_case()
    case["authorization"]["evidenceMayGrantAuthority"] = True

    with pytest.raises(FCRPV02Error, match="must be false"):
        evaluate_fcrp_v02_case(case)


def test_mutation_authority_requires_separate_authorization_reference() -> None:
    case = load_case()
    case["authorization"]["mutationAuthorized"] = True
    case["authorization"]["authorizationRef"] = None

    with pytest.raises(FCRPV02Error, match="authorizationRef"):
        evaluate_fcrp_v02_case(case)


def test_causal_advance_requires_evidence_when_the_time_model_requires_it() -> None:
    case = load_case()
    case["timeModel"]["causalAdvanceRequired"] = True
    case["timeModel"]["causalAdvanceEvidenceRefs"] = []

    with pytest.raises(FCRPV02Error, match="causalAdvanceEvidenceRefs"):
        evaluate_fcrp_v02_case(case)


def test_upward_not_required_needs_explicit_causal_propagation_stop() -> None:
    case = load_case()
    case["verification"]["upward"] = "NOT_REQUIRED"
    case["verification"]["stopConditions"]["causalPropagationStopped"] = False

    with pytest.raises(FCRPV02Error, match="all four stop conditions"):
        evaluate_fcrp_v02_case(case)


def test_simulation_failure_blocks_even_when_local_and_upward_verification_pass() -> None:
    case = load_case()
    case["simulation"]["status"] = "FAIL"
    case["simulation"]["evidenceRefs"] = ["E-LIMINAL-SELF009"]

    result = evaluate_fcrp_v02_case(case)
    assert result["decision"] == "BLOCK"


def test_v01_module_remains_independent() -> None:
    from contractgraph_qa.fcrp import FCRP_SCHEMA

    assert FCRP_SCHEMA == "cgqa.fcrp-case.v0.1"
    assert load_case()["schema"] != FCRP_SCHEMA
