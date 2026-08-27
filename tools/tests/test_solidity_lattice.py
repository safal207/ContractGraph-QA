from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.solidity_lattice import (  # noqa: E402
    SolidityLatticeProfile,
    check_ast,
    check_target,
    profile_from_dict,
)

HAS_FORGE = shutil.which("forge") is not None
PROFILE = ROOT / "scenarios" / "solidity-lattice-disputed-dead-end-profile.json"


def _state_expr() -> dict[str, object]:
    return {"nodeType": "Identifier", "name": "state"}


def _state_member(name: str) -> dict[str, object]:
    return {
        "nodeType": "MemberAccess",
        "memberName": name,
        "expression": {"nodeType": "Identifier", "name": "State"},
    }


def _assignment(target: str) -> dict[str, object]:
    return {
        "nodeType": "ExpressionStatement",
        "expression": {
            "nodeType": "Assignment",
            "operator": "=",
            "leftHandSide": _state_expr(),
            "rightHandSide": _state_member(target),
        },
    }


def _if_revert_guard(source: str, *, builtin: bool) -> dict[str, object]:
    if builtin:
        true_body: dict[str, object] = {
            "nodeType": "ExpressionStatement",
            "expression": {
                "nodeType": "FunctionCall",
                "expression": {"nodeType": "Identifier", "name": "revert"},
                "arguments": [{"nodeType": "Literal", "value": "invalid state"}],
            },
        }
    else:
        true_body = {"nodeType": "RevertStatement"}
    return {
        "nodeType": "IfStatement",
        "condition": {
            "nodeType": "BinaryOperation",
            "operator": "!=",
            "leftExpression": _state_expr(),
            "rightExpression": _state_member(source),
        },
        "trueBody": true_body,
        "falseBody": None,
    }


def _synthetic_ast(*, builtin_revert: bool = True, guarded: bool = True) -> dict[str, object]:
    statements = [_assignment("Disputed")]
    if guarded:
        statements.insert(0, _if_revert_guard("Funded", builtin=builtin_revert))
    return {
        "nodeType": "SourceUnit",
        "nodes": [
            {
                "nodeType": "ContractDefinition",
                "name": "Fixture",
                "nodes": [
                    {
                        "nodeType": "EnumDefinition",
                        "name": "State",
                        "members": [
                            {"nodeType": "EnumValue", "name": "Created"},
                            {"nodeType": "EnumValue", "name": "Funded"},
                            {"nodeType": "EnumValue", "name": "Released"},
                            {"nodeType": "EnumValue", "name": "Refunded"},
                            {"nodeType": "EnumValue", "name": "Disputed"},
                        ],
                    },
                    {
                        "nodeType": "FunctionDefinition",
                        "id": 42,
                        "kind": "function",
                        "name": "raiseDispute",
                        "body": {"nodeType": "Block", "statements": statements},
                    },
                ],
            }
        ],
    }


def _profile() -> SolidityLatticeProfile:
    return SolidityLatticeProfile(
        contract_name="Fixture",
        enum_name="State",
        state_selector="state",
        selector_kind="identifier",
        initial_state="Funded",
        value_holding_states=("Funded", "Disputed"),
        safe_terminal_states=("Released", "Refunded"),
        invariant_id="CGQ-LIVE-001",
    )


class SolidityLatticeTest(unittest.TestCase):
    def test_builtin_revert_string_is_a_supported_state_guard(self) -> None:
        result = check_ast(_synthetic_ast(builtin_revert=True), _profile())
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["extraction"]["extractionComplete"])
        transitions = result["extraction"]["transitionEvidence"]
        self.assertEqual(transitions[0]["sourceState"], "Funded")
        self.assertEqual(transitions[0]["targetState"], "Disputed")

    def test_custom_error_revert_statement_is_supported(self) -> None:
        result = check_ast(_synthetic_ast(builtin_revert=False), _profile())
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["extraction"]["extractionComplete"])

    def test_unguarded_state_writer_is_inconclusive(self) -> None:
        result = check_ast(_synthetic_ast(guarded=False), _profile())
        self.assertEqual(result["status"], "inconclusive")
        unresolved = result["extraction"]["unresolvedStateWriters"]
        self.assertEqual(unresolved[0]["function"], "raiseDispute")

    def test_lattice_template_keeps_static_claim_boundary(self) -> None:
        result = check_ast(_synthetic_ast(), _profile())
        template = result["latticeTemplate"]
        self.assertEqual(template["schemaVersion"], "contract-lattice-template-v0.1")
        self.assertEqual(
            template["dimensions"],
            ["state", "relativeVersion", "valuePresence", "authority", "evidence", "timeWitness"],
        )
        self.assertTrue(all(edge["versionDelta"] == 1 for edge in template["transitionTemplates"]))
        disputed = next(point for point in template["points"] if point["state"] == "Disputed")
        self.assertTrue(disputed["valuePresence"])
        self.assertEqual(disputed["authority"], "not_inferred_from_static_ast")

    def test_profile_rejects_value_terminal_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot hold locked value"):
            profile_from_dict(
                {
                    "contractName": "Fixture",
                    "enumName": "State",
                    "stateSelector": "state",
                    "selectorKind": "identifier",
                    "initialState": "Funded",
                    "valueHoldingStates": ["Funded", "Refunded"],
                    "safeTerminalStates": ["Refunded"],
                    "invariantId": "CGQ-LIVE-001",
                }
            )

    @unittest.skipUnless(HAS_FORGE, "forge is required for compiler-AST integration")
    def test_real_foundry_finds_disputed_dead_end(self) -> None:
        profile = profile_from_dict(json.loads(PROFILE.read_text(encoding="utf-8")))
        result = check_target(
            "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
            profile,
            ROOT,
        )
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["extraction"]["extractionComplete"])
        violations = result["lifecycleVerification"]["violations"]
        self.assertTrue(any(item["state"] == "Disputed" for item in violations))
        transition_ids = {
            item["transitionId"] for item in result["extraction"]["transitionEvidence"]
        }
        self.assertIn("raiseDispute:Funded->Disputed", transition_ids)

    @unittest.skipUnless(HAS_FORGE, "forge is required for compiler-AST integration")
    def test_real_foundry_safe_escrow_passes(self) -> None:
        profile = SolidityLatticeProfile(
            contract_name="Escrow",
            enum_name="State",
            state_selector="state",
            selector_kind="identifier",
            initial_state="Created",
            value_holding_states=("Funded",),
            safe_terminal_states=("Released", "Refunded"),
            invariant_id="CGQ-LIVE-001",
        )
        result = check_target("src/examples/Escrow.sol:Escrow", profile, ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["extraction"]["extractionComplete"])
        self.assertEqual(result["lifecycleVerification"]["violations"], [])


if __name__ == "__main__":
    unittest.main()
