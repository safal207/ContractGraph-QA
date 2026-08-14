# NEO REZONANS Native ProofPath → LiminalDB v0.1

## Status

**FCRP-SYSTEM-004 — native evidence handoff up to the persistence frontier.**

This experiment replaces the synthetic ProofPath → LiminalDB heartbeat edge with native contracts on both sides while deliberately refusing to claim durable persistence.

```text
native ProofPath SCIG verification
        ↓
exact native receipt
        ↓
dedicated LiminalDB AuditEvent projection
        ↓
canonical LiminalDB artifact-only validator
        ↓
LTP strict trajectory inspection
        ↓
STOP BEFORE PERSISTENCE
```

## First Meaningful Divergence

The whole-system shorthand previously described the LiminalDB stage as:

```text
ProofPath
   ↓
LiminalDB
   ↓
durable verified state
```

The canonical consumer surface did not yet justify that claim.

The first dedicated ProofPath consumer contract in LiminalDB is intentionally:

```text
mode = dry_run
write_performed = false
durable_memory_accepted = false
live_ingestion_performed = false
```

Therefore:

> **Native consumer acceptance is not durable persistence.**

SYSTEM-004 corrects the system model to the strongest currently executable claim rather than extending the implementation to satisfy an over-strong diagram.

## Why the Lotus import contract is not reused

The canonical Lotus profile is semantically specific:

```text
actor  = liminalqa-lotus
action = lotus.finding.observed
```

A ProofPath SCIG verification is a different fact. Relabeling it as Lotus merely to reuse a green validator would create semantic identity drift.

LiminalDB therefore now exposes a dedicated canonical ProofPath artifact profile:

```text
actor  = proofpath-scig-native-verifier
action = proofpath.scig.verification.observed
schema = liminaldb-proofpath-audit-event-v0.1
```

Canonical LiminalDB import-contract commit:

`00580ff097dee61b45ad3c8a3c36ae5f548f572d`

Current `AuditEvent` contract blob:

`fd733971aaae089df770062bcf7f2c2d6d19ca1d`

## Identity model

SYSTEM-004 keeps these coordinates separate:

```text
ProofPath capability commit
    = verifier capability provenance

ProofPath dependency lock
    = execution dependency identity

SCIG / native receipt digests
    = evidence identity

LiminalDB repository commit
    = consumer snapshot provenance

LiminalDB AuditEvent Git blob
    = current semantic compatibility identity

logical_operation_id
    = end-to-end semantic operation identity
```

None is inferred from another.

This composes earlier lessons:

```text
repository head ≠ capability identity
source commit ≠ dependency-resolution identity
historical provenance ≠ current semantic compatibility
```

## Native producer lane

SYSTEM-004 replays the same safe source chain used by SYSTEM-003:

```text
ContractGraph-QA provider evidence
→ exact local replay
→ ProofPath SCIG projection
→ current ProofPath capability manifest
→ canonical proofpath.scig.v0.1 bytes
→ generated-and-bound Cargo.lock
→ native Rust proofpath-scig
→ RESULT VALID
→ deterministic native bridge receipt
```

The source receipt must preserve:

```text
authorityTransfer = NONE
executionAuthorized = false
mutationAuthorized = false
externalEffectsPerformed = false
```

## Native consumer lane

The verified native ProofPath receipt is projected into the dedicated LiminalDB AuditEvent profile.

The canonical LiminalDB validator then checks:

- exact ProofPath capability identity;
- native verifier result `VALID`;
- exact SCIG and bridge-receipt digest shapes;
- preserved `logical_operation_id` / `correlationId`;
- bounded and replayable evidence;
- exact current `AuditEvent` contract blob;
- event SHA-256 integrity;
- zero execution, mutation, persistence, deployment or merge grants;
- artifact-only write semantics.

A consumer PASS means:

> the event is compatible with the current ProofPath-specific LiminalDB AuditEvent artifact contract.

It does not mean:

> the event was appended to a live LiminalDB journal.

## Path-admissibility lane

A correct final JSON object is not enough.

SYSTEM-004 generates a four-frame LTP trajectory:

```text
proofpath-native-verified
        ↓
liminaldb-audit-event-projected
        ↓
liminaldb-dry-run-validated
        ↓
stop-before-persistence
```

All frames carry one stable continuity token and the same logical operation identity.

The exact LTP revision is pinned to:

`fc58072d301a487c09227ea09004dc8e99676370`

The native `ltp:inspect` tool runs in strict JSON mode and the path is replayed separately.

This implements the Signal 013 rule:

> **Output correct does not imply path admissible.**

## Negative controls

SYSTEM-004 fails closed on at least these mutations:

- logical-operation identity drift;
- tampered ProofPath native receipt digest;
- authority transfer from ProofPath;
- wrong canonical LiminalDB import-contract commit;
- changed `AuditEvent` contract bytes;
- LiminalDB report claiming durable memory or live ingestion;
- omitted consumer validation in the modeled path;
- LTP continuity or trace-contract failure.

## Authority boundary

The entire segment remains evidence-only:

```text
authorityTransfer          = NONE
executionAuthorized        = false
mutationAuthorized         = false
persistenceAuthorized      = false
externalEffectsPerformed   = false
persistenceFrontierCrossed = false
```

A PASS grants no repository write, live database write, deployment, external contact, payment, disclosure or merge authority.

## What SYSTEM-004 proves if green

Within the pinned revisions and synthetic bounded source case:

1. the same logical operation survives the ProofPath → LiminalDB handoff;
2. native ProofPath verification precedes the consumer projection;
3. producer provenance is not confused with consumer compatibility identity;
4. the canonical LiminalDB ProofPath artifact validator accepts the event;
5. the consumer reports no write and no durable-memory acceptance;
6. the path to that result remains inspectable by native LTP tooling;
7. authority does not leak through the evidence path;
8. the system explicitly stops at the currently unproven persistence frontier.

## What remains unproven

SYSTEM-004 does not establish:

- live LiminalDB journal append;
- durable storage across process restart;
- bi-temporal persistence of `valid_time` and `transaction_time`;
- namespace or tenant isolation for ProofPath ingestion;
- idempotent append semantics;
- atomicity between journal append, index update and acknowledgement;
- rejection / rollback recovery;
- retention or compaction behavior;
- independent organizational replication;
- truth of an arbitrary ProofPath incident;
- persistence authority.

## Next falsifiable question

**FCRP-SYSTEM-005 — Durable Proof Ingestion v0.1**

Can an explicitly authorized local/test LiminalDB ingestion path persist the accepted ProofPath evidence and reproduce it after restart while preserving:

```text
logical_operation_id
producer provenance
consumer contract identity
valid_time
transaction_time
idempotent append identity
zero execution-authority escalation
```

and fail closed on duplicate, stale, incompatible, partially committed, or rollback-required ingestion?

Until that gate exists and passes, the canonical system wording should remain:

```text
ProofPath
→ verified evidence
→ LiminalDB-compatible artifact
→ persistence frontier
```

not `durable verified state`.
