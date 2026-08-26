<!-- seo-product-intro:start -->
# ContractGraph-QA — Smart Contract QA & State-Transition Testing

**Causal-temporal smart-contract testing for Solidity, Foundry, escrow, settlement, payouts, DeFi, and other stateful financial workflows.**

ContractGraph-QA finds **reachable economic failures** that isolated function tests can miss: stuck funds, duplicate settlement, broken value conservation, unsafe retries, transaction-ordering races, stale authorization, and exact-time boundary defects.

> Can an allowed sequence of actors, transactions, parameter values, retries, concurrency, and time changes drive the contract into a state that violates an explicit business or security invariant?

```text
actor → action → pre-state → transition → post-state → effect
                        ↓
               invariant + replayable evidence
```

## Why teams use ContractGraph-QA

| Need | ContractGraph-QA provides |
|---|---|
| Smart-contract QA before release | Bounded state-space exploration and native framework test planning |
| Solidity / Foundry invariant testing | Reviewed action, state, and invariant models with deterministic replay |
| Escrow, payout, vesting, or settlement review | Economic-path pressure tests across retries, concurrency, and timing boundaries |
| Reproducible findings | Minimal violating paths, observed pre/post state, source receipts, and verifiable evidence bundles |
| Honest assurance language | `violated`, `not_found_within_bound`, or `inconclusive` — never an unsupported security certification |

