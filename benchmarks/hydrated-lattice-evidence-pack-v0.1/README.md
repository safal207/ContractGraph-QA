# Hydrated Lattice Evidence Pack Benchmark v0.1

This benchmark freezes the portable evidence boundary immediately above Hydrated Contract Lattice v0.1.

## Proof object

```text
static result
+ ExecutionTrace
+ hydration bindings
+ recomputed hydrated assessment
+ client summary
+ manifest hashes
= deterministic ZIP
```

## Required regressions

The executable test suite proves:

- two builds from equivalent inputs are byte-identical;
- canonical local replay verifies a valid pack;
- an independently supplied complete-pack SHA-256 binds the exact ZIP bytes;
- a wrong external digest fails for the `external pack digest mismatch` reason;
- rehashing a type-altered assessment (`true` → `1`) does not bypass semantic replay;
- rehashing a modified execution trace does not make the old assessment valid;
- boolean authority-boundary type drift (`false` → `0`) is rejected;
- non-canonical ZIP metadata is rejected.

## Interpretation

A successful verification means the embedded normalized inputs reproduce the exact embedded assessment and summary under the current deterministic verifier. With an independently obtained pack SHA-256, the verifier additionally proves that the checked ZIP is the externally referenced byte sequence.

It does not prove that upstream runtime capture was complete, that external authority/time sources were truthful, or that the artifact authorizes any production action.
