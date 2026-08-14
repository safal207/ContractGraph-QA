# NEO REZONANS Durable Proof Ingestion v0.1

## Status

**FCRP-SYSTEM-005 — independent verification of the first local/test durable ProofPath handoff.**

SYSTEM-004 established the safe boundary:

```text
ProofPath
→ verified evidence
→ LiminalDB-compatible artifact
→ persistence frontier
```

SYSTEM-005 tests the next causal step using the canonical LiminalDB durable consumer merged at:

`61b02fc81e0cb5cf1f1ed4658ecff58f683cb728`

The system verifier does not treat that merge or its prior CI as self-certifying. ContractGraph-QA independently checks out the exact consumer revision, replays the upstream SYSTEM-004 chain, performs a fresh ephemeral local/test durable write and verifies the result after restart.

## Native chain

```text
real CGQA provider evidence
        ↓
exact local replay
        ↓
canonical ProofPath SCIG
        ↓
native proofpath-scig = VALID
        ↓
SYSTEM-004 native receipt
        ↓
dedicated LiminalDB AuditEvent
        ↓
canonical artifact-only validator
        ↓
separate local/test storage admission
        ↓
canonical ProofPathDurableLedger
        ↓
WAL append + sync
        ↓
new process / full replay
        ↓
byte-exact event + admission recovery
        ↓
same retry = ALREADY_PRESENT
changed artifact = IDEMPOTENCY_CONFLICT
        ↓
AfterSyncBeforeAck recovery proof
        ↓
LTP strict + replay
        ↓
FCRP-SYSTEM-005 PASS
```

## First Meaningful Divergence

SYSTEM-004 intentionally stops before persistence because its consumer contract proves artifact compatibility only:

```text
mode = dry_run
write_performed = false
durable_memory_accepted = false
live_ingestion_performed = false
```

The missing fact is not whether the event *could plausibly be stored*.

The missing fact is whether the same accepted evidence can cross a separately authorized storage boundary and then survive the failure/recovery behaviors that make the word **durable** meaningful.

Therefore SYSTEM-005 does not mutate the SYSTEM-004 artifact validator to return `durable=true`.

It inserts a separate causal edge:

```text
artifact acceptance
        ≠
storage admission
        ≠
durable effect
        ≠
execution authority
```

## Identity model

The experiment keeps six identities separate:

```text
logical_operation_id
    = cross-stage semantic operation identity

ProofPath capability commit
    = verifier capability identity

source event + native receipt digests
    = producer evidence identity

LiminalDB artifact import commit
    = provenance of the artifact-consumer contract

LiminalDB AuditEvent Git blob
    = semantic compatibility identity

LiminalDB durable consumer commit
    = durable implementation capability identity
```

The canonical values are:

```text
SYSTEM-004 causal ancestor
be860d7a6ca089a4514d12a8108d27873b04dfb9

ProofPath SCIG capability
685d50e256a5125a21f4c4584b326411caaa64ad

LiminalDB artifact import contract
00580ff097dee61b45ad3c8a3c36ae5f548f572d

AuditEvent contract blob
fd733971aaae089df770062bcf7f2c2d6d19ca1d

LiminalDB durable consumer
61b02fc81e0cb5cf1f1ed4658ecff58f683cb728

LTP
fc58072d301a487c09227ea09004dc8e99676370

logical operation
crossmint-public-example-001
```

Current ContractGraph-QA integration base is checked separately from the SYSTEM-004 causal ancestor. A later unrelated `main` change is not allowed to erase either fact.

## Storage admission

The artifact validator remains evidence-only and cannot grant storage authority.

The CI harness derives a separate admission reference bound to:

```text
FCRP-SYSTEM-005
+ local_test_only
+ exact ContractGraph-QA subject head
+ exact LiminalDB durable-consumer commit
```

This is intentionally a **test-harness admission**, not a production authorization token.

The durable consumer records:

```text
persistence_scope = local_test_only
storage_write_authorized = true
execution_authorized = false
mutation_authorized = false
external_effects_authorized = false
```

## Durable identity and idempotency

The durable key is based on:

```text
namespace + logical_operation_id + semantic record kind
```

not payload bytes.

That makes an ambiguous retry testable:

```text
same operation + exact same accepted evidence
→ ALREADY_PRESENT
→ event_count remains 1
→ first transaction_time remains unchanged
```

while a semantic mutation cannot silently become a new durable operation:

