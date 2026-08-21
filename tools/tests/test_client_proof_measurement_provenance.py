from __future__ import annotations

import copy
import unittest

from contractgraph_qa.change_gate_measurement import (
    build_change_gate_measurement_artifacts,
    provenance_result_from_change_gate_input,
)
from contractgraph_qa.client_proof import (
    attach_change_gate_evidence,
    attach_measurement_provenance_evidence,
    build_measurement_provenance_evidence,
    measurement_provenance_result_sha256,
    verify_measurement_provenance_evidence,
)
from contractgraph_qa.measurement_provenance import MeasurementProvenanceError


GATE_RESULT = {
    "schemaVersion": 1,
    "status": "pass",
    "baseCommitSha": "a" * 40,
    "headCommitSha": "b" * 40,
    "models": [{"id": "adapter"}, {"id": "new-model"}],
}
BASE_CONFIG = b'schemaVersion = 1\n[[models]]\nid = "adapter"\npath = "a.json"\n'
HEAD_CONFIG = (
    b'schemaVersion = 1\n'
    b'[[models]]\nid = "adapter"\npath = "a.json"\n'
    b'[[models]]\nid = "new-model"\npath = "b.json"\n'
)


def passing_artifacts() -> tuple[dict[str, object], dict[str, object]]:
    payload, source = build_change_gate_measurement_artifacts(
        GATE_RESULT,
        base_model_ids=("adapter",),
        head_model_ids=("adapter", "new-model"),
        base_config_bytes=BASE_CONFIG,
        head_config_bytes=HEAD_CONFIG,
    )
    return provenance_result_from_change_gate_input(payload), source


def blocked_artifacts() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    gate_result = copy.deepcopy(GATE_RESULT)
    gate_result["models"] = [{"id": "adapter"}]
    payload, source = build_change_gate_measurement_artifacts(
        gate_result,
        base_model_ids=("adapter",),
        head_model_ids=("adapter", "new-model"),
        base_config_bytes=BASE_CONFIG,
        head_config_bytes=HEAD_CONFIG,
    )
    return provenance_result_from_change_gate_input(payload), source, gate_result


class ClientProofMeasurementProvenanceTests(unittest.TestCase):
    def test_binding_preserves_exact_recomputed_result_and_source(self) -> None:
        result, source = passing_artifacts()
        evidence = build_measurement_provenance_evidence(
            result, source, gate_result=GATE_RESULT
        )
        self.assertEqual(evidence["provenanceResult"], result)
        self.assertEqual(evidence["source"], source)
        self.assertEqual(
            evidence["provenanceResultSha256"],
            measurement_provenance_result_sha256(result),
        )
        self.assertEqual(
            verify_measurement_provenance_evidence(
                evidence, gate_result=GATE_RESULT
            ),
            result,
        )

    def test_nested_tamper_is_rejected_even_before_digest_check(self) -> None:
        result, source = passing_artifacts()
        tampered = copy.deepcopy(result)
        tampered["measurements"][0]["coverageFraction"] = 0.5
        with self.assertRaisesRegex(
            MeasurementProvenanceError, "recomputed provenance verdict"
        ):
            build_measurement_provenance_evidence(
                tampered, source, gate_result=GATE_RESULT
            )

    def test_source_receipt_cannot_be_replayed_to_another_gate_result(self) -> None:
        result, source = passing_artifacts()
        evidence = build_measurement_provenance_evidence(
            result, source, gate_result=GATE_RESULT
        )
        different_gate = copy.deepcopy(GATE_RESULT)
        different_gate["headCommitSha"] = "c" * 40
        with self.assertRaisesRegex(
            MeasurementProvenanceError, "gate-result digest mismatch"
        ):
            verify_measurement_provenance_evidence(
                evidence, gate_result=different_gate
            )

    def test_blocked_provenance_remains_diagnostic_but_cannot_be_authority(self) -> None:
        result, source, gate_result = blocked_artifacts()
        evidence = build_measurement_provenance_evidence(
            result, source, gate_result=gate_result
        )
        self.assertEqual(
            verify_measurement_provenance_evidence(
                evidence, gate_result=gate_result
            )["status"],
            "blocked",
        )
        proof = attach_change_gate_evidence({"schemaVersion": 2}, gate_result)
        with self.assertRaisesRegex(ValueError, "cannot be bound"):
            attach_measurement_provenance_evidence(proof, result, source)

    def test_attach_does_not_mutate_existing_proof(self) -> None:
        result, source = passing_artifacts()
        proof = attach_change_gate_evidence({"schemaVersion": 2}, GATE_RESULT)
        original = copy.deepcopy(proof)
        bound = attach_measurement_provenance_evidence(proof, result, source)
        self.assertEqual(proof, original)
        self.assertEqual(bound["changeGateEvidence"], original["changeGateEvidence"])
        self.assertEqual(
            bound["measurementProvenanceEvidence"]["provenanceResult"]["status"],
            "pass",
        )

    def test_conflicting_source_rebind_fails_closed(self) -> None:
        result, source = passing_artifacts()
        proof = attach_change_gate_evidence({"schemaVersion": 2}, GATE_RESULT)
        bound = attach_measurement_provenance_evidence(proof, result, source)
        _, changed_source = build_change_gate_measurement_artifacts(
            GATE_RESULT,
            base_model_ids=("adapter",),
            head_model_ids=("adapter", "new-model"),
            base_config_bytes=BASE_CONFIG,
            head_config_bytes=HEAD_CONFIG + b"\n# same semantics, different exact source bytes\n",
        )
        with self.assertRaisesRegex(ValueError, "already contains different"):
            attach_measurement_provenance_evidence(
                bound, result, changed_source
            )


if __name__ == "__main__":
    unittest.main()
