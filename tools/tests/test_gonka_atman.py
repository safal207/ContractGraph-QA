from contractgraph_qa.gonka_atman import GonkaAtmanError, select_next_best_evidence


def _base():
    return {
        "case_id": "G-004",
        "logical_operation_id": "op-42",
        "source_revision": "f040d0a5",
        "runtime_generation": "img-v7",
        "expected_runtime_generation": "img-v7",
        "evidence_generation": "img-v7",
        "hypotheses": [
            "PROTOCOL_TIME_DELAY",
            "SETTLEMENT_RECONCILIATION_FAILURE",
        ],
        "observed_evidence": [],
    }


def test_protocol_time_pair_selects_next_protocol_diff():
    result = select_next_best_evidence(_base())
    assert result["action"] == "COLLECT_MORE_EVIDENCE"
    assert result["next_best_evidence"]["check_id"] == "WAIT_NEXT_PROTOCOL_DIFF"
    assert result["target_claim_allowed"] is False


def test_generation_mismatch_preempts_target_interpretation():
    payload = _base()
    payload["runtime_generation"] = "stale-image"
    result = select_next_best_evidence(payload)
    assert result["generation"]["verdict"] == "VERIFIER_GENERATION_MISMATCH"
    assert result["next_best_evidence"]["check_id"] == "COMPARE_RUNTIME_FINGERPRINT"
    assert result["target_claim_allowed"] is False


def test_duplicate_execution_prefers_nonce_reconciliation():
    payload = _base()
    payload["hypotheses"] = [
        "DUPLICATE_EXECUTION",
        "ACCOUNTING_LOOKUP_FAILURE",
    ]
    result = select_next_best_evidence(payload)
    assert result["next_best_evidence"]["check_id"] == "RECONCILE_EXECUTION_NONCES"


def test_observed_check_is_not_selected_again():
    payload = _base()
    payload["observed_evidence"] = ["WAIT_NEXT_PROTOCOL_DIFF"]
    result = select_next_best_evidence(payload)
    assert result["next_best_evidence"]["check_id"] == "RECONCILE_SETTLEMENT_REFS"


def test_unknown_hypothesis_is_rejected():
    payload = _base()
    payload["hypotheses"] = ["MAGIC_CAUSE"]
    try:
        select_next_best_evidence(payload)
    except GonkaAtmanError as exc:
        assert "unsupported hypothesis" in str(exc)
    else:
        raise AssertionError("expected GonkaAtmanError")
