# ContractGraph-QA v1.0 product runtime

ContractGraph-QA v1.0 is a command-line QA evidence pipeline for explicitly authorized smart-contract testing.

It combines the existing causal-temporal engine with an operator-facing runtime that turns a reviewed model and a Foundry capture into reproducible client evidence.

## Product promise

Given:

1. an explicitly authorized test scope;
2. a reviewed adapter manifest;
3. a deterministic Foundry adapter/capture test;
4. explicit invariants;
5. optionally, a reviewed adversarial reachability model;

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
[optional] assumption/capability reachability
      ↓
finding JSON
      ↓
client Markdown report
      ↓
deterministic evidence ZIP
      ↓
independent bundle verification
```

The product does not claim that bounded search proves a contract secure. Results are limited to the modeled actors, actions, parameter corpus, time assumptions, search depth, state hash, adapter mapping, snapshot, invariants, declared reachability assumptions, and capability graph.

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

### Optional reachability model

A product config can add:

```toml
reachabilityModel = "scenarios/adversarial-wallet-replay.json"
```

The model declares assumptions, capabilities, guarded capability transitions, initial capabilities, target capabilities, violated assumptions, and a search bound. It is strict, deterministic, stdlib-only, and separately fingerprinted by canonical SHA-256.

### Product CLI

`cgqa` supplies the operator workflow:

- `doctor` — dependency check;
- `validate` — manifest/result validation;
- `fingerprint` — canonical manifest SHA-256;
- `reachability` — bounded assumption/capability reachability;
- `run` — capture → optional reachability → export → report → bundle;
- `verify-bundle` — independent integrity + semantic-chain verification.

## Deterministic evidence bundles

### Bundle v1

Configs without a reachability model keep the existing bundle shape:

```text
manifest.json
result.json
finding.json
report.md
bundle.json
```

### Bundle v2

Configs with `reachabilityModel` produce:

```text
manifest.json
result.json
reachability-model.json
reachability.json
finding.json
report.md
bundle.json
```

`reachability-model.json` is the canonicalized model. `reachability.json` is the deterministic bounded result. `finding.json` binds that result under `evidence.reachability`, including the model SHA-256 and artifact references.

`bundle.json` records the tool version, finding ID, canonical manifest SHA-256, exact SHA-256/byte count for every evidence artifact, and for v2 the reachability model SHA-256.

The ZIP writer fixes file order, metadata timestamps, permissions, and names so identical semantic inputs produce identical bundle bytes.

`cgqa verify-bundle` checks integrity and meaning. For v1 it checks:

1. exact entry set and order;
2. per-entry size limits;
3. byte counts and SHA-256 values;
4. manifest and result validation;
5. manifest/result provenance binding;
6. deterministic re-export of `finding.json`;
7. deterministic re-render of `report.md`.

For v2 it additionally:

8. validates and canonicalizes the bundled reachability model;
9. recomputes the reachability model SHA-256;
10. re-runs bounded reachability from the bundled model;
11. requires `reachability.json` to equal that recomputed result;
12. requires `finding.json` to carry exactly the recomputed reachability evidence.

This preserves backward compatibility for existing evidence while making the new capability path independently recomputable.

## Product safety boundaries

ContractGraph-QA is for:

- contracts you own;
- repository-local fixtures;
- client contracts with explicit authorization;
- public bug-bounty assets strictly within published scope and rules.

A public address, ABI, source repository, manifest file, reachability model, or RPC endpoint is not authorization by itself.

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
