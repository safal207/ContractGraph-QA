# ContractGraph-QA Benchmarks

Repository-owned benchmark suites for reproducible verification research and product evidence.

## Suites

- [`state-transition-v0.1`](state-transition-v0.1/) — function-level PASS vs lifecycle-level FAIL cases: dead-end escrow states, replay, timeout recovery, and invalid transition composition.
- [`agent-payment-recovery-v0.1`](agent-payment-recovery-v0.1/) — agent payment recovery and evidence scenarios.
- [`fcrp-v0.1`](fcrp-v0.1/), [`fcrp-v0.2`](fcrp-v0.2/), [`fcrp-v0.3`](fcrp-v0.3/) — FCRP benchmark generations.
- [`system-native`](system-native/) and [`system-e2e`](system-e2e/) — system-level benchmark fixtures.

## State-transition thesis

> Unit tests verify operations. ContractGraph-QA verifies their composition.

The first state-transition suite is designed around a deliberately uncomfortable result:

> **17/17 tests passed. The funds can still be locked forever.**

That distinction is the benchmark target: locally correct functions do not imply a safe reachable lifecycle.
