# ContractGraph-QA Benchmarks

Repository-owned benchmark suites for reproducible verification research and product evidence.

## Suites

- [`state-transition-v0.1`](state-transition-v0.1/) — function-level PASS vs lifecycle-level FAIL cases: dead-end escrow states, replay, timeout recovery, and invalid transition composition.
- [`openescrow-partial-funding-v0.1`](openescrow-partial-funding-v0.1/) — source-pinned OpenEscrow multi-tenant partial-funding liveness case: one tenant funds, another stalls, and the funded tenant has no unilateral refund path.
- [`contract-lattice-v0.1`](contract-lattice-v0.1/) — six-coordinate contract model binding state, version, value, authority, evidence, and time witnesses.
- [`agent-payment-recovery-v0.1`](agent-payment-recovery-v0.1/) — agent payment recovery and evidence scenarios.
- [`crewai-tool-event-conformance-v0.1`](crewai-tool-event-conformance-v0.1/) — source-pinned CrewAI native tool-event witness projection benchmark.
- [`langgraph-checkpoint-state-conformance-v0.1`](langgraph-checkpoint-state-conformance-v0.1/) — source-pinned LangGraph hosted checkpoint/state benchmark.
- [`autogen-saved-state-conformance-v0.1`](autogen-saved-state-conformance-v0.1/) — source-pinned AutoGen save/load-state benchmark.
- [`ms-agent-framework-checkpoint-conformance-v0.1`](ms-agent-framework-checkpoint-conformance-v0.1/) — source-pinned Microsoft Agent Framework workflow-checkpoint benchmark.
- [`openai-agents-session-conformance-v0.1`](openai-agents-session-conformance-v0.1/) — source-pinned OpenAI Agents SDK SQLiteSession hosted benchmark with native mutation caveat.
- [`agent-runtime-conformance-matrix-v0.1`](agent-runtime-conformance-matrix-v0.1/) — machine-readable seven-axis comparison across the source-pinned runtime benchmarks.
- [`fcrp-v0.1`](fcrp-v0.1/), [`fcrp-v0.2`](fcrp-v0.2/), [`fcrp-v0.3`](fcrp-v0.3/) — FCRP benchmark generations.
- [`system-native`](system-native/) and [`system-e2e`](system-e2e/) — system-level benchmark fixtures.

## Runtime-conformance thesis

> Projection conformance is not the same claim as persistence, and persistence is not the same claim as append-only evidence.

The v0.1 runtime matrix therefore records semantic replay capabilities and storage/evidence guarantees on separate axes. Each row is pinned to an upstream repository commit and cross-checked against its benchmark `result.json`.

## State-transition thesis

> Unit tests verify operations. ContractGraph-QA verifies their composition.

The first state-transition suite is designed around a deliberately uncomfortable result:

> **17/17 tests passed. The funds can still be locked forever.**

That distinction is the benchmark target: locally correct functions do not imply a safe reachable lifecycle.

## Contract-lattice thesis

A lifecycle point is not only a named state. ContractGraph-QA v0.1 can bind the point to six explicit coordinates:

```text
State × Version × Value × Authority × Evidence × TimeWitness
```

This lets the same model reason about economic liveness, causal version continuity, authority/evidence provenance, and deterministic time-bound transitions without reading an ambient clock.
