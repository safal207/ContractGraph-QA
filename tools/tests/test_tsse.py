from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.causal_temporal_utils import canonical_sha256  # noqa: E402
from contractgraph_qa.tsse import (  # noqa: E402
    TSSEError,
    load_tsse_model,
    run_tsse_model,
    validate_tsse_model,
)


EXACT_SUBJECT = {
    "repository": "https://github.com/Uniswap/v4-core",
    "commit": "a" * 64,
    "adapter": "foundry-state-observer-v0.1",
}
SUBJECT_HASH = canonical_sha256(EXACT_SUBJECT)


def _node(
    node_id: str,
    *,
    step: int,
    phase: str,
    combined_destination: bool = False,
) -> dict[str, object]:
    return {
        "id": node_id,
        "subjectHash": SUBJECT_HASH,
        "time": {
            "block": 100 + step,
            "timestamp": 1_000 + step,
            "epoch": 8 if combined_destination else 7,
            "causalStep": step,
        },
        "space": {
            "chainId": "31337",
            "contract": "Hook" if combined_destination else "PoolManager",
            "callFrame": "hook-callback" if combined_destination else "unlock-entry",
            "storageDomain": "hook-session" if combined_destination else "pool-manager",
            "protocolLocation": "pool:A/hook" if combined_destination else "pool:A",
        },
        "state": {
            "phase": phase,
            "stateHash": f"{step:x}" * 64,
            "values": {
                "currencyDelta": "7" if combined_destination else "0",
                "liquidity": "1000",
            },
        },
        "environment": {
            "oracleState": "stale-boundary" if combined_destination else "fresh",
            "tokenModel": "erc777-callback" if combined_destination else "erc20-standard",
            "feeMode": "dynamic" if combined_destination else "static",
            "implementation": "Hook@a1" if combined_destination else "PoolManager@a1",
            "externalStateHash": "4" * 64 if combined_destination else "3" * 64,
        },
        "actor": {"identity": "0xabc", "role": "swapper"},
        "authority": {"epoch": 7, "status": "valid"},
        "value": {"unit": "token0", "locked": 10, "moved": 0},
    }


def valid_tsse_model() -> dict[str, object]:
    return {
        "schema": "cgqa/tsse-transition-model/v0.1",
        "modelId": "uniswap-v4-tsse-001",
        "exactSubject": copy.deepcopy(EXACT_SUBJECT),
        "nodes": [
            _node("n0", step=0, phase="LOCKED_CLEAN"),
            _node(
                "n1",
                step=1,
                phase="UNLOCKED_CALLBACK_DIRTY",
                combined_destination=True,
            ),
        ],
        "transitions": [
            {
                "id": "t0",
                "sequence": 0,
                "predecessorId": None,
                "sourceId": "n0",
                "targetId": "n1",
                "cause": "swapper enters unlock and invokes the configured hook",
                "action": "unlock_and_callback",
                "evidenceRefs": ["ev-0"],
                "crossedBoundaries": ["time", "space", "state", "environment"],
            }
        ],
        "invariants": [
            {
                "id": "CGQ-TSSE-001",
                "kind": "safety",
                "description": "A declared TSSE path preserves causal and subject continuity.",
            }
        ],
        "forbiddenTransitions": [
            {
                "id": "terminal-resurrection",
                "fromPhase": "SETTLED",
                "toPhase": "UNLOCKED_CALLBACK_DIRTY",
                "invariantId": "CGQ-TSSE-001",
            }
        ],
        "requirements": {
            "requireMonotonicTime": True,
            "requireCausalContinuity": True,
            "requireExactSubjectBinding": True,
            "requireEvidenceBindings": True,
        },
        "evidence": [
            {
                "id": "ev-0",
                "subjectHash": SUBJECT_HASH,
                "kind": "execution-trace",
                "source": "anvil-trace:0xabc",
                "digest": "d" * 64,
            }
        ],
        "scope": "Synthetic local replay; no claim of production completeness.",
    }


