# ASTRA Gonka Queue Benchmark v0.1

This benchmark asks one narrow question: when the target is already independently verified by the Gonka profile, can ASTRA reach the same target on the same bounded projection with lower discovery cost than deterministic BFS?

It does **not** claim that the pressure scores are Gonka facts, that ASTRA proves the findings, or that earlier discovery changes finding severity. The verified finding facts are source-bound to ContractGraph-QA PR #33; the TPS values are explicit reviewed benchmark assumptions used only to compare queue order.

## Source binding

Pinned Gonka revision: `f040d0a5b5ef207a0c431894c9f9e2608f9d3073`.

Source profile: `external-validation/gonka/graph.yaml` in PR #33.

Verified findings used as targets:

- `CGQA-GONKA-001`: detached/background execution lost request identity on the unmodified baseline; the same harness passed after explicit background identity propagation.
- `CGQA-GONKA-002`: after a client timeout, the request could continue and complete while the caller-known request ID did not resolve the completed accounting record.

## Result

| Benchmark | BFS expanded nodes | ASTRA expanded nodes | Nodes saved | Reduction | Same target | Same path |
|---|---:|---:|---:|---:|---|---|
| GONKA-001 | 9 | 7 | 2 | 22.2222% | yes | yes |
| GONKA-002 | 7 | 5 | 2 | 28.5714% | yes | yes |

In both projections, the number of examined transitions is unchanged. The current pressure queue therefore demonstrates **earlier target discovery**, not total graph-work reduction. This distinction is important: v0.1 reorders exploration but does not prune.

## Interpretation

The result supports only this statement:

> On these two source-bound derived projections, the reviewed ASTRA pressure ordering reaches the same already-verified Gonka target along the same transition path after expanding fewer nodes than deterministic BFS.

It does not yet support a general speedup claim. A stronger claim requires a larger benchmark set, pressure derivation independent of the known target, and held-out cases where TPS is assigned before the target location is revealed.

## Next validity gate

To reduce hindsight bias, the next benchmark should separate:

1. **training/review cases** where pressure weights may be informed by known findings;
2. **held-out cases** where weights are frozen before the target is revealed;
3. deterministic BFS as the authoritative complete baseline;
4. comparison by same-target discovery cost, false-focus rate, and total explored transitions.
