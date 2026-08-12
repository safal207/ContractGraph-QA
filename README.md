# ContractGraph-QA

**Causal-temporal smart-contract QA with reproducible evidence.**

ContractGraph-QA treats a smart contract as a reachable state space rather than a collection of isolated functions.

The core question is:

> Can an allowed sequence of actors, transactions, parameter values, and time changes drive the contract into a state that violates an explicit business or security invariant?

## Try the product first

The fastest proof path needs only Python 3.11+ and the installed wheel:

```bash
python -m pip install contractgraph-qa
cgqa demo --output-dir cgqa-demo
cgqa verify-bundle cgqa-demo/CGQA-005.evidence.zip
```

`cgqa demo` uses only repository-owned packaged evidence. It makes no external RPC call and is **not** presented as a third-party audit.

It produces:

```text
cgqa-demo/
  inputs/manifest.json
  inputs/result.json
  CGQA-005.finding.json
  CGQA-005.md
  CGQA-005.evidence.zip
```

See [`docs/DISTRIBUTION.md`](docs/DISTRIBUTION.md).

## Product runtime

The full engine is exposed through the installable `cgqa` CLI and turns a reviewed adapter model plus deterministic Foundry search into a client-verifiable evidence bundle.

```text
AUTHORIZED SCOPE
      ↓
REVIEWED ADAPTER MANIFEST
      ↓
FOUNDRY SEARCH
      ↓
MULTI-INVARIANT OUTCOMES
      ↓
MINIMAL VIOLATING PATHS
      ↓
DETERMINISTIC REPLAY
      ↓
OBSERVED PRE/POST STATE
      ↓
PROVENANCE VALIDATION
      ↓
CLIENT FINDINGS / ENGAGEMENT REPORT
      ↓
DETERMINISTIC EVIDENCE ZIP
      ↓
INDEPENDENT VERIFICATION
```

For engine execution, install Foundry and run:

```bash
cgqa doctor --require-forge
cgqa init-engagement acme-escrow
# Replace every generated TODO only after explicit scope/authorization review.
cgqa engagement-run --config engagements/acme-escrow/cgqa.toml
cgqa verify-engagement-bundle engagements/acme-escrow/evidence/engagement.evidence.zip
```

The generated scaffold deliberately starts fail-closed and is not execution-ready until the operator replaces the authorization, target, state-hash, action, invariant, and capture-adapter TODOs.

See [`docs/PRODUCT.md`](docs/PRODUCT.md), [`docs/CLI.md`](docs/CLI.md), and [`docs/ENGAGEMENT.md`](docs/ENGAGEMENT.md).

## Adversarial capability reachability

The experimental reachability layer models a second question:

> Can a broken assumption make a previously forbidden capability reachable, cross a control boundary, and produce a bounded, reproducible impact path?

Repository-owned models can be executed without network access or Forge:

```bash
cgqa reachability --model scenarios/adversarial-wallet-replay.json
```

The current model is:

```text
ASSUMPTION
    ↓ violation
CAPABILITY
    ↓ transition
CONTROL BOUNDARY / INVARIANT
    ↓
FORBIDDEN CAPABILITY
    ↓
IMPACT
```

The command emits deterministic JSON containing a canonical model SHA-256, the declared violated assumptions, and the shortest reachable impact path within the configured bound. `not_found_within_bound` is bounded evidence only, not a safety certification.

The same model can now be bound into the single-finding product pipeline by adding:

```toml
reachabilityModel = "scenarios/adversarial-wallet-replay.json"
```

`cgqa run` then emits a backward-compatible **bundle v2** containing canonical `reachability-model.json` and recomputable `reachability.json`, and binds the result into `finding.json -> evidence.reachability`. `cgqa verify-bundle` independently re-runs the bundled model and rejects any mismatch in the model hash, impact path, finding evidence, or artifact bytes. Configs without `reachabilityModel` continue to produce the existing bundle v1.

See [`docs/ADVERSARIAL_REACHABILITY.md`](docs/ADVERSARIAL_REACHABILITY.md).

## Mental model

```text
CAUSE
  ↓
ACTOR
  ↓
ACTION / TRANSACTION
  ↓
PARAMETER / TIME INPUT
  ↓
PRE-STATE
  ↓
STATE TRANSITION
  ↓
POST-STATE
  ↓
STATE HASH
  ↓
EFFECT
  ↓
FUTURE REACHABLE STATES
```

A finding should remain traceable as:

