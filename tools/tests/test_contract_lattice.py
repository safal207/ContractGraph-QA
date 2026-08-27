from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_OK, EXIT_VALIDATION, main as cli_main  # noqa: E402
from contractgraph_qa.contract_lattice import (  # noqa: E402
    BINDING_INVARIANT,
    LIVENESS_INVARIANT,
    TIME_INVARIANT,
    VERSION_INVARIANT,
    contract_lattice_from_dict,
    contract_lattice_sha256,
    load_contract_lattice,
    run_contract_lattice,
)

FIXTURE = ROOT / "scenarios" / "contract-lattice-disputed-dead-end.json"


def _document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class ContractLatticeTest(unittest.TestCase):
    def test_disputed_dead_end_is_reachable_value_liveness_failure(self) -> None:
        result = run_contract_lattice(load_contract_lattice(FIXTURE))

        self.assertEqual(result["status"], "fail")
        live = [item for item in result["violations"] if item["invariantId"] == LIVENESS_INVARIANT]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["pointId"], "Disputed@2")
        self.assertEqual(live[0]["counterexamplePath"], ["Created@0", "Funded@1", "Disputed@2"])
        self.assertEqual(live[0]["lockedValue"], 10000000)

    def test_resolution_transition_restores_liveness(self) -> None:
        data = _document()
        data["points"].append(
            {
                "id": "DisputeRefunded@3",
                "state": "Refunded",
                "version": 3,
                "lockedValue": 0,
                "authorityRefs": [],
                "evidenceRefs": ["dispute-resolution"],
                "timeWitnessRefs": [],
            }
        )
        data["safeTerminals"].append("DisputeRefunded@3")
        data["transitions"].append(
            {
                "id": "resolveDispute",
                "source": "Disputed@2",
                "target": "DisputeRefunded@3",
                "action": "resolveDispute",
                "authorityRef": "participant-authority",
                "evidenceRefs": ["dispute-raised"],
                "timeSensitive": False,
                "timeWitnessRefs": [],
            }
        )

        result = run_contract_lattice(contract_lattice_from_dict(data))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])

    def test_time_sensitive_transition_requires_explicit_witness(self) -> None:
        data = _document()
        data["transitions"][1]["timeSensitive"] = True
        result = run_contract_lattice(contract_lattice_from_dict(data))

        time_violations = [item for item in result["violations"] if item["invariantId"] == TIME_INVARIANT]
        self.assertTrue(any(item["kind"] == "time_sensitive_transition_without_witness" for item in time_violations))

    def test_bound_time_witness_is_accepted(self) -> None:
        data = _document()
        funded = next(item for item in data["points"] if item["id"] == "Funded@1")
        funded["timeWitnessRefs"] = ["deadline-check-T"]
        release = next(item for item in data["transitions"] if item["id"] == "release")
        release["timeSensitive"] = True
        release["timeWitnessRefs"] = ["deadline-check-T"]

        result = run_contract_lattice(contract_lattice_from_dict(data))
        time_violations = [item for item in result["violations"] if item["invariantId"] == TIME_INVARIANT]
        self.assertEqual(time_violations, [])

    def test_unbound_authority_fails(self) -> None:
        data = _document()
        data["transitions"][0]["authorityRef"] = "unknown-authority"
        result = run_contract_lattice(contract_lattice_from_dict(data))

        binding = [item for item in result["violations"] if item["invariantId"] == BINDING_INVARIANT]
        self.assertTrue(any(item["kind"] == "authority_not_bound_at_source" for item in binding))

    def test_unbound_evidence_fails(self) -> None:
        data = _document()
        data["transitions"][0]["evidenceRefs"] = ["missing-evidence"]
        result = run_contract_lattice(contract_lattice_from_dict(data))

        binding = [item for item in result["violations"] if item["invariantId"] == BINDING_INVARIANT]
        self.assertTrue(any(item["kind"] == "evidence_not_bound_at_source" for item in binding))

    def test_non_unit_version_step_fails(self) -> None:
        data = _document()
        funded = next(item for item in data["points"] if item["id"] == "Funded@1")
        funded["version"] = 5
        result = run_contract_lattice(contract_lattice_from_dict(data))

        version = [item for item in result["violations"] if item["invariantId"] == VERSION_INVARIANT]
        self.assertTrue(version)

    def test_unreachable_locked_trap_is_not_a_liveness_failure(self) -> None:
        data = _document()
        data["points"].append(
            {
                "id": "Ghost@9",
                "state": "Ghost",
                "version": 9,
                "lockedValue": 999,
                "authorityRefs": [],
                "evidenceRefs": [],
                "timeWitnessRefs": [],
            }
        )
        result = run_contract_lattice(contract_lattice_from_dict(data))
        live = [item for item in result["violations"] if item["invariantId"] == LIVENESS_INVARIANT]
        self.assertFalse(any(item["pointId"] == "Ghost@9" for item in live))

    def test_model_hash_is_deterministic(self) -> None:
        first = load_contract_lattice(FIXTURE)
        second = load_contract_lattice(FIXTURE)
        self.assertEqual(contract_lattice_sha256(first), contract_lattice_sha256(second))

    def test_safe_terminal_cannot_hold_locked_value(self) -> None:
        data = _document()
        released = next(item for item in data["points"] if item["id"] == "Released@2")
        released["lockedValue"] = 1
        with self.assertRaisesRegex(ValueError, "cannot retain lockedValue"):
            contract_lattice_from_dict(data)

    def test_cli_failure_returns_validation_exit_and_counterexample(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli_main(["contract-lattice-check", "--model", str(FIXTURE)])
        self.assertEqual(code, EXIT_VALIDATION)
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["dimensions"], ["state", "version", "value", "authority", "evidence", "timeWitness"])

    def test_cli_pass_returns_zero(self) -> None:
        data = _document()
        data["points"].append(
            {
                "id": "DisputeRefunded@3",
                "state": "Refunded",
                "version": 3,
                "lockedValue": 0,
                "authorityRefs": [],
                "evidenceRefs": ["dispute-resolution"],
                "timeWitnessRefs": [],
            }
        )
        data["safeTerminals"].append("DisputeRefunded@3")
        data["transitions"].append(
            {
                "id": "resolveDispute",
                "source": "Disputed@2",
                "target": "DisputeRefunded@3",
                "action": "resolveDispute",
                "authorityRef": "participant-authority",
                "evidenceRefs": ["dispute-raised"],
                "timeSensitive": False,
                "timeWitnessRefs": [],
            }
        )
        path = ROOT / ".contract-lattice-pass-test.json"
        try:
            path.write_text(json.dumps(data), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cli_main(["contract-lattice-check", "--model", str(path)])
            self.assertEqual(code, EXIT_OK)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "pass")
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
