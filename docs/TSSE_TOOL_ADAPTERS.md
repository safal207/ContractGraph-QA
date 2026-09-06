# TSSE Reviewed Tool Adapters v0.1

`cgqa tsse-adapt` connects Cargo/Soroban, Foundry, Echidna, Medusa, and Slither evidence to
the TSSE transition verifier without treating untrusted scanner output as a
security verdict.

```text
source bytes + raw tool bytes + reviewed observations
                         ↓ recompute every artifact SHA-256
             exact subject + adapter profile binding
                         ↓ compile, never guess
                    TSSE model
                         ↓ locked fail-closed requirements
              bounded TSSE result / HOLD
```

The adapter records the original command and bounds, but never executes a
command found in input JSON.

## Commands

Verify the repository-owned Foundry example and optionally save the generated
TSSE model:

```bash
cgqa tsse-adapt \
  --capture scenarios/tsse-tools/foundry-capture.json \
  --profile scenarios/tsse-tools/foundry-profile.json \
  --model-out tsse-model.json \
  --output adapter-result.json
```

Import Slither detector output as static replay seeds:

```bash
cgqa tsse-adapt \
  --capture scenarios/tsse-tools/slither-capture.json \
  --profile scenarios/tsse-tools/slither-profile.json
```

Import one reviewed Cargo/Soroban test receipt and its state snapshot:

```bash
cgqa tsse-adapt \
  --capture scenarios/tsse-tools/soroban-capture.json \
  --profile scenarios/tsse-tools/soroban-profile.json \
  --model-out soroban-model.json \
  --output soroban-adapter-result.json
```

Existing outputs require `--force`. Output paths cannot replace the capture,
profile, any bound source artifact, any raw scanner artifact, or each other.
`--model-out` requires a companion `--output`; the adapter receipt is committed
first so a model is never published without its normalization receipt.

## Capture contract

The strict input schema is:

`graph/schema/tsse-tool-capture.schema.json`

The separate reviewer-controlled profile schema is:

`graph/schema/tsse-tool-profile.schema.json`

The emitted receipt contract is:

`graph/schema/tsse-tool-adapter-result.schema.json`

Every capture declares:

- tool name and exact reported version;
- recorded argv, termination reason, seed, and bounded search settings;
- a self-described repository label, revision label, and source-artifact list
  which must exactly match the separate profile;
- one or more raw scanner/replay artifacts;
- complete reviewed observations for dynamic traces;
- reviewed invariants and executable forbidden phase pairs;
- an explicit applicability scope.

The profile independently pins the accepted tool/version and exit codes,
subject artifact manifest, canonical observation hash for dynamic tools,
invariant policy, forbidden phase pairs, and scope.
The adapter rejects a capture unless every duplicated policy/subject field is
canonically identical to that external profile. Scanner output therefore
cannot silently replace the reviewed policy with a harmless one.
Changing any reviewed time, space, state, environment, actor, authority, value,
incoming action, or evidence reference changes that observation hash and is
rejected before normalization. Slither profiles use `observationHash: null`
because they cannot supply runtime observations.

All artifact paths are relative to the capture file. Parent traversal,
absolute paths, and resolved paths outside the capture directory are rejected.
The adapter reopens every file and compares its raw-byte SHA-256 with the
declared digest.

Completed dynamic captures must record concrete positive test, sequence, time,
and worker bounds. Their recorded executable/subcommand or JSON-output mode is
checked before native parsing; Echidna and Medusa transaction contracts are
also matched to the reviewed spatial observations.

The exact TSSE subject is compiled from the profile rather than accepted from
scanner input:

```text
commit  = sha256(canonical sorted source-artifact manifest)
adapter = tool + adapter-version + reviewed-profile hash
```

The source-artifact manifest binds only the files listed in the capture. It is
not a claim that the list is a complete build inventory.

## Dynamic tools

Cargo/Soroban, Foundry, Echidna, and Medusa use the same linear observation sidecar. Each node
must explicitly provide:

- block, timestamp, and epoch;
- chain, contract, call frame, storage domain, and protocol location;
- phase and state values;
- oracle, token, fee, and implementation environment;
- actor and role;
- authority epoch and status;
- locked and moved value.

The adapter computes causal steps, complete phase+value state hashes,
domain-separated external-environment hashes, subject hashes, predecessor
links, and crossed boundaries. It locks all TSSE requirements to `true`;
scanner input cannot disable them.

