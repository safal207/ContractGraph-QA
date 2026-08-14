# NEO REZONANS Durable State → RINSE Reflection v0.1

## Status

**FCRP-SYSTEM-006 — independent verification of the native LiminalDB → RINSE boundary.**

SYSTEM-005 established a local/test durable ProofPath record:

```text
ProofPath native verification
→ LiminalDB artifact acceptance
→ separate local/test storage admission
→ durable WAL state
→ restart-replayable exact evidence
```

SYSTEM-006 asks the next question:

> Can that exact durable record become a RINSE source trace without becoming truth, being rewritten, or creating a second interpretation authority?

## Canonical consumer

RINSE durable-source consumer:

`3be0d2ceb1440641b141cdb80c82ed118e4186dd`

It performs only:

```text
validate durable bundle
→ build immutable normalized trace
→ create_reflection_record()
→ build_reflection_graph()
```

No ProofPath-specific reflection engine exists.

## Source identity

SYSTEM-006 preserves the durable record identity directly:

```text
RINSE source_trace.id
=
liminaldb-proof-durable:<LiminalDB record_hash>
```

The reflection receives its own deterministic RINSE identity, but that identity never replaces the source record identity.

This preserves the RINSE parent invariant:

> **Meaning may change. Trace must not.**

## Authority split

The source record may prove that evidence was durably recorded in the pinned local/test LiminalDB consumer.

It does not prove:

- the underlying real-world outcome is true;
- production persistence is authorized;
- a RINSE interpretation may execute;
- the source trace may be rewritten.

The reflection is intentionally bounded:

```text
status = SUPPORTED_WITH_LIMITS
graph verdict = ACCEPT_WITH_LIMITS
authority = REFLECTION_ONLY
truth_authorized = false
execution_authorized = false
candidate execution_allowed = false
```

## Semantic validation beyond hashes

The RINSE consumer validates both exact bytes and semantic authority fields.

SYSTEM-006 includes a discriminator where the original source event is changed from:

```text
durable_memory = false
```

to:

```text
durable_memory = true
```

and the durable source-event digest is recomputed.

The bundle is therefore byte/digest-consistent but semantically incompatible with the SYSTEM-005 source contract.

RINSE must still reject it.

This proves:

```text
hash-consistent
≠
contract-consistent
```

## Time coordinates

The durable source carries:

```text
valid_time_ms
transaction_time_ms
```

RINSE maps them to:

```text
valid_time.from ← valid_time_ms
recorded_time   ← transaction_time_ms
reviewed_time   ← explicit downstream review time
```

Review time remains a distinct downstream fact and may not precede durable recorded time.

## Independent proof sequence

The ContractGraph-QA gate will:

1. rebuild real upstream provider evidence;
2. run canonical ProofPath native verification;
3. rebuild the SYSTEM-004 AuditEvent;
4. run canonical LiminalDB artifact validation;
5. create a separate local/test storage admission;
6. persist the exact event through canonical LiminalDB `61b02fc...`;
7. reopen in a new process and recover exact durable bytes;
8. record the durable summary and source byte digests;
9. check out exact canonical RINSE `3be0d2c...`;
10. run its durable-source adapter and existing reflection core;
11. verify source bytes are unchanged before/after;
12. verify source-trace ID contains the exact durable record hash;
13. verify deterministic reflection ID/digest and `REFLECTION_ONLY` authority;
14. run the semantic authority-escalation negative control with recomputed digest;
15. run native LTP strict/replay;
16. evaluate FCRP-SYSTEM-006 and upload immutable evidence.

## Non-goals

A green SYSTEM-006 does not establish:

- production persistence authorization;
- source write-back from RINSE;
- executable Kairos transitions;
- truth of the underlying incident;
- a production policy for reflection promotion;
- distributed replication;
- downstream publication authority.

## Expected system state after PASS

```text
LiminalDB durable evidence state
        ↓
immutable RINSE source trace
        ↓
canonical deterministic reflection
        ↓
REFLECTION_ONLY
```

The next system gate may test the return path from bounded interpretation into RESONANCE operational memory without granting authority or rewriting durable history.