def _with_second_transition(model: dict[str, object]) -> dict[str, object]:
    extended = copy.deepcopy(model)
    nodes = extended["nodes"]
    assert isinstance(nodes, list)
    n2 = copy.deepcopy(nodes[1])
    assert isinstance(n2, dict)
    n2["id"] = "n2"
    n2["time"] = {"block": 102, "timestamp": 1_002, "epoch": 8, "causalStep": 2}
    n2["state"] = {
        "phase": "SETTLED",
        "stateHash": "2" * 64,
        "values": {"currencyDelta": "0", "liquidity": "1000"},
    }
    nodes.append(n2)

    transitions = extended["transitions"]
    assert isinstance(transitions, list)
    transitions.append(
        {
            "id": "t1",
            "sequence": 1,
            "predecessorId": "t0",
            "sourceId": "n1",
            "targetId": "n2",
            "cause": "callback returns and all deltas are settled",
            "action": "settle",
            "evidenceRefs": ["ev-1"],
            "crossedBoundaries": ["time", "state"],
        }
    )
    evidence = extended["evidence"]
    assert isinstance(evidence, list)
    evidence.append(
        {
            "id": "ev-1",
            "subjectHash": SUBJECT_HASH,
            "kind": "execution-trace",
            "source": "anvil-trace:0xdef",
            "digest": "e" * 64,
        }
    )
    return extended


def _violation_codes(result: dict[str, object]) -> set[str]:
    violations = result["violations"]
    assert isinstance(violations, list)
    return {
        str(item["code"])
        for item in violations
        if isinstance(item, dict) and "code" in item
    }