The first observation has `incoming: null`. Every later observation carries a
single incoming action with non-empty evidence references. Every declared tool
artifact must be consumed by at least one transition.

### Foundry

Use the strict `cgqa/foundry-replay-observation/v0.1` harness receipt together
with a reviewed observation sidecar. The adapter checks its selected test and
step sequence against the recorded argv and TSSE actions. Do
not make generic `forge test --json` parsing the trust boundary: Foundry has
documented that this output has no stable formal schema. Human-readable
verbosity traces also do not contain authoritative TSSE state by themselves.

Primary artifact kind: `foundry-test-output`.

### Cargo/Soroban

Cargo/Soroban uses the strict `cgqa/cargo-soroban-transition-receipt/v0.1`
receipt. The recorded command must select one package and one exact test with
`cargo test --locked`; the receipt must confirm exactly one matched/passed test
and bind its subject bundle hash. Every post-transition step binds ledger
sequence/timestamp/epoch, network/contract/call frame/storage location, state
and environment hashes, actor/authority, value movement, and a distinct
`soroban-state-snapshot` digest. The adapter never executes Cargo and keeps the
initial pre-state as an explicit verification debt until a native pre-state
snapshot is supplied.

Primary artifact kind: `cargo-soroban-transition-receipt`; supporting artifact
kind: `soroban-state-snapshot`.

### Echidna

The adapter parses the official JSON campaign, binds its seed, one solved
property, and exact minimized transaction-function sequence to the reviewed
observations. That sequence still needs the TSSE observer because it does not
contain complete state/environment snapshots.

Primary artifact kind: `echidna-campaign-json`.

### Medusa

Use the strict `cgqa/medusa-counterexample/v0.1` receipt for one selected,
minimized counterexample/corpus sequence. The adapter binds every function to
one observation action. Never merge interleaved worker logs into a transition
sequence.

Primary artifact kind: `medusa-counterexample`.

## Slither

The Slither branch parses the official `slither --json` detector structure and
produces deterministic, deduplicated static seeds. Each seed retains detector,
impact, confidence, description, relative source locations, and its evidence
artifact.

Slither never emits a TSSE model or TSSE `PASS`. Static findings are hypotheses
for Foundry/Echidna/Medusa challenge and replay. An empty detector list means
only that the selected Slither run emitted no detector result.

Primary artifact kind: `slither-json`.

## Statuses and claim boundary

- `ready` — dynamic evidence normalized and its nested finite TSSE trace passed;
- `hold` — the nested TSSE trace reached a declared violation or failed a
  locked transition requirement;
- `inconclusive` — static-only Slither evidence, including a failed or
  non-terminal Slither run;
- structural, digest, path, or format errors are rejected by the CLI.

Dynamic Cargo/Soroban/Foundry/Echidna/Medusa evidence that is non-terminal, unbounded, uses
an unaccepted exit code, or cannot bind its native sequence is rejected instead
of being promoted to an adapter result.

`ready` is not a scan verdict. The adapter reports `scanVerdict: NOT_ASSESSED`.
It does not prove source-inventory completeness, tool-binary authenticity,
compiler equivalence, campaign coverage, observation correctness, production
security, or exhaustive reachability.

For exact upstream formats, see the
[Foundry JSON schema request](https://github.com/foundry-rs/foundry/issues/7813),
[Echidna repository](https://github.com/crytic/echidna),
[Medusa repository](https://github.com/crytic/medusa), and
[Slither JSON documentation](https://github.com/crytic/slither/wiki/JSON-output).

## Causal engagement spine

- **Spine ID:** `cgqa-tsse-tool-adapters-v0.1`
- **Purpose:** prevent scanner evidence from acquiring stronger meaning while
  crossing into the TSSE graph.
- **Parent invariants:** exact subject binding, raw evidence integrity, locked
  fail-closed policy, no static-to-dynamic promotion, no invented coordinates.
- **Forbidden outcomes:** unverified bytes accepted, incomplete coordinates
  defaulted, scanner input disabling a requirement, Slither producing a runtime
  transition, or nested trace success described as system security.
- **Evidence boundary:** repository fixtures and deterministic tests only;
  production tool runs remain external evidence.
- **Mutation authority:** the current implementation request.
- **Publication/merge authority:** not granted by this document.
- **Verification debt:** native harness templates, exact tool-binary/container
  digests, build/compiler inventories, campaign completeness receipts, and
  independent replay bundles.
