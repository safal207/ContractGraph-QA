"""One-command RPC transaction capture to Hydrated Contract Lattice assessment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.evm_receipt_adapter import adapt_receipt, load_profile as load_receipt_profile
from contractgraph_qa.execution_trace import execution_trace_from_dict
from contractgraph_qa.hydrated_lattice import load_hydration_bindings, run_hydrated_lattice
from contractgraph_qa.hydrated_race_composition import compose_hydrated_with_protective_ordering
from contractgraph_qa.protective_ordering import load_protective_ordering_model
from contractgraph_qa.rpc_capture import capture_transaction, write_capture_result
from contractgraph_qa.solidity_lattice import check_target, load_profile as load_solidity_profile

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _rpc_url(cli_value: str | None) -> str:
    value = cli_value or os.environ.get("CGQA_RPC_URL")
    if value is None or not value.strip():
        raise ValueError("RPC URL is required via --rpc-url or CGQA_RPC_URL")
    return value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-rpc-hydrated",
        description=(
            "Capture one transaction from JSON-RPC, normalize its mapped logs into ExecutionTrace, "
            "compile Solidity to a static lattice, then run the Hydrated Contract Lattice assessment. "
            "An optional reviewed race model adds CGQ-RACE-001 as a required proof leg."
        ),
    )
    parser.add_argument("--tx-hash", required=True, help="32-byte transaction hash")
    parser.add_argument("--rpc-url", help="JSON-RPC endpoint; prefer CGQA_RPC_URL")
    parser.add_argument("--target", required=True, help="Foundry target <source.sol>:<Contract>")
    parser.add_argument("--profile", type=Path, required=True, help="Reviewed Solidity lattice profile")
    parser.add_argument("--receipt-profile", type=Path, required=True, help="Reviewed EVM receipt mapping profile")
    parser.add_argument("--bindings", type=Path, required=True, help="Hydration authority/time/evidence bindings")
    parser.add_argument("--race-model", type=Path, help="Optional reviewed CGQ-RACE-001 protective-ordering model")
    parser.add_argument("--root", type=Path, help="Optional Foundry project root")
    parser.add_argument("--capture-out", type=Path, help="Optional immutable RPC capture output path")
    args = parser.parse_args(argv)

    try:
        capture = capture_transaction(_rpc_url(args.rpc_url), args.tx_hash)
        if args.capture_out is not None:
            write_capture_result(args.capture_out.resolve(), capture)
        if capture["status"] != "pass":
            result = {
                "schemaVersion": "rpc-hydrated-assessment-v0.1",
                "status": "inconclusive",
                "rpcCapture": capture,
                "receiptAdapter": None,
                "hydratedAssessment": None,
                "claimBoundary": "No hydrated audit is produced until a mined receipt and matching block witness are captured.",
            }
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            return EXIT_VALIDATION

        capture_doc = capture["capture"]
        if not isinstance(capture_doc, dict):
            raise ValueError("RPC capture is missing capture document")
        receipt = capture_doc.get("receipt")
        if not isinstance(receipt, dict):
            raise ValueError("RPC capture is missing receipt")

        receipt_profile = load_receipt_profile(args.receipt_profile.resolve())
        captured_chain = capture_doc.get("chainId")
        if receipt_profile.get("chainId") != captured_chain:
            raise ValueError(
                f"receipt profile chainId {receipt_profile.get('chainId')} does not match captured chainId {captured_chain}"
            )
        adapter = adapt_receipt(receipt, receipt_profile)
        if adapter["status"] != "pass":
            result = {
                "schemaVersion": "rpc-hydrated-assessment-v0.1",
                "status": "inconclusive",
                "rpcCapture": capture,
                "receiptAdapter": adapter,
                "hydratedAssessment": None,
                "claimBoundary": "RPC evidence was captured, but no complete reviewed ExecutionTrace projection was produced.",
            }
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
            return EXIT_VALIDATION

        root = None if args.root is None else args.root.resolve()
        static_result = check_target(args.target, load_solidity_profile(args.profile.resolve()), root)
        hydrated = run_hydrated_lattice(
            static_result,
            execution_trace_from_dict(adapter["executionTrace"]),
            load_hydration_bindings(args.bindings.resolve()),
        )
        if args.race_model is not None:
            hydrated = compose_hydrated_with_protective_ordering(
                hydrated,
                load_protective_ordering_model(args.race_model.resolve()),
            )
        result = {
            "schemaVersion": "rpc-hydrated-assessment-v0.1",
            "status": hydrated["status"],
            "rpcCapture": capture,
            "receiptAdapter": adapter,
            "hydratedAssessment": hydrated,
            "claimBoundary": (
                "RPC capture proves only one provider observation. Receipt normalization is limited to reviewed mappings. "
                "Static, runtime, authority/time/evidence, race, canonical-chain and finality claims remain distinct."
            ),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-rpc-hydrated: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-rpc-hydrated: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-rpc-hydrated: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
