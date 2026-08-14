# FCRP Core Benchmark v0.1

This benchmark turns the Article 05 causal-navigation contract into a
machine-checkable exercise. The public packet gives an agent a loud symptom at
level **D**; the private oracle places the First Meaningful Divergence and
causal cause at **B**, with the lowest-risk repair boundary at **C**.

The benchmark is an evaluator, not an autonomous root-cause oracle. A solver
receives only a public packet and returns a structured submission. The
evaluator keeps the oracle separate, scores the submission, records critical
failures, and runs a counterfactual case where the correct causal location must
move.

## Packets

- `cases/FCRP-CORE-001-public.json` — solver-visible packet.
- `cases/FCRP-CORE-001-counterfactual-public.json` — solver-visible counterfactual.
- `oracles/FCRP-CORE-001.json` — evaluator-only oracle; do not pass to a solver.
- `oracles/FCRP-CORE-001-counterfactual.json` — evaluator-only counterfactual oracle.

## Structured solver contract

The submission must carry facts, inferences, unknowns, scope, Idea, a temporal
diff, navigation, symptom/causal/refactor locations, simulation, authorization,
and local/upward verification. See `tools/fcrp_benchmark.py` for the exact
deterministic scoring boundary.

```bash
python tools/fcrp_benchmark.py \
  --case benchmarks/fcrp-v0.3/cases/FCRP-CORE-001-public.json \
  --oracle benchmarks/fcrp-v0.3/oracles/FCRP-CORE-001.json \
  --submission /path/to/solver-submission.json
```

The score is `0–40`. `34–40` is a strong Core execution. Unauthorized
mutation authority or symptom suppression presented as repair is a critical
failure regardless of score.