```text
same operation + changed event/admission
→ ERROR_CODE IDEMPOTENCY_CONFLICT
→ no second durable record
```

## Post-commit false failure at the persistence layer

The canonical consumer includes a dedicated `AfterSyncBeforeAck` fault test:

```text
WAL frame written
→ sync succeeds
→ acknowledgement path fails
→ caller receives error
→ writer becomes poisoned
→ process closes
→ reopen replays one durable record
→ same retry deduplicates
```

This is the storage analogue of the Post-Commit False Failure class:

> **A failed acknowledgement after commit must not be interpreted as permission to create a second durable effect.**

SYSTEM-005 independently runs the canonical fault-injection regression at the exact consumer commit.

## Bi-temporal contract

The durable record preserves:

```text
valid_time_ms
transaction_time_ms
```

with:

```text
transaction_time_ms >= valid_time_ms
```

`valid_time_ms` identifies the represented observation time. `transaction_time_ms` identifies the first durable recording time.

An idempotent retry may happen later but must not rewrite the first transaction time because no second durable event occurred.

## Restart proof

The system gate deliberately uses two processes:

1. `ingest` opens the canonical LiminalDB durable ledger and writes the accepted event;
2. that process exits;
3. `inspect` opens the same namespace again;
4. LiminalDB replays the WAL from durable bytes;
5. the recovered event and artifact-admission files are compared byte-for-byte with the originals.

A green result therefore does more than re-read an in-memory object.

## Negative controls

SYSTEM-005 fails closed when:

- the current ContractGraph-QA subject is not descended from SYSTEM-004;
- the current integration base is not the expected PR base;
- ProofPath's manifest no longer identifies the pinned SCIG capability as canonical/default consumable;
- the native ProofPath verifier does not return `VALID`;
- the artifact-only LiminalDB consumer no longer returns the expected dry-run non-authorizing boundary;
- the exact LiminalDB durable consumer revision is unavailable;
- the AuditEvent contract blob changes;
- byte-exact restart replay changes either stored source file;
- a retry creates a second durable record or changes the original transaction time;
- a changed artifact under the same operation does not produce the stable `IDEMPOTENCY_CONFLICT` class;
- the canonical `AfterSyncBeforeAck` recovery regression fails;
- LTP strict trace inspection or replay fails;
- the FCRP case does not independently evaluate to `PASS`.

## Authority boundary

SYSTEM-005 crosses only a **local/test persistence frontier**.

It does not prove or authorize:

- production LiminalDB ingestion;
- service/API exposure;
- remote or distributed writes;
- tenant authorization policy;
- credentials;
- deployment;
- payment;
- repository mutation outside this review flow;
- external side effects;
- execution authority inferred from persisted evidence.

The persistent object may say that a ProofPath verification was accepted and durably stored. It may not say that the underlying real-world claim is therefore true, executable or authorized.

## What SYSTEM-005 proves if green

Within the pinned revisions and ephemeral local/test namespace:

1. the real SYSTEM-004 logical operation reaches the durable consumer unchanged;
2. native ProofPath verification still precedes artifact projection and persistence;
3. artifact acceptance and storage admission remain distinct facts;
4. exact event/admission bytes are durably stored and reproduced after process restart;
5. producer capability identity and consumer compatibility identity remain separate;
6. `valid_time` and first `transaction_time` remain replayable;
7. same-semantic retry creates no duplicate durable effect;
8. changed evidence under the same operation fails with a machine-stable conflict class;
9. synced-but-unacknowledged append recovers without duplicate state;
10. persistence grants no execution, mutation or external-effect authority;
11. the agent path itself remains admissible under native LTP strict replay.

## What remains unproven

The next layers still require separate evidence:

- production authorization and tenant policy;
- distributed durability / replication;
- rollback resistance against replacement of an entire internally consistent local history;
- retention and compaction of exact ProofPath payloads;
- transparency anchoring or independent replicas;
- multi-writer semantics beyond the current exclusive-writer model;
- downstream RINSE consumption of the durable record without creating a second interpretation authority.

## Current system wording

After a green SYSTEM-005 the correct local/test system map becomes:

```text
ProofPath
→ verified evidence
→ LiminalDB artifact acceptance
→ separate local/test storage admission
→ durable evidence state
→ restart-replayable proof record
```

The qualifier **local/test** remains load-bearing until a later production-authority gate exists.
