"""One-command Solidity + raw EVM receipt hydrated assessment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.evm_receipt_adapter import adapt_receipt_files
from contractgraph_qa.execution_trace import execution_trace_from_dict
from contractgraph_qa.hydrated_lattice import load_hydration_bindings, run_hydrated_lattice
from contractgraph_qa.hydrated_race_composition import compose_hydrated_with_protective_ordering
from contractgraph_qa.protective_ordering import load_protective_ordering_model
from contractgraph_qa.solidity_lattice import check_target, load_profile

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-evm-hydrated",
        description=(
            "Compile Solidity to a static lattice, normalize one raw JSON-RPC receipt "
            "through a reviewed event mapping, then run hydrated lifecycle/replay/"
            "successor/static-runtime verification. An optional reviewed race model adds "
            "CGQ-RACE-001 as a required proof leg."
        ),
    )
    parser.add_argument("--target", required=True, help="Foundry target <source.sol>:<Contract>")
    parser.add_argument("--profile", type=Path, required=True, help="Reviewed Solidity lattice profile")
    parser.add_argument("--receipt", type=Path, required=True, help="Raw JSON-RPC transaction receipt")
    parser.add_argument("--receipt-profile", type=Path, required=True, help="Reviewed EVM receipt mapping profile")
    parser.add_argument("--bindings", type=Path, required=True, help="Hydration authority/time/evidence bindings")
    parser.add_argument("--race-model", type=Path, help="Optional reviewed CGQ-RACE-001 protective-ordering model")
    parser.add_argument("--root", type=Path, help="Optional Foundry project root")
    args = parser.parse_args(argv)

    try:
        root = None if args.root is None else args.root.resolve()
        static_result = check_target(args.target, load_profile(args.profile.resolve()), root)
        adapter_result = adapt_receipt_files(args.receipt.resolve(), args.receipt_profile.resolve())
        trace = execution_trace_from_dict(adapter_result["executionTrace"])
        hydrated = run_hydrated_lattice(
            static_result,
            trace,
            load_hydration_bindings(args.bindings.resolve()),
        )
        if args.race_model is not None:
            hydrated = compose_hydrated_with_protective_ordering(
                hydrated,
                load_protective_ordering_model(args.race_model.resolve()),
            )
        result = {
            "schemaVersion": "evm-hydrated-assessment-v0.1",
            "status": hydrated["status"],
            "receiptAdapter": adapter_result,
            "hydratedAssessment": hydrated,
            "claimBoundary": (
                "The receipt adapter proves deterministic normalization only for explicitly mapped logs. "
                "The hydrated assessment preserves separate static, runtime, binding, race and provenance claims."
            ),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if result["status"] == "pass" else EXIT_VALIDATION
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-evm-hydrated: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-evm-hydrated: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive product boundary
        print(f"cgqa-evm-hydrated: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
