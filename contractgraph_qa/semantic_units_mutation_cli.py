"""CLI for compiler-AST-bound reviewed units/decimals mutation generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contractgraph_qa import legacy_cli
from contractgraph_qa.mutation_acquisition import mutation_plan_from_dict, run_mutation_acquisition
from contractgraph_qa.semantic_units_mutation import generate_semantic_units_mutation_plan, load_semantic_units_config

EXIT_OK = legacy_cli.EXIT_OK
EXIT_VALIDATION = legacy_cli.EXIT_VALIDATION
EXIT_INTERNAL = legacy_cli.EXIT_INTERNAL


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cgqa-semantic-units-mutate",
        description=(
            "Generate compiler-AST-bound decimal counterfactuals from reviewed unit bindings; optionally execute "
            "them through Foundry Mutation Acquisition and CGQ-SPEC-001."
        ),
    )
    parser.add_argument("--config", type=Path, required=True, help="Semantic Units Mutation v0.1 JSON")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Foundry project root")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory")
    parser.add_argument("--execute", action="store_true", help="Execute generated mutants with Foundry")
    args = parser.parse_args(argv)

    try:
        config = load_semantic_units_config(args.config.resolve())
        root = args.project_root.resolve()
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        generation = generate_semantic_units_mutation_plan(config, root)
        _write_json(output_dir / "semantic-units-generation-result.json", generation)
        plan = generation.get("mutationPlan")
        if isinstance(plan, dict):
            _write_json(output_dir / "generated-mutation-plan.json", plan)

        execution = None
        if args.execute:
            if not isinstance(plan, dict):
                raise ValueError("no executable semantic units mutation plan was generated")
            execution = run_mutation_acquisition(
                mutation_plan_from_dict(plan),
                root,
                output_dir=output_dir / "mutation-evidence",
            )
            _write_json(output_dir / "mutation-execution-result.json", execution)

        response = {"generation": generation, "execution": execution}
        print(json.dumps(response, indent=2, ensure_ascii=False, sort_keys=True))

        if generation["status"] != "pass":
            return EXIT_VALIDATION
        if execution is not None:
            spec = execution.get("specAssurance") if isinstance(execution, dict) else None
            if not isinstance(spec, dict) or spec.get("status") != "pass":
                return EXIT_VALIDATION
        return EXIT_OK
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"cgqa-semantic-units-mutate: {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    except KeyboardInterrupt:
        print("cgqa-semantic-units-mutate: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover
        print(f"cgqa-semantic-units-mutate: unexpected error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL


if __name__ == "__main__":
    raise SystemExit(main())
