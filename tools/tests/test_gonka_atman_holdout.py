from contractgraph_qa.gonka_atman import GonkaAtmanError
from contractgraph_qa.gonka_atman_holdout import evaluate_revealed_holdout, seal_holdout_case


def _case():
    return {
        "case_id": "G-HOLDOUT-001",
        "logical_operation_id": "op-hidden-001",
        "source_revision": "rev-1",
        "runtime_generation": "gen-1",
        "evidence_generation": "gen-1",
        "hypotheses": [
            "PROTOCOL_TIME_DELAY",
            "SETTLEMENT_RECONCILIATION_FAILURE",
        ],
        "observed_evidence": [],
        "policy_id": "gonka-atman-policy-v0.1-frozen",
    }


def test_seal_rejects_target_leakage():
    case = _case()
    case["target_cause"] = "PROTOCOL_TIME_DELAY"
    try:
        seal_holdout_case(case)
    except GonkaAtmanError as exc:
        assert "target/oracle" in str(exc)
    else:
        raise AssertionError("target leakage must be rejected")


def test_seal_is_deterministic():
    a = seal_holdout_case(_case())
    b = seal_holdout_case(_case())
    assert a == b
    assert a["target_revealed"] is False


def test_reveal_can_show_atman_earlier_without_rewriting_case():
    sealed = seal_holdout_case(_case())
    result = evaluate_revealed_holdout(
        sealed,
        {
            "target_cause": "PROTOCOL_TIME_DELAY",
            "resolving_check_id": "WAIT_NEXT_PROTOCOL_DIFF",
        },
    )
    assert result["atman_first_check"] == "WAIT_NEXT_PROTOCOL_DIFF"
    assert result["baseline_checks_to_resolution"] == 2
    assert result["atman_checks_to_resolution"] == 1
    assert result["evidence_checks_saved"] == 1
    assert result["verdict"] == "ATMAN_EARLIER"


def test_tampered_sealed_case_is_rejected():
    sealed = seal_holdout_case(_case())
    sealed["case"]["hypotheses"] = ["DUPLICATE_EXECUTION"]
    try:
        evaluate_revealed_holdout(
            sealed,
            {
                "target_cause": "DUPLICATE_EXECUTION",
                "resolving_check_id": "RECONCILE_EXECUTION_NONCES",
            },
        )
    except GonkaAtmanError as exc:
        assert "commitment mismatch" in str(exc)
    else:
        raise AssertionError("tampering must be rejected")
