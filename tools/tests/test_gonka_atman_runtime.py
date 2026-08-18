from contractgraph_qa.gonka_atman_runtime import verify_restart_lineage, verify_runtime_fingerprint

PIN = "379bebced638aeb5e6077bfd51c986f898443832"


def fp():
    return {
        "source_revision": PIN,
        "config_generation": "g005-testenv-1",
        "runtime_artifacts": [
            {"component": "devshardctl", "sha256": "sha256:" + "1" * 64},
            {"component": "versiond", "sha256": "sha256:" + "2" * 64},
            {"component": "devshardd", "sha256": "sha256:" + "3" * 64},
        ],
    }


def test_runtime_fingerprint_fails_closed_without_runtime_artifacts():
    out = verify_runtime_fingerprint({"source_revision": PIN, "config_generation": "x"})
    assert out["verdict"] == "UNPROVEN"
    assert out["target_claim_allowed"] is False


def test_runtime_fingerprint_rejects_wrong_source_generation():
    payload = fp(); payload["source_revision"] = "0" * 40
    out = verify_runtime_fingerprint(payload)
    assert out["verdict"] == "MISMATCH"


def test_runtime_fingerprint_requires_three_execution_components():
    payload = fp(); payload["runtime_artifacts"] = payload["runtime_artifacts"][:2]
    out = verify_runtime_fingerprint(payload)
    assert out["verdict"] == "UNPROVEN"
    assert "devshardd" in out["missing_components"]


def test_restart_lineage_inconclusive_until_runtime_proven():
    out = verify_restart_lineage({"runtime_fingerprint": {}, "logical_operation_id": "op-1", "attempts": [{"nonce": 1}]})
    assert out["verdict"] == "INCONCLUSIVE"
    assert out["target_claim_allowed"] is False


def test_restart_lineage_passes_reconciled_case():
    out = verify_restart_lineage({
        "runtime_fingerprint": fp(),
        "logical_operation_id": "op-1",
        "attempts": [{"nonce": 1}, {"nonce": 2}],
        "unexplained_effects": [],
        "accounting_reconciles": True,
        "settlement_reconciles": True,
    })
    assert out["verdict"] == "PASS"
    assert out["attempt_nonces"] == [1, 2]


def test_restart_lineage_flags_unexplained_effects():
    out = verify_restart_lineage({
        "runtime_fingerprint": fp(),
        "logical_operation_id": "op-1",
        "attempts": [{"nonce": 1}],
        "unexplained_effects": ["orphan accounting row"],
        "accounting_reconciles": False,
        "settlement_reconciles": True,
    })
    assert out["verdict"] == "FAIL_HYPOTHESIS"
