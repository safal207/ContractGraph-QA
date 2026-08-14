# NEO REZONANS Native Segment v0.1 — ContractGraph-QA → ProofPath

## Status

`FCRP-SYSTEM-003` replaces the first synthetic edge from `FCRP-SYSTEM-002` with native contracts on both sides:

```text
ContractGraph-QA native deterministic provider evidence
        ↓ exact local replay
CGQA → ProofPath SCIG adapter
        ↓ authority_transfer = NONE
ProofPath canonical SCIG v0.1 source bytes
        ↓ generated dependency lock is captured and bound
ProofPath native Rust proofpath-scig verifier under --locked
VALID
        ↓
CGQA deterministic bridge receipt
        + native-segment evidence envelope
```

This is the first native segment of the NEO REZONANS heartbeat. It is **not** yet full runtime interoperability.

## Why this segment first

ContractGraph-QA already has a canonical deterministic provider-decision evidence pack. ProofPath already has one manifest-declared canonical/default-consumable causal verifier: `proofpath.scig.v0.1`.

The richer ProofPath PoCI, Evidence Builder, Control Cloud, admission and governance stack remains `PROPOSED`. SYSTEM-003 deliberately does not import it.

## Capability identity

ProofPath has two relevant identities:

```text
current ProofPath repository main
    = where the capability manifest is read

proofpath.scig.v0.1 canonical capability commit
    = exact source bytes consumed as the native verifier
```

The current capability manifest declares:

```text
id                       = proofpath.scig.v0.1
status                   = CANONICAL
consumer_default_allowed = true
canonical_commit         = 685d50e256a5125a21f4c4584b326411caaa64ad
```

SYSTEM-003 checks the current manifest first and then executes `proofpath-scig` from that exact capability commit. Repository head and capability identity are intentionally not treated as interchangeable facts.

## Dependency-resolution identity

The first native run exposed another identity boundary: **ProofPath does not commit a workspace `Cargo.lock`**, including at the canonical SCIG capability commit and at current `main`.

Therefore:

```text
exact source commit
!=
exact dependency resolution
```

SYSTEM-003 does not solve this by silently removing `--locked`.

Instead the gate executes:

```text
exact SCIG capability checkout
        ↓
cargo generate-lockfile
        ↓
copy generated Cargo.lock into evidence
        ↓
compute Cargo.lock SHA-256
        ↓
record Rust/Cargo versions
        ↓
cargo test --locked
cargo run  --locked
```

The generated lock is a **run-specific dependency-resolution identity**. It is stored beside the native verifier output and bound into `cgqa.native-segment-evidence.v0.1` together with the bridge receipt digest and exact capability commit.

This means a later dependency-resolution change cannot masquerade as the same proof. It must produce a different evidence identity.

It does **not** mean the generated lock was authored or endorsed by ProofPath.

## Native ContractGraph-QA producer

The source is `contractgraph_qa/provider_decision_evidence.py`.

For the first proof it uses the already-reviewed Crossmint public-contract fixtures:

- `crossmint-public-contract.v0.1.json`
- `crossmint-observations-get-success.json`
- explicit fixture authority evidence
- decision id `crossmint-evidence-pack-example`

The native CGQA path must first produce and replay-verify:

```text
decision = STOP
monetaryActionAllowed = false
```

The adapter does not accept a producer-authored success assertion as sufficient evidence.

## Cross-repository claim boundary

A subtle boundary matters here: the CGQA pack's `claimBoundary` is not part of the four embedded payload digests. Therefore successful provider-decision replay alone does not prove those metadata flags were not weakened after the pack was built.

The cross-repository adapter explicitly requires:

```text
classification           = PUBLIC_CONTRACT_REPLAY_EVIDENCE
networkCallsPerformed    = false
walletExecutionPerformed = false
securityCertification    = false
productionAuthorization  = false
financialAuthorization   = false
```

It also requires the provider-decision authority classification to remain non-authorizing.

This is intentional: a boundary verifier may need to be stricter than either local component when it composes their claims.

## SCIG projection

`contractgraph_qa/proofpath_scig_adapter.py` emits an ordinary SCIG v0.1 document plus additive extension fields. SCIG v0.1 allows additional properties and the native Rust verifier does not deny unknown fields.

The extension binds:

```text
logical_operation_id
source_evidence_pack_sha256
consumer_capability
consumer_capability_commit
authority_transfer = NONE
authorization_ref = null
execution_authorized = false
mutation_authorized = false
external_effects_performed = false
```

The native SCIG contract still validates its own state transition, invariant, causal-edge, recovery, verification and evidence-reference rules.

## Native verifier

After generating and recording the run-specific lock, the exact ProofPath capability is executed with:

```bash
cargo generate-lockfile
cargo test --locked -p proofpath-verifier --bin proofpath-scig
cargo run --locked -p proofpath-verifier --bin proofpath-scig -- <generated-scig.json>
```

The bridge accepts native output only when it binds the expected incident and contains:

```text
VERIFICATION PASSED
RESULT       VALID
```

## Receipt and evidence boundary

The deterministic `cgqa.proofpath-scig-native-bridge-receipt.v0.1` receipt is produced by ContractGraph-QA **around the native ProofPath verifier output**.

It is not represented as a native ProofPath signed/provenance receipt. That stronger product surface would require a separately promoted ProofPath capability.

The bridge receipt binds:

```text
logicalOperationId
sourceEvidencePackSha256
SCIG digest
ProofPath capability ID
ProofPath capability commit
native verifier identity/result
authorityTransfer = NONE
executionAuthorized = false
mutationAuthorized = false
externalEffectsPerformed = false
```

The surrounding `cgqa.native-segment-evidence.v0.1` envelope additionally binds:

```text
current ProofPath main observed by the gate
ProofPath capability commit
ProofPath generated Cargo.lock SHA-256
bridge receipt digest
FCRP-SYSTEM-003 decision
```

The uploaded evidence directory also includes the generated `proofpath-Cargo.lock` and a `SHA256SUMS` file covering the complete evidence set.

## Fail-closed regressions

The focused suite rejects:

- tampered CGQA evidence packs;
- claim-boundary mutation that invents production authorization;
- claim-boundary mutation that invents network activity;
- wrong ProofPath canonical capability commit;
- native verifier output that is not `VALID`;
- authority reappearing in the ProofPath projection.

CI additionally reads the **current** ProofPath manifest before checking out the exact capability commit. If SCIG is later demoted, superseded, or stops being default-consumable, the native segment must not silently continue as canonical.

## Safety boundary

SYSTEM-003 performs no provider call, wallet action, payment, deployment, repository mutation in downstream systems, or production execution. The Crossmint inputs are repository fixtures and the ProofPath verifier consumes a generated local JSON document.

```text
native evidence producer != live provider execution
native verifier           != external endorsement
VALID                      != execution authority
generated Cargo.lock       != ProofPath-authored lock
bridge receipt             != ProofPath signed receipt
```

## Next segment

After SYSTEM-003 is canonical, the next candidate is `ProofPath → LiminalDB`: consume a canonical ProofPath evidence/provenance surface and prove that persistence keeps provenance identity separate from semantic compatibility while authority remains absent.
