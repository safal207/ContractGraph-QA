# Solidity Mutation Acquisition v0.1

`cgqa-mutation-run` turns a reviewed mutation plan into source-bound Solidity mutants, executes narrow Foundry test selectors in isolated project copies, and feeds the outcomes into `CGQ-SPEC-001`.

The goal is not to maximize a mutation score. The goal is to produce reproducible evidence that a reviewed specification is sensitive to concrete fault classes without inflating the score with invalid mutants.

## Flow

```text
REVIEWED SOURCE SHA-256
        ↓
EXACT REVIEWED TEXT MUTATIONS
        ↓
ISOLATED PROJECT COPY PER MUTANT
        ↓
forge build
        ↓
compilable?
  no → INCONCLUSIVE
  yes
        ↓
exact forge test selector
        ↓
0  → SURVIVED
1  → DETECTED
other / timeout / selector absent → INCONCLUSIVE
        ↓
CGQ-SPEC-001
```

A compile failure is never counted as a detected mutation. This prevents syntactically invalid or otherwise unbuildable mutants from artificially improving mutation sensitivity.

## Repository fixture

```bash
cgqa-mutation-run \
  --plan scenarios/escrow-foundry-mutation-plan.json \
  --project-root . \
  --output-dir mutation-evidence
```

The repository-owned plan targets `src/examples/Escrow.sol` and declares two reviewed fault classes:

- `authorization-inversion`
- `deadline-guard-removal`

Each mutation has its own exact Foundry selector. The adapter first confirms that every selected baseline test passes, then compiles and tests each mutant in a temporary project copy.

## Evidence binding

The plan binds the exact original source bytes with `sourceSha256`. Each generated mutation records:

- original source SHA-256;
- mutant source SHA-256;
- exact byte and line/column span;
- unified-diff SHA-256;
- `forge build` command/result hashes;
- selected `forge test` command/result hashes;
- execution classification;
- evidence SHA-256 consumed by `CGQ-SPEC-001`.

The output directory contains materialized mutants plus:

```text
mutation-result.json
spec-assurance-model.json
spec-assurance-result.json
mutants/<mutation-id>/...
```

## Claim boundary

v0.1 intentionally does not claim that mutation operators are exhaustive or that a passing specification covers all possible bugs. Mutations are reviewed exact text replacements. The adapter also does not infer property activation from a passing test; activation remains explicit reviewed evidence.

`CGQ-SPEC-001 PASS` therefore means only that the property was active according to its reviewed activation witness and detected every supplied compilable mutation in every represented required fault class.

## Why exact replacements first

AST mutation and external mutation engines can be added later, but exact reviewed replacements give v0.1 a deterministic acquisition boundary:

```text
source SHA + exact unique match + replacement → exact mutant SHA
```

This makes it possible to add future Gambit, Medusa, Echidna, Halmos, or Kontrol acquisition adapters without changing the downstream `CGQ-SPEC-001` semantics.