**Open for fixed-scope verification engagements:** start with one critical workflow and one economic promise.  
[Request a review](mailto:safal0645@gmail.com?subject=ContractGraph-QA%20fixed-scope%20review) · [Run the quickstart](#test-your-project-in-one-command) · [See the product demo](#try-the-product-demo)
<!-- seo-product-intro:end -->

## Test your project in one command

Start from any local smart-contract repository without writing an adapter first:

```bash
python -m pip install contractgraph-qa
cgqa quickstart --target /path/to/project
```

The default quickstart is read-only with respect to project code. It detects common ecosystems and frameworks, inventories contract/program declarations, computes a source fingerprint, surfaces bounded Solidity review signals, plans the native test command, and writes:

```text
<project>/.cgqa/quickstart/
  quickstart.json
  REPORT.md
```

Detected front doors include Foundry, Hardhat, Truffle, Ape/Brownie/Vyper, Soroban, Anchor, Move, and Cairo/Scarb. Run local project tests only after reviewing the command:

```bash
cgqa quickstart --target /path/to/project --run-native
```

`--run-native` is never implied. Review signals are investigation prompts, not vulnerability findings; native test success is not a security proof. Deep stateful analysis still requires a reviewed action/state/invariant model or adapter.

See [`docs/UNIVERSAL_QUICKSTART.md`](docs/UNIVERSAL_QUICKSTART.md).

## Try the product demo

The fastest repository-owned proof path needs only Python 3.11+ and the installed wheel:

```bash
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
PROJECT QUICKSTART / EXACT SUBJECT
      ↓
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
MEASUREMENT POPULATION + SOURCE RECEIPT
      ↓
MEASUREMENT PROVENANCE
      ↓
CLIENT FINDINGS / ENGAGEMENT REPORT
      ↓
PROVENANCE-BOUND EVIDENCE ZIP
      ↓
INDEPENDENT VERIFICATION
```

For deep Foundry execution, run:

```bash
cgqa quickstart --target .
cgqa doctor --require-forge
cgqa init-engagement acme-escrow
# Replace every generated TODO only after explicit scope/authorization review.
cgqa engagement-run --config engagements/acme-escrow/cgqa.toml
cgqa verify-engagement-bundle engagements/acme-escrow/evidence/engagement.evidence.zip
```

The generated scaffold deliberately starts fail-closed and is not execution-ready until the operator replaces the authorization, target, state-hash, action, invariant, and capture-adapter TODOs.

### Measurement provenance in v1.8+

For multi-invariant engagement evidence, ContractGraph-QA derives the eligible measurement population from the invariant IDs declared in the reviewed manifest and the observed population from the checks actually emitted by the engagement result.

The final engagement wrapper binds exact manifest/result artifact SHA-256 values and contains:

```text
base-engagement.zip
measurement-input.json
measurement-source.json
measurement-provenance.json
bundle.json
```

`cgqa verify-engagement-bundle` auto-detects legacy engagement bundles and provenance wrappers. For a provenance wrapper it independently verifies the embedded legacy evidence, reconstructs the declared/observed populations, checks exact source digests, recomputes the provenance verdict, and rejects `EPOCH_MISMATCH`, `PARTIAL_COVERAGE`, or `UNMEASURED` before the evidence can be treated as authoritative.

A passing provenance boundary means the declared measurement is source-bound and sufficiently covered for its stated requirement. It does **not** mean the selected invariants are complete or that bounded exploration proved the target secure.

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

A reachability model can also be bound into the single-finding product pipeline. The repository-owned binding fixture uses:

```toml
reachabilityModel = "scenarios/adversarial-adapter-fixture.json"
```

Product binding is fail-closed: the selected target capability must be marked forbidden, every path invariant must exist in the reviewed manifest, and the path must include the exact invariant identified by the explorer result. An unrelated reachability model is rejected rather than silently attached to a finding.

`cgqa run` then emits a backward-compatible **bundle v2** containing canonical `reachability-model.json` and recomputable `reachability.json`, and binds the result into `finding.json -> evidence.reachability`. `cgqa verify-bundle` independently re-runs the bundled model and rejects any mismatch in the model hash, impact path, finding invariant binding, or artifact bytes. Configs without `reachabilityModel` continue to produce the existing bundle v1.

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
# Universal project front door
cgqa quickstart --target /path/to/project
cgqa quickstart --target /path/to/project --run-native

# Product/evidence pipeline
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

# Causal-temporal vNext examples
cgqa geometry --model geometry.json
cgqa witness --input witness.json
cgqa subject-freeze --input freeze.json
cgqa trace-integrity --input trace.json
cgqa evidence-readiness --input evidence.json
cgqa plan-verification --input campaign.json
```

Run `cgqa --help` for the full unified command surface. Automation-facing exit codes are documented in [`docs/CLI.md`](docs/CLI.md).

## Recommended commercial workflow

```text
zero-config quickstart
  ↓
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
measurement provenance + source binding
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
  project_quickstart.py
  project_quickstart_cli.py
  demo.py
  product.py
  engagement.py
  engagement_run.py
  engagement_provenance.py
  measurement_provenance.py
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
  UNIVERSAL_QUICKSTART.md
  PRODUCT.md
  CLI.md
  ENGAGEMENT.md
  ADVERSARIAL_REACHABILITY.md
  DISTRIBUTION.md
  RELEASE.md
  client-proof/

.github/workflows/
  ci.yml
  reporting.yml
  product.yml
  measurement-provenance.yml
  distribution.yml
  authorized-fork.yml
```

## Development and release gates

```bash
forge fmt --check
forge build --sizes
forge test -vvv
python -m unittest discover -s tools/tests -p 'test_*.py' -v
python -m pip wheel . --no-deps --wheel-dir .product-wheel
cgqa quickstart --target .
cgqa demo --output-dir /tmp/cgqa-demo
cgqa verify-bundle /tmp/cgqa-demo/CGQA-005.evidence.zip
cgqa engagement-run --config cgqa.engagement.example.toml
cgqa verify-engagement-bundle dist/CGQA-E-001-run/CGQA-E-001.engagement.zip
```

Release/version policy: [`CHANGELOG.md`](CHANGELOG.md) and [`docs/RELEASE.md`](docs/RELEASE.md).
Distribution instructions: [`docs/DISTRIBUTION.md`](docs/DISTRIBUTION.md).
Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## What ContractGraph-QA proves — and what it does not

ContractGraph-QA provides reproducible evidence **within an explicit bounded model**.

It does not claim that:

- quickstart review signals are confirmed vulnerabilities;
- native unit-test success is a security proof;
- bounded graph exploration proves an arbitrary protocol secure;
- the chosen invariants are complete;
- the state hash is automatically complete;
- a finite parameter corpus covers every possible value;
- measurement provenance expands the modeled scope beyond the declared population;
- `not_found_within_bound` means no vulnerability exists;
- a QA engagement is equivalent to formal verification or an independent full security audit.

Security conclusions remain limited to the modeled actors, actions, parameters, time assumptions, search depth, state-hash completeness, authorization scope, fork snapshot, adapter mapping, manifest correctness, capture mapping, measurement coverage scope, source binding, and explicit invariants.

## Product evolution

- **v1.0** — installable runtime, deterministic evidence bundles, independent verification.
- **v1.1** — schema/runtime contract parity gate.
- **v1.2** — multi-invariant engagement engine.
- **v1.3** — direct multi-invariant Foundry capture.
- **v1.4** — one-command `engagement-run`.
- **v1.5** — fail-closed client engagement scaffold.
- **v1.6** — packaged self-serve demo and verified distribution artifact workflow.
- **v1.7** — Linux/Windows portability, deterministic SBOM, checksums, and GitHub/Sigstore release attestations.
- **v1.8** — measurement provenance, independent coverage populations, source receipts, and provenance-bound engagement evidence.
- **v1.9** — universal smart-contract quickstart, framework routing, source inventory, review signals, and one unified vNext CLI.

Earlier v0.x engine milestones remain documented in Git history and the changelog.

## Safety

Use ContractGraph-QA only on contracts you own, repository-local/open-source test fixtures, systems where you have explicit authorization, or public bug-bounty assets strictly within their published scope and rules.

Never commit RPC secrets, private keys, seed phrases, or client credentials.

See [`SECURITY.md`](SECURITY.md).

## License

Apache-2.0