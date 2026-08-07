# ContractGraph-QA

**Causal-temporal smart-contract QA with reproducible evidence.**

ContractGraph-QA treats a smart contract as a reachable state space rather than a collection of isolated functions.

The core question is:

> Can an allowed sequence of actors, transactions, parameter values, and time changes drive the contract into a state that violates an explicit business or security invariant?

## v1.0 product runtime

The engine is exposed through an installable `cgqa` CLI that turns a reviewed adapter model and deterministic Foundry search into a client-verifiable evidence bundle.

```text
AUTHORIZED SCOPE
      ↓
REVIEWED ADAPTER MANIFEST
      ↓
FOUNDRY SEARCH
      ↓
MINIMAL VIOLATING PATH
      ↓
DETERMINISTIC REPLAY
      ↓
OBSERVED PRE/POST STATE
      ↓
EXPLORER RESULT JSON
      ↓
PROVENANCE VALIDATION
      ↓
FINDING JSON
      ↓
CLIENT MARKDOWN REPORT
      ↓
DETERMINISTIC EVIDENCE ZIP
      ↓
INDEPENDENT VERIFICATION
```

### Quick start

Requirements: Python 3.11+ and Foundry.

```bash
python -m pip install -e .
cgqa doctor --require-forge
cgqa run --config cgqa.example.toml --clean
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

The repository-owned demo produces:

```text
dist/CGQA-005/CGQA-005.finding.json
dist/CGQA-005/CGQA-005.md
dist/CGQA-005/CGQA-005.evidence.zip
```

`cgqa run` does not return success until the generated evidence bundle has been independently re-opened and verified against the manifest → result → finding → report semantic chain.

See [`docs/PRODUCT.md`](docs/PRODUCT.md), [`docs/CLI.md`](docs/CLI.md), and [`docs/ENGAGEMENT.md`](docs/ENGAGEMENT.md).

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
- temporal/deadline conditions.

### Automatic path exploration

The bounded breadth-first explorer searches shortest paths first. Parameterized steps can model contract calls, business values, actor choices, or time deltas.

The repository fixtures demonstrate findings such as:

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

### Deterministic result capture and reporting

Foundry can capture the actual discovered/replayed path into machine-readable result JSON. The result is cryptographically bound to the canonical reviewed-manifest fingerprint.

The reporting layer then produces:

- strict finding JSON;
- deterministic client Markdown;
- deterministic evidence ZIP;
- bundle SHA-256 for delivery verification.

## `cgqa` commands

```bash
cgqa doctor --require-forge
cgqa fingerprint --manifest manifests/client.json
cgqa validate --manifest manifests/client.json
cgqa validate --manifest manifests/client.json --result results/client.result.json
cgqa run --config cgqa.toml --clean
cgqa verify-bundle dist/client.evidence.zip
```

Automation-facing exit codes are documented in [`docs/CLI.md`](docs/CLI.md).

## Product configuration

`cgqa run` uses a strict TOML project file. The checked-in local example is:

```toml
schemaVersion = 1
workingDirectory = "."
manifest = "manifests/examples/adapter-fixture.json"
result = "results/generated/CGQA-005.result.json"
finding = "dist/CGQA-005/CGQA-005.finding.json"
report = "dist/CGQA-005/CGQA-005.md"
bundle = "dist/CGQA-005/CGQA-005.evidence.zip"

[capture]
enabled = true
profile = "capture"
test = "test_CaptureExplorerResult"
verbosity = 3
```

Capture is invoked as a process argument array rather than a shell command string. Profile/test identifiers are restricted to safe identifier characters.

## Evidence bundle

A v1 evidence ZIP contains exactly:

```text
manifest.json
result.json
finding.json
report.md
bundle.json
```

`bundle.json` records the tool version, finding ID, canonical manifest SHA-256, and exact SHA-256/byte count of every artifact.

The verifier checks:

1. exact bundle entry set/order;
2. per-entry size limits;
3. byte counts and hashes;
4. manifest/result validation;
5. adapter/scope/manifest provenance;
6. deterministic finding re-export;
7. deterministic Markdown re-render.

Identical evidence inputs produce identical bundle bytes.

## Recommended engagement workflow

For a real authorized client engagement:

1. obtain and record written scope;
2. pin chain, target, and fixed snapshot block;
3. review the adapter manifest and executable adapter;
4. define finite action/parameter/time corpora and invariants;
5. run `cgqa validate` before execution;
6. run the authorized adapter through `cgqa run`;
7. review severity/impact/recommendation as a human;
8. deliver Markdown + evidence ZIP + bundle SHA-256;
9. replay the exact path after the fix and generate a new bundle.

See [`docs/ENGAGEMENT.md`](docs/ENGAGEMENT.md).

## Repository layout

```text
contractgraph_qa/
  __init__.py
  cli.py
  product.py

