# ContractGraph-QA v1.0 product runtime

ContractGraph-QA v1.0 is a command-line QA evidence pipeline for explicitly authorized smart-contract testing.

It combines the existing causal-temporal engine with an operator-facing runtime that turns a reviewed model and a Foundry capture into reproducible client evidence.

## Product promise

Given:

1. an explicitly authorized test scope;
2. a reviewed adapter manifest;
3. a deterministic Foundry adapter/capture test;
4. explicit invariants;

ContractGraph-QA can produce a reproducible evidence chain:

```text
scope + manifest
      ↓
Foundry search
      ↓
minimal violating path
      ↓
deterministic replay
      ↓
explorer-result JSON
      ↓
manifest/result provenance validation
      ↓
finding JSON
      ↓
client Markdown report
      ↓
deterministic evidence ZIP
      ↓
independent bundle verification
```

The product does not claim that bounded search proves a contract secure. Results are limited to the modeled actors, actions, parameter corpus, time assumptions, search depth, state hash, adapter mapping, snapshot, and invariants.

## Runtime components

### Solidity engine

The Foundry harnesses provide:

- causal transition evidence;
- bounded breadth-first path exploration;
- parameter/time corpora;
- state hashing and equivalent-state pruning;
- fixed-block fork context with explicit authorization gates;
- contract-specific adapter boundary;
- direct explorer-result capture.

### Reviewed manifest

The adapter manifest is the human-reviewable engagement contract for:

- adapter and scope IDs;
- target and authorization reference;
- search depth;
- state fields;
- allowed actions and actors;
- invariants and client-facing finding metadata.

### Product CLI

`cgqa` supplies the operator workflow:

- `doctor` — dependency check;
- `validate` — manifest/result validation;
- `fingerprint` — canonical manifest SHA-256;
- `run` — capture → export → report → bundle;
- `verify-bundle` — independent integrity + semantic-chain verification.

## Deterministic evidence bundle

A v1 bundle contains exactly:

```text
manifest.json
result.json
finding.json
report.md
bundle.json
```

`bundle.json` records the tool version, finding ID, canonical manifest SHA-256, and exact SHA-256/byte count for every evidence artifact.

The ZIP writer fixes file order, metadata timestamps, permissions, and names so identical inputs produce identical bundle bytes.

`cgqa verify-bundle` checks both integrity and meaning:

1. exact entry set and order;
2. per-entry size limits;
3. byte counts and SHA-256 values;
4. manifest and result validation;
5. manifest/result provenance binding;
6. deterministic re-export of `finding.json`;
7. deterministic re-render of `report.md`.

## Product safety boundaries

ContractGraph-QA is for:

- contracts you own;
- repository-local fixtures;
- client contracts with explicit authorization;
- public bug-bounty assets strictly within published scope and rules.

A public address, ABI, source repository, manifest file, or RPC endpoint is not authorization by itself.

The CLI does not execute arbitrary shell strings. Foundry is invoked as an argument array, and capture profile/test identifiers are restricted to safe identifier characters.

Real fork execution continues to require the v0.6/v0.7 authorization and adapter gates.

## v1.0 Definition of Done

v1.0 is considered product-ready when all of the following are green on the exact release head:

- default Foundry build/tests;
- Slither advisory scan;
- reporting unit/golden tests;
- direct Foundry capture regression;
- installable `contractgraph-qa` package;
- `cgqa doctor --require-forge`;
- full `cgqa run --config cgqa.example.toml --clean`;
- generated finding/report equal checked-in goldens;
- `cgqa verify-bundle` succeeds;
- wheel build/install smoke;
- no unresolved blocking review thread.

## Not in v1.0

The following are deliberate follow-up areas rather than hidden claims:

- automatic Solidity adapter generation from arbitrary ABIs;
- automatic invariant synthesis;
- unbounded/exhaustive protocol verification;
- permissionless production-target testing;
- automated exploit execution or fund movement;
- a hosted multi-tenant service/UI.