```text
Finding → Cause → Path → Evidence → Replay → Fix → Retest
```

## What the engine supports

### Functional and security-invariant QA

- positive and negative contract flows;
- role/access-control paths;
- state transitions and terminal states;
- custom errors/reverts and events;
- asset/accounting invariants;
- temporal/deadline conditions;
- multiple invariants in one bounded exploration session.

### Explicit outcome semantics

Every declared invariant is classified as exactly one of:

```text
violated
not_found_within_bound
inconclusive
```

`not_found_within_bound` is bounded evidence only. `inconclusive` stays unresolved and fails closed; neither is converted into a security certification.

### Automatic path exploration

The bounded breadth-first explorer searches shortest paths first. Parameterized steps can model contract calls, business values, actor choices, or time deltas.

Repository fixtures demonstrate findings such as:

```text
fund → release → refund → payout conservation violated
```

```text
fund(101) → deposit-cap invariant violated
```

```text
fund(1) → wait(1 day) → refund → timing invariant violated
```

### State hashing and deduplication

Equivalent reachable states can be pruned while preserving a shortest representative path.

The state hash is part of the QA model. It must include every modeled value that can change future behavior; an incomplete hash can make pruning unsound.

The engine caps retained unique states and attempted transitions so bounded search fails closed rather than consuming unbounded resources.

### Authorized fixed-block fork testing

The fork layer requires explicit authorization metadata, exact chain/block/target provenance, and a secret RPC alias.

A public address, public ABI, source repository, or RPC endpoint is not treated as authorization.

The default CI does not open an external fork. Real target execution remains behind the dedicated authorization and adapter gates documented in [`docs/FORK_TESTING.md`](docs/FORK_TESTING.md) and [`docs/FORK_ADAPTER_TEMPLATE.md`](docs/FORK_ADAPTER_TEMPLATE.md).

### Deterministic capture, reporting, and evidence

Foundry can capture actual discovered/replayed paths into strict machine-readable result JSON. Results are cryptographically bound to the reviewed manifest fingerprint.

The runtime then produces deterministic findings, Markdown, engagement summaries, and evidence ZIPs with independent semantic verification.

## `cgqa` commands

```bash
cgqa demo --output-dir cgqa-demo
cgqa doctor --require-forge
cgqa init-engagement acme-escrow
cgqa fingerprint --manifest manifests/client.json
cgqa validate --manifest manifests/client.json
cgqa validate --manifest manifests/client.json --result results/client.result.json
cgqa reachability --model scenarios/adversarial-wallet-replay.json
cgqa run --config cgqa.toml --clean
cgqa engagement-run --config engagements/acme-escrow/cgqa.toml
cgqa verify-bundle dist/client.evidence.zip
cgqa verify-engagement-bundle dist/client.engagement.zip
```

Automation-facing exit codes are documented in [`docs/CLI.md`](docs/CLI.md).

## Recommended commercial workflow

```text
self-serve demo
  ↓
client proof pack
  ↓
fixed-scope pilot
  ↓
written authorization / safe-harbor scope
  ↓
init-engagement
  ↓
review adapter + state hash + invariants
  ↓
one-command engagement-run
  ↓
human severity/impact review
  ↓
client report + independently verifiable evidence ZIP
  ↓
fix → exact replay → retest bundle
```

The repository includes a client proof pack under [`docs/client-proof/`](docs/client-proof/) that is regression-bound to repository-owned evidence and explicitly separated from a completed external audit claim.

## Repository layout

```text
contractgraph_qa/
  cli.py
  demo.py
  product.py
  engagement.py
  engagement_run.py
  scaffold.py
  finding.py
  report.py
  reachability.py
  demo_assets/

src/harness/
  CausalGraphHarness.sol
  PathExplorerHarness.sol
  ParameterizedPathExplorerHarness.sol
  StateDedupPathExplorerHarness.sol
  MultiInvariantStateExplorerHarness.sol
  ForkAuthorization.sol
  ForkContextHarness.sol
  ForkAdapterTemplate.sol
  DirectResultCaptureHarness.sol
  DirectEngagementCaptureHarness.sol

src/examples/
test/
capture-test/
fork-test/
engagements/
manifests/examples/
results/examples/
results/generated/
reports/examples/
graph/schema/
scenarios/

tools/
docs/
  PRODUCT.md
  CLI.md
  ENGAGEMENT.md
  ADVERSARIAL_REACHABILITY.md
  DISTRIBUTION.md
  RELEASE.md
  client-proof/
```
