# Hydrated race composition v0.1

`CGQ-RACE-001` can now participate in the full hydrated audit without changing the existing Hydrated Contract Lattice v0.1 API.

## Why this is separate

Successor consistency asks whether more than one child commit was actually accepted from the same parent state/version.

Protective ordering asks a different business-semantic question: if two actions are both valid from one parent, can transaction ordering alone destroy a declared protective right even though EVM serialization permits only one action to commit?

## CLI

All hydrated entrypoints accept an optional reviewed race model:

```bash
cgqa-hydrated \
  --target src/MyEscrow.sol:MyEscrow \
  --profile lifecycle-profile.json \
  --trace execution-trace.json \
  --bindings hydration-bindings.json \
  --race-model protective-ordering.json \
  --root .
```

The same `--race-model` option is supported by `cgqa-evm-hydrated` and `cgqa-rpc-hydrated`.

## Verdict composition

When no race model is supplied, existing hydrated v0.1 verdict semantics are unchanged.

When a race model is supplied:

- hydrated FAIL or race FAIL => overall FAIL;
- hydrated PASS and race PASS => overall PASS;
- otherwise => INCONCLUSIVE.

A supplied race model therefore becomes a required proof leg for full PASS.

## Provenance

The result adds:

- `protectiveOrderingVerification`;
- `evidenceFingerprint.raceModelSha256`;
- a recomputed `assessmentSha256` binding the race model into the assessment.

## Claim boundary

The race verifier is exact only over the reviewed two-order counterfactual. The following remain separate evidence/specification claims:

- both actions are actually jointly enabled in the target contract/state;
- the modeled transaction outcomes match executable contract behavior;
- preserving the protective right across ordering is an intended business guarantee.

This prevents an LLM-generated race hypothesis from becoming a product verdict until the reviewed counterfactual is explicitly supplied.
