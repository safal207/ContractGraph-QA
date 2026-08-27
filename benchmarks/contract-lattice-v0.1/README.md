# Contract Lattice Benchmark v0.1

This benchmark freezes the first executable six-coordinate contract model:

```text
State × Version × Value × Authority × Evidence × TimeWitness
```

## Canonical case

The benchmark uses:

```text
scenarios/contract-lattice-disputed-dead-end.json
```

The expected counterexample is:

```text
Created@0 → Funded@1 → Disputed@2
```

At `Disputed@2`:

- `lockedValue > 0`;
- the point is reachable;
- no path reaches a declared safe economic terminal.

Expected verdict:

```text
CGQ-LIVE-001 = FAIL
```

## Additional lattice laws

The same verifier also checks:

- `CGQ-LATTICE-VER-001` — every transition advances one causal version;
- `CGQ-LATTICE-BIND-001` — declared authority/evidence must already be bound at the source point;
- `CGQ-LATTICE-TIME-001` — time-sensitive transitions require explicit source-bound time witnesses.

## Run

```bash
cgqa contract-lattice-check \
  --model scenarios/contract-lattice-disputed-dead-end.json
```

The fixture is intentionally vulnerable, so the command returns a validation-failure exit code with machine-readable counterexample evidence.

## Claim boundary

This benchmark proves properties over the declared lattice only. Runtime trace completeness and raw EVM/provider normalization are independent provenance claims and are not promoted by this benchmark.
