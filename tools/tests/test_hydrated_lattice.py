from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.execution_trace import execution_trace_from_dict, load_execution_trace  # noqa: E402
from contractgraph_qa.hydrated_lattice import (  # noqa: E402
    hydration_bindings_from_dict,
    load_hydration_bindings,
    run_hydrated_lattice,
)
from contractgraph_qa.solidity_lattice import check_target, profile_from_dict  # noqa: E402

HAS_FORGE = shutil.which("forge") is not None
STATIC_PROFILE = ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"
RACE_TRACE = ROOT / "scenarios" / "execution-trace-double-settlement-conflict.json"
RACE_BINDINGS = ROOT / "scenarios" / "hydration-bindings-escrow-race.json"


def _static_pass() -> dict[str, object]:
    return {
        "status": "pass",
        "extraction": {"astSha256": "a" * 64, "profileSha256": "b" * 64},
        "lifecycleVerification": {"status": "pass", "violations": []},
        "latticeTemplate": {
            "points": [
                {"state": "Created", "valuePresence": False, "safeTerminal": False},
                {"state": "Funded", "valuePresence": True, "safeTerminal": False},
                {"state": "Released", "valuePresence": False, "safeTerminal": True},
            ],
            "transitionTemplates": [
                {
                    "id": "fund:Created->Funded",
                    "sourceState": "Created",
                    "targetState": "Funded",
                    "versionDelta": 1,
                    "sourceEvidence": {"function": "fund"},
                },
                {
                    "id": "release:Funded->Released",
                    "sourceState": "Funded",
                    "targetState": "Released",
                    "versionDelta": 1,
                    "sourceEvidence": {"function": "release"},
                },
            ],
        },
    }


def _pass_trace(*, include_effect: bool = True, release_operation: str = "release", successor_version: int = 2):
    release_event: dict[str, object] = {
        "eventId": "evt-release",
        "sourceRef": "tx:release",
        "stateCommit": {
            "commitId": "commit:release",
            "conflictKey": "escrow:1",
            "parentState": "Funded",
            "parentVersion": 1,
            "operation": release_operation,
            "successorState": "Released",
            "successorVersion": successor_version,
            "committed": True,
        },
    }
    if include_effect:
        release_event["economicEffect"] = {
            "actionId": "escrow:1:release",
            "effectKey": "escrow-payout",
            "occurrenceId": "tx:release",
            "applied": True,
        }
    return execution_trace_from_dict(
        {
            "schemaVersion": "execution-trace-v0.1",
            "traceId": "trace-pass",
            "events": [
                {
                    "eventId": "evt-fund",
                    "sourceRef": "tx:fund",
                    "stateCommit": {
                        "commitId": "commit:fund",
                        "conflictKey": "escrow:1",
                        "parentState": "Created",
                        "parentVersion": 0,
                        "operation": "fund",
                        "successorState": "Funded",
                        "successorVersion": 1,
                        "committed": True,
                    },
                },
                release_event,
            ],
        }
    )


def _bindings(*, release_authority: str | None = "authority:buyer"):
    return hydration_bindings_from_dict(
        {
            "schemaVersion": "hydration-bindings-v0.1",
            "bindingId": "bindings-pass",
            "authorityRequiredOperations": ["fund", "release"],
            "timeSensitiveOperations": [],
            "commits": [
                {
                    "commitId": "commit:fund",
                    "authorityRef": "authority:buyer",
                    "evidenceRefs": ["tx:fund"],
                    "timeWitnessRefs": [],
                },
                {
                    "commitId": "commit:release",
                    "authorityRef": release_authority,
                    "evidenceRefs": ["tx:release"],
                    "timeWitnessRefs": [],
                },
            ],
        }
    )


class HydratedLatticeTest(unittest.TestCase):
    def test_full_composition_passes_when_all_claims_are_present(self) -> None:
        result = run_hydrated_lattice(_static_pass(), _pass_trace(), _bindings())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["staticRuntimeConformance"]["status"], "pass")
        self.assertEqual(result["bindingVerification"]["status"], "pass")
        self.assertEqual(result["runtimeVerification"]["economicCardinality"]["status"], "pass")
        self.assertEqual(result["runtimeVerification"]["successorConsistency"]["status"], "pass")

    def test_missing_authority_is_inconclusive_not_false_pass(self) -> None:
        result = run_hydrated_lattice(_static_pass(), _pass_trace(), _bindings(release_authority=None))
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["bindingVerification"]["status"], "inconclusive")
        self.assertIn("commit:release", result["bindingVerification"]["missingAuthorityCommitIds"])

    def test_runtime_transition_outside_static_lattice_fails(self) -> None:
        result = run_hydrated_lattice(
            _static_pass(),
            _pass_trace(release_operation="forceRelease"),
            _bindings(),
        )
        self.assertEqual(result["status"], "fail")
        violations = result["staticRuntimeConformance"]["violations"]
        self.assertTrue(any(item["kind"] == "runtime_transition_not_in_static_lattice" for item in violations))

    def test_runtime_version_jump_fails(self) -> None:
        result = run_hydrated_lattice(
            _static_pass(),
            _pass_trace(successor_version=3),
            _bindings(),
        )
        self.assertEqual(result["status"], "fail")
        violations = result["staticRuntimeConformance"]["violations"]
        self.assertTrue(any(item["kind"] == "non_unit_runtime_version_step" for item in violations))

    def test_missing_economic_projection_blocks_full_pass(self) -> None:
        result = run_hydrated_lattice(_static_pass(), _pass_trace(include_effect=False), _bindings())
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["runtimeVerification"]["economicCardinality"]["status"], "not_applicable")

    @unittest.skipUnless(HAS_FORGE, "forge is required for hydrated Solidity integration")
    def test_real_disputed_fixture_combines_static_and_runtime_failures(self) -> None:
        profile = profile_from_dict(json.loads(STATIC_PROFILE.read_text(encoding="utf-8")))
        static_result = check_target(
            "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
            profile,
            ROOT,
        )
        result = run_hydrated_lattice(
            static_result,
            load_execution_trace(RACE_TRACE),
            load_hydration_bindings(RACE_BINDINGS),
        )
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["staticLifecycle"]["status"], "fail")
        self.assertEqual(result["staticRuntimeConformance"]["status"], "pass")
        self.assertEqual(result["bindingVerification"]["status"], "pass")
        self.assertEqual(result["runtimeVerification"]["economicCardinality"]["status"], "fail")
        self.assertEqual(result["runtimeVerification"]["successorConsistency"]["status"], "fail")


if __name__ == "__main__":
    unittest.main()
