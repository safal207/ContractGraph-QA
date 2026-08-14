# NEO REZONANS Native Segment v0.1 — ContractGraph-QA → ProofPath

## Status

`FCRP-SYSTEM-003` replaces the first synthetic edge from `FCRP-SYSTEM-002` with native contracts on both sides:

```text
ContractGraph-QA native deterministic provider evidence
        ↓ exact local replay
CGQA → ProofPath SCIG adapter
        ↓ authority_transfer = NONE
ProofPath canonical SCIG v0.1 bytes
        ↓ native Rust proofpath-scig verifier
VALID
        ↓
CGQA deterministic bridge receipt over native verifier output
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
    = exact bytes consumed as the native verifier
```

The current capability manifest declares:

```text
id                       = proofpath.scig.v0.1
status                   = CANONICAL
consumer_default_allowed = true
canonical_commit         = 685d50e256a5125a21f4c4584b326411caaa64ad
```

SYSTEM-003 checks the current manifest first and then executes `proofpath-scig` at that exact capability commit. Repository head and capability identity are intentionally not treated as interchangeable facts.

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

The exact ProofPath capability is executed with:

```bash
cargo test --locked -p proofpath-verifier --bin proofpath-scig
cargo run --locked -p proofpath-verifier --bin proofpath-scig -- <generated-scig.json>
```

The bridge accepts native output only when it binds the expected incident and contains:

```text
VERIFICATION PASSED
RESULT       VALID
```

## Receipt boundary

The deterministic `cgqa.proofpath-scig-native-bridge-receipt.v0.1` receipt is produced by ContractGraph-QA **around the native ProofPath verifier output**.

It is not represented as a native ProofPath signed/provenance receipt. That stronger product surface would require a separately promoted ProofPath capability.

The receipt binds:

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
bridge receipt             != ProofPath signed receipt
```

## Next segment

After SYSTEM-003 is canonical, the next candidate is `ProofPath → LiminalDB`: consume a canonical ProofPath evidence/provenance surface and prove that persistence keeps provenance identity separate from semantic compatibility while authority remains absent.
