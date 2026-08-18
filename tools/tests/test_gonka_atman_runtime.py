from contractgraph_qa.gonka_atman_runtime import verify_restart_lineage, verify_runtime_fingerprint

PIN = "379bebced638aeb5e6077bfd51c986f898443832"


def artifact(component, ch):
    return {
        "component": component,
        "container_id": f"container-{component}",
        "image_id": f"image-{component}",
        "image_ref": f"local/{component}:g005",
        "image_digest": "sha256:" + ch * 64,
    }


def fp():
    arts = [artifact("devshardctl", "1"), artifact("versiond", "2"), artifact("devshardd", "3")]
    return {
        "source_revision": PIN,
        "config_generation": "g005-testenv-1",
        "runtime_artifacts": arts,
        "provenance": {
            "method": "local-build-from-pinned-source",
            "source_revision": PIN,
            "evidence_sha256": "sha256:" + "a" * 64,
            "component_image_digests": {x["component"]: x["image_digest"] for x in arts},
        },
    }


def test_runtime_fingerprint_fails_closed_without_runtime_artifacts():
    out = verify_runtime_fingerprint({"source_revision": PIN, "config_generation": "x", "provenance": {}})
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


def test_metadata_digest_without_provenance_is_never_proven():
    payload = fp(); payload.pop("provenance")
    out = verify_runtime_fingerprint(payload)
    assert out["verdict"] == "UNPROVEN"
    assert "provenance" in out["missing"]


def test_runtime_digest_must_match_provenance_binding():
    payload = fp()
    payload["provenance"]["component_image_digests"]["devshardctl"] = "sha256:" + "f" * 64
    out = verify_runtime_fingerprint(payload)
    assert out["verdict"] == "MISMATCH"
    assert out["target_claim_allowed"] is False


def test_runtime_fingerprint_proven_only_with_source_image_binding():
    out = verify_runtime_fingerprint(fp())
    assert out["verdict"] == "PROVEN"
    assert out["target_claim_allowed"] is True


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
