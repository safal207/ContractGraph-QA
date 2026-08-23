"""CLI for deterministic fault-model mutation generation and optional execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.fault_coverage import build_fault_coverage_matrix, render_fault_coverage_markdown
from contractgraph_qa.fault_mutation_generator import generate_fault_mutation_plan, load_generator_config
from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict, run_mutation_acquisition

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-fault-mutate",
        description=(
            "Generate deterministic source-bound Solidity mutations for supported fault classes; "
            "optionally execute them through Foundry Mutation Acquisition, CGQ-SPEC-001, and a fault coverage matrix."
        ),
    )
    parser.add_argument("--config", type=Path, required=True, help="Fault mutation generator v0.1 JSON")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Foundry project root")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    parser.add_argument("--execute", action="store_true", help="Run generated mutations with Foundry and emit coverage matrix")
    args = parser.parse_args(argv)

    try:
        config = load_generator_config(args.config.resolve())
        result = generate_fault_mutation_plan(config, args.project_root.resolve())
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(output_dir / "fault-generation-result.json", result)

        plan = result.get("mutationPlan")
        if isinstance(plan, dict):
            _write_json(output_dir / "generated-mutation-plan.json", plan)

        execution = None
        coverage = None
        if args.execute:
            if not isinstance(plan, dict):
                raise ValueError("no executable mutation plan was generated")
            execution = run_mutation_acquisition(
                mutation_plan_from_dict(plan),
                args.project_root.resolve(),
                output_dir=output_dir / "mutation-evidence",
            )
            _write_json(output_dir / "mutation-execution-result.json", execution)
            coverage = build_fault_coverage_matrix(result, execution)
            _write_json(output_dir / "fault-coverage-matrix.json", coverage)
            (output_dir / "fault-coverage-matrix.md").write_text(
                render_fault_coverage_markdown(coverage), encoding="utf-8"
            )

        response: dict[str, object] = {
            "generation": result,
            "execution": execution,
            "coverage": coverage,
        }
        print(json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True))

        if result["status"] != "pass":
            return EXIT_VALIDATION
        if execution is not None:
            spec = execution.get("specAssurance") if isinstance(execution, dict) else None
            if not isinstance(spec, dict) or spec.get("status") != "pass":
                return EXIT_VALIDATION
            if not isinstance(coverage, dict) or coverage.get("status") != "pass":
                return EXIT_VALIDATION
        return EXIT_OK
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-fault-mutate: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-fault-mutate: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"cgqa-fault-mutate: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