src/harness/
  CausalGraphHarness.sol
  PathExplorerHarness.sol
  ParameterizedPathExplorerHarness.sol
  StateDedupPathExplorerHarness.sol
  ForkAuthorization.sol
  ForkContextHarness.sol
  ForkAdapterTemplate.sol
  DirectResultCaptureHarness.sol

src/examples/
  Escrow.sol
  VulnerableEscrow.sol
  VulnerableTimedEscrow.sol
  ConvergentStateMachine.sol
  AdapterFixtureMachine.sol

test/
  EscrowGraph.t.sol
  VulnerableEscrowGraph.t.sol
  PathExplorer.t.sol
  ParameterizedTemporalExplorer.t.sol
  StateDedupPathExplorer.t.sol
  ForkAuthorization.t.sol
  ForkAdapterTemplate.t.sol

capture-test/
  AdapterFixtureCapture.t.sol

fork-test/
  AuthorizedForkSmoke.t.sol
  AuthorizedAdapterTemplate.t.sol.example

manifests/examples/
results/examples/
results/generated/
reports/examples/
graph/schema/

tools/
  export_finding.py
  render_finding.py
  manifest_fingerprint.py
  validate_fork_scope.py

docs/
  PRODUCT.md
  CLI.md
  ENGAGEMENT.md
  RELEASE.md
  CAUSAL_MODEL.md
  INVARIANTS.md
  PATH_EXPLORER.md
  PARAMETER_TIME_EXPLORER.md
  STATE_DEDUP.md
  FORK_TESTING.md
  FORK_ADAPTER_TEMPLATE.md
  ADAPTER_MANIFEST.md
  DIRECT_RESULT_CAPTURE.md
  REPORTING.md

.github/workflows/
  ci.yml
  reporting.yml
  product.yml
  authorized-fork.yml
```

## Development and release gates

```bash
forge fmt --check
forge build --sizes
forge test -vvv
python -m unittest discover -s tools/tests -p 'test_*.py' -v
python -m pip wheel . --no-deps --wheel-dir .product-wheel
cgqa run --config cgqa.example.toml --clean
cgqa verify-bundle dist/CGQA-005/CGQA-005.evidence.zip
```

Release/version policy: [`CHANGELOG.md`](CHANGELOG.md) and [`docs/RELEASE.md`](docs/RELEASE.md).

Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## What ContractGraph-QA proves — and what it does not

ContractGraph-QA provides reproducible evidence **within an explicit bounded model**.

It does not claim that:

- bounded graph exploration proves an arbitrary protocol secure;
- the chosen invariants are complete;
- the state hash is automatically complete;
- a finite parameter corpus covers every possible value;
- a QA engagement is equivalent to formal verification or an independent full security audit.

Security conclusions remain limited to the modeled actors, actions, parameters, time assumptions, search depth, state-hash completeness, authorization scope, fork snapshot, adapter mapping, manifest correctness, capture mapping, and explicit invariants.

## Evolution

- **v0.1** — causal-temporal graph model, fixtures, invariants, CI, Slither.
- **v0.2** — bounded BFS path explorer and deterministic replay.
- **v0.3** — deterministic client finding reports.
- **v0.4** — parameter and time exploration.
- **v0.5** — state hashing and equivalent-state pruning.
- **v0.6** — authorization-gated fixed-block fork context.
- **v0.7** — contract-specific fork adapter template.
- **v0.8** — strict adapter manifest/result contract and automatic finding export.
- **v0.9** — direct Foundry result capture.
- **v1.0** — installable product runtime, one-command pipeline, evidence bundles, independent verification, and product E2E CI.

## Safety

Use ContractGraph-QA only on contracts you own, repository-local/open-source test fixtures, systems where you have explicit authorization, or public bug-bounty assets strictly within their published scope and rules.

Never commit RPC secrets, private keys, seed phrases, or client credentials.

See [`SECURITY.md`](SECURITY.md).

## License

Apache-2.0