class TSSEModelTest(unittest.TestCase):
    def test_load_tsse_model_reads_and_validates_json(self) -> None:
        expected = valid_tsse_model()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            path.write_text(json.dumps(expected), encoding="utf-8")
            loaded = load_tsse_model(path)

        self.assertEqual(run_tsse_model(loaded), run_tsse_model(expected))

    def test_valid_combined_time_space_state_environment_transition(self) -> None:
        model = valid_tsse_model()
        self.assertIsNotNone(validate_tsse_model(copy.deepcopy(model)))

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["subjectHash"], SUBJECT_HASH)
        self.assertRegex(str(result["modelHash"]), r"^[0-9a-f]{64}$")
        self.assertTrue(result["claimBoundary"])
        self.assertEqual(
            result["phaseTransitions"],
            [
                {
                    "transitionId": "t0",
                    "fromPhase": "LOCKED_CLEAN",
                    "toPhase": "UNLOCKED_CALLBACK_DIRTY",
                    "phaseChanged": True,
                    "changedDimensions": ["time", "space", "state", "environment"],
                    "classification": "time+space+state+environment",
                    "declaredBoundaries": ["time", "space", "state", "environment"],
                    "forbiddenTransitionIds": [],
                }
            ],
        )
        self.assertEqual(
            result["crossedBoundaryCounts"],
            {
                "time": 1,
                "space": 1,
                "state": 1,
                "environment": 1,
                "actor": 0,
                "authority": 0,
                "value": 0,
            },
        )

    def test_non_monotonic_timestamp_places_model_on_hold(self) -> None:
        model = valid_tsse_model()
        model["nodes"][1]["time"]["timestamp"] = 999  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("NON_MONOTONIC_TIME", _violation_codes(result))

    def test_causal_step_must_advance_by_exactly_one(self) -> None:
        model = valid_tsse_model()
        model["nodes"][1]["time"]["causalStep"] = 2  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("CAUSAL_STEP_DISCONTINUITY", _violation_codes(result))

    def test_predecessor_chain_must_match_sequence(self) -> None:
        model = _with_second_transition(valid_tsse_model())
        model["transitions"][1]["predecessorId"] = None  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("PREDECESSOR_DISCONTINUITY", _violation_codes(result))

    def test_target_to_next_source_continuity_is_required(self) -> None:
        model = _with_second_transition(valid_tsse_model())
        model["transitions"][1]["sourceId"] = "n0"  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("PATH_CONTINUITY_BROKEN", _violation_codes(result))

    def test_exact_subject_mismatch_cannot_become_pass(self) -> None:
        model = valid_tsse_model()
        model["nodes"][1]["subjectHash"] = "b" * 64  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("EXACT_SUBJECT_MISMATCH", _violation_codes(result))

    def test_required_evidence_binding_cannot_be_empty(self) -> None:
        model = valid_tsse_model()
        model["transitions"][0]["evidenceRefs"] = []  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("EVIDENCE_BINDING_MISSING", _violation_codes(result))

    def test_declared_boundaries_are_checked_against_observed_changes(self) -> None:
        model = valid_tsse_model()
        model["transitions"][0]["crossedBoundaries"] = ["time", "space", "state"]  # type: ignore[index]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("BOUNDARY_DECLARATION_MISMATCH", _violation_codes(result))
        self.assertEqual(
            result["phaseTransitions"][0]["classification"],  # type: ignore[index]
            "time+space+state+environment",
        )

    def test_forbidden_phase_transition_places_model_on_hold(self) -> None:
        model = valid_tsse_model()
        model["forbiddenTransitions"] = [
            {
                "id": "dirty-unlock",
                "fromPhase": "LOCKED_CLEAN",
                "toPhase": "UNLOCKED_CALLBACK_DIRTY",
                "invariantId": "CGQ-TSSE-001",
            }
        ]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("FORBIDDEN_PHASE_TRANSITION", _violation_codes(result))
        self.assertEqual(
            result["phaseTransitions"][0]["forbiddenTransitionIds"],  # type: ignore[index]
            ["dirty-unlock"],
        )

    def test_unknown_fields_are_rejected_at_every_model_layer(self) -> None:
        cases: list[tuple[str, dict[str, object]]] = []
        for label in (
            "model",
            "subject",
            "node",
            "time",
            "space",
            "state",
            "environment",
            "actor",
            "authority",
            "value",
            "transition",
            "invariant",
            "forbidden",
            "requirements",
            "evidence",
        ):
            model = valid_tsse_model()
            if label == "model":
                target = model
            elif label == "subject":
                target = model["exactSubject"]  # type: ignore[assignment]
            elif label in {"node", "time", "space", "state", "environment", "actor", "authority", "value"}:
                node = model["nodes"][0]  # type: ignore[index]
                target = node if label == "node" else node[label]
            elif label == "transition":
                target = model["transitions"][0]  # type: ignore[index]
            elif label == "invariant":
                target = model["invariants"][0]  # type: ignore[index]
            elif label == "forbidden":
                target = model["forbiddenTransitions"][0]  # type: ignore[index]
            elif label == "requirements":
                target = model["requirements"]  # type: ignore[assignment]
            else:
                target = model["evidence"][0]  # type: ignore[index]
            assert isinstance(target, dict)
            target["unexpected"] = True
            cases.append((label, model))

        for label, model in cases:
            with self.subTest(layer=label):
                with self.assertRaises(TSSEError):
                    validate_tsse_model(model)

    def test_unknown_transition_node_id_is_a_structural_error(self) -> None:
        model = valid_tsse_model()
        model["transitions"][0]["targetId"] = "not-a-node"  # type: ignore[index]
        with self.assertRaises(TSSEError):
            validate_tsse_model(model)

    def test_boundaries_are_normalized_to_canonical_enum_order(self) -> None:
        model = valid_tsse_model()
        model["transitions"][0]["crossedBoundaries"] = [  # type: ignore[index]
            "environment",
            "state",
            "space",
            "time",
        ]

        validated = validate_tsse_model(model)

        self.assertEqual(
            validated["transitions"][0]["crossedBoundaries"],
            ["time", "space", "state", "environment"],
        )
        self.assertEqual(run_tsse_model(model)["status"], "pass")
        self.assertEqual(
            run_tsse_model(model)["modelHash"],
            run_tsse_model(valid_tsse_model())["modelHash"],
        )

    def test_duplicate_json_keys_are_rejected_before_policy_can_be_weakened(self) -> None:
        model = valid_tsse_model()
        rendered = json.dumps(model)
        needle = '"requireExactSubjectBinding": true'
        self.assertIn(needle, rendered)
        rendered = rendered.replace(
            needle,
            f'{needle}, "requireExactSubjectBinding": false',
            1,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate-policy-key.json"
            path.write_text(rendered, encoding="utf-8")
            with self.assertRaisesRegex(TSSEError, "duplicate JSON object key"):
                load_tsse_model(path)

    def test_bool_to_integer_change_is_a_state_boundary(self) -> None:
        model = valid_tsse_model()
        source_state = model["nodes"][0]["state"]  # type: ignore[index]
        target_state = copy.deepcopy(source_state)
        source_state["values"]["typedFlag"] = True  # type: ignore[index]
        target_state["values"]["typedFlag"] = 1  # type: ignore[index]
        model["nodes"][1]["state"] = target_state  # type: ignore[index]
        model["transitions"][0]["crossedBoundaries"] = [  # type: ignore[index]
            "time",
            "space",
            "environment",
        ]

        result = run_tsse_model(model)

        self.assertEqual(result["status"], "hold")
        self.assertIn("BOUNDARY_DECLARATION_MISMATCH", _violation_codes(result))
        self.assertIn("state", result["phaseTransitions"][0]["changedDimensions"])  # type: ignore[index]

    def test_model_hash_is_deterministic_and_content_addressed(self) -> None:
        model = valid_tsse_model()
        first = run_tsse_model(copy.deepcopy(model))["modelHash"]
        second = run_tsse_model(copy.deepcopy(model))["modelHash"]
        changed = copy.deepcopy(model)
        changed["scope"] = "A different bounded claim."
        third = run_tsse_model(changed)["modelHash"]

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", str(first)))


if __name__ == "__main__":
    unittest.main()
