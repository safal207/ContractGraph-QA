# Minimal Verified Repair Benchmark v0.1

This benchmark exercises `CGQ-CAUSAL-002` against the MilePact lifecycle counterfactual in:

`scenarios/milepact-minimal-repair-search.json`

The benchmark contains three atomic repair candidates and all seven non-empty combinations. Each combination carries an independent reviewed assessment snapshot and evidence hash.

Expected result:

```text
evaluated candidate sets: 7
verified candidate sets: 2
minimum repair count: 2
selected: cutoff-plus-resolve
```

The benchmark is intentionally designed so that neither target can be repaired by pretending single-patch effects compose automatically:

- cutoff alone repairs `CGQ-RACE-001` but leaves `CGQ-LIVE-001` failing;
- dispute resolution alone repairs `CGQ-LIVE-001` but leaves `CGQ-RACE-001` failing;
- UI-only change repairs neither on-chain invariant;
- cutoff + dispute resolution repairs both while preserving `CGQ-SAFE-001` and `CGQ-CONS-001`.

The result proves minimality only within the supplied reviewed candidate-set search space.
