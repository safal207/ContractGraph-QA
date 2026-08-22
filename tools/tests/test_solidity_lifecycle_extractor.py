from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contractgraph_qa.cli import EXIT_VALIDATION, main as cli_main  # noqa: E402
from contractgraph_qa.solidity_lifecycle_extractor import (  # noqa: E402
    SolidityLifecycleProfile,
    check_lifecycle_from_ast,
    lifecycle_profile_from_dict,
    load_forge_ast,
    load_lifecycle_profile,
)


HAS_FORGE = shutil.which("forge") is not None


def _synthetic_ast(*, guarded: bool = True, member_selector: bool = False) -> dict[str, object]:
    state_expression: dict[str, object]
    if member_selector:
        state_expression = {
            "nodeType": "MemberAccess",
            "memberName": "state",
            "expression": {"nodeType": "Identifier", "name": "agreement"},
        }
    else:
        state_expression = {"nodeType": "Identifier", "name": "state"}

    guard = {
        "nodeType": "ExpressionStatement",
        "expression": {
            "nodeType": "FunctionCall",
            "expression": {"nodeType": "Identifier", "name": "require"},
            "arguments": [
                {
                    "nodeType": "BinaryOperation",
                    "operator": "==",
                    "leftExpression": state_expression,
                    "rightExpression": {
                        "nodeType": "MemberAccess",
                        "memberName": "Funded",
                        "expression": {"nodeType": "Identifier", "name": "State"},
                    },
                }
            ],
        },
    }
    assignment = {
        "nodeType": "ExpressionStatement",
        "expression": {
            "nodeType": "Assignment",
            "operator": "=",
            "leftHandSide": state_expression,
            "rightHandSide": {
                "nodeType": "MemberAccess",
                "memberName": "Disputed",
                "expression": {"nodeType": "Identifier", "name": "State"},
            },
        },
    }
    statements = [assignment]
    if guarded:
        statements.insert(0, guard)

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


def _profile(*, selector_kind: str = "identifier") -> SolidityLifecycleProfile:
    return SolidityLifecycleProfile(
        contract_name="Fixture",
        enum_name="State",
        state_selector="state",
        selector_kind=selector_kind,
        initial_state="Funded",
        value_holding_states=("Funded", "Disputed"),
        safe_terminal_states=("Released", "Refunded"),
        invariant_id="CGQ-LIVE-001",
    )


class SolidityLifecycleExtractorTest(unittest.TestCase):
    def test_incomplete_state_writer_is_inconclusive(self) -> None:
        result = check_lifecycle_from_ast(_synthetic_ast(guarded=False), _profile())
        self.assertEqual(result["status"], "inconclusive")
        extraction = result["extraction"]
        self.assertFalse(extraction["extractionComplete"])
        self.assertEqual(
            extraction["unresolvedStateWriters"][0]["reason"],
            "state_write_without_unambiguous_entry_state_guard",
        )

    def test_member_selector_supports_struct_style_state_access(self) -> None:
        result = check_lifecycle_from_ast(
            _synthetic_ast(member_selector=True),
            _profile(selector_kind="member"),
        )
        self.assertEqual(result["status"], "fail")
        transitions = result["extraction"]["transitionEvidence"]
        self.assertEqual(transitions[0]["sourceState"], "Funded")
        self.assertEqual(transitions[0]["targetState"], "Disputed")

    def test_profile_rejects_value_terminal_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot hold locked value"):
            lifecycle_profile_from_dict(
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
    def test_forge_ast_extraction_finds_disputed_dead_end(self) -> None:
        profile = load_lifecycle_profile(
            ROOT / "scenarios" / "disputed-dead-end-extractor-profile.json"
        )
        ast = load_forge_ast(
            "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
            ROOT,
        )
        result = check_lifecycle_from_ast(ast, profile)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["extraction"]["extractionComplete"])
        transition_ids = {
            item["transitionId"] for item in result["extraction"]["transitionEvidence"]
        }
        self.assertIn("raiseDispute:Funded->Disputed", transition_ids)
        self.assertTrue(
            any(item["state"] == "Disputed" for item in result["verification"]["violations"])
        )

    @unittest.skipUnless(HAS_FORGE, "forge is required for compiler-AST integration")
    def test_forge_ast_extraction_allows_safe_escrow(self) -> None:
        profile = SolidityLifecycleProfile(
            contract_name="Escrow",
            enum_name="State",
            state_selector="state",
            selector_kind="identifier",
            initial_state="Created",
            value_holding_states=("Funded",),
            safe_terminal_states=("Released", "Refunded"),
            invariant_id="CGQ-LIVE-001",
        )
        ast = load_forge_ast("src/examples/Escrow.sol:Escrow", ROOT)
        result = check_lifecycle_from_ast(ast, profile)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["extraction"]["extractionComplete"])
        self.assertEqual(result["verification"]["violations"], [])

    @unittest.skipUnless(HAS_FORGE, "forge is required for compiler-AST integration")
    def test_cli_target_mode_returns_failure_evidence(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "solidity-lifecycle-check",
                    "--target",
                    "src/examples/DisputedDeadEndEscrow.sol:DisputedDeadEndEscrow",
                    "--profile",
                    str(ROOT / "scenarios" / "disputed-dead-end-extractor-profile.json"),
                    "--root",
                    str(ROOT),
                ]
            )
        self.assertEqual(exit_code, EXIT_VALIDATION)
        document = json.loads(stdout.getvalue())
        self.assertEqual(document["status"], "fail")
        self.assertEqual(document["verification"]["invariantId"], "CGQ-LIVE-001")


if __name__ == "__main__":
    unittest.main()
