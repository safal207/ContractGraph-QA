# Fault Coverage Matrix v0.1

`Fault Coverage Matrix` turns source-bound mutation generation and execution evidence into a per-fault-class view of the current verification suite.

```text
Solidity source
  -> Fault-Model Mutation Generator
  -> exact mutation plan SHA-256
  -> Foundry Mutation Acquisition
  -> CGQ-SPEC-001
  -> Fault Coverage Matrix
```

## Why this exists

A single mutation score hides important differences. A suite can be excellent at time-boundary checks while remaining blind to authorization or state-transition mutations. The matrix keeps those classes separate and preserves the underlying mutation identities.

## Per-class states

- `covered_over_reviewed_mutations`: every generated mutation in the class has conclusive `detected` evidence.
- `blind_spot`: at least one generated mutation in the class compiled/executed and survived the bound verification selector.
- `inconclusive`: the class is unsupported, unrepresented, unbound, or has execution evidence that cannot be classified as detected/survived.

A `killRate` is emitted only when every generated mutation in that class has a conclusive `detected` or `survived` outcome. `INCONCLUSIVE` rows deliberately show no percentage.

## Evidence binding

The matrix refuses to combine results unless:

1. the generation result contains a valid source-bound mutation plan;
2. the execution result declares the exact canonical SHA-256 of that same plan;
3. source SHA-256 values agree;
4. mutation ID sets agree exactly;
5. each execution fault class agrees with the generated mutation declaration.

This prevents mixing generation counts from one run with favorable execution evidence from another.

## One-command path

```bash
cgqa-fault-mutate \
  --config scenarios/escrow-auto-fault-generator.json \
  --project-root . \
  --output-dir fault-evidence \
  --execute
```

With `--execute`, the workflow now writes:

- `fault-generation-result.json`
- `generated-mutation-plan.json`
- `mutation-execution-result.json`
- `fault-coverage-matrix.json`
- `fault-coverage-matrix.md`
- detailed mutation evidence under `mutation-evidence/`

The standalone projection can also be rerun without Forge:

```bash
cgqa-fault-coverage \
  --generation fault-generation-result.json \
  --execution mutation-execution-result.json \
  --output fault-coverage-matrix.json \
  --markdown fault-coverage-matrix.md
```

## Claim boundary

Coverage is exact only over the reviewed/generated mutation challenge set. A green row does not prove that the fault class is exhaustively represented, and a green matrix does not certify that the contract is secure. A surviving mutant is a narrower, evidence-backed claim: the current bound property/test suite did not distinguish that generated faulty program from the baseline.
