# Execution receipt durability v0.1

**System case:** \`EXECUTION-RECEIPT-DURABILITY-001\`

This proof moves the execution-receipt contract across a real OS-process crash boundary.

## Core sequence

\`\`\`text
Aegisora ALLOW
    ↓
durable SQLite PENDING
    ↓
fresh process independently re-reads PENDING
    ↓
provider attempt
    ↓
optional external effect
    ↓
SIGKILL before local TERMINAL
    ↓
fresh recovery process
    ↓
authoritative receiver readback
    ↓
bounded reconciliation
\`\`\`

The tested runtime subject is:

\`aegisora-ai/aegisora@2bac618215671f6f0ac8ebddf169830d4fc0f9b3\`

No Aegisora source file is modified.

## Storage boundary

Two separate SQLite databases are used:

1. **receipt DB**
   - WAL mode;
   - \`synchronous=FULL\`;
   - PENDING + reconciliation records;
   - SHA-256 chained records.

2. **receiver DB**
   - separate WAL database;
   - provider attempt ledger;
   - external effect ledger.

The proof is scoped to **process SIGKILL**, not host/power-loss durability.

## Pre-dispatch durability condition

At the enterprise audit \`ALLOW\` callback, before provider dispatch:

1. PENDING is committed;
2. WAL is checkpointed;
3. a separate Python process reopens the DB;
4. the process recomputes the record SHA-256;
5. only after that fresh read succeeds may the provider be invoked.

Required PENDING semantics:

\`\`\`text
record_kind = PENDING
observation_availability = NOT_READ_BACK
external_outcome = INDETERMINATE
continuity = IN_FLIGHT
\`\`\`

PENDING is not execution truth.

## Crash cases

### A. effect_then_crash

\`\`\`text
PENDING durable
provider attempt = 1
receiver effect = 1
fresh receiver process confirms effect
SIGKILL before local terminal
\`\`\`

Fresh recovery performs FULL receiver readback.

Required:

\`\`\`text
ONE_EFFECT_MATCHING
effect_count = 1
continuity = FINALIZE_EXISTING
decision = FINALIZE_EXISTING_NO_REDISPATCH
provider attempts remain 1
effects remain 1
\`\`\`

### B. crash_before_effect

\`\`\`text
PENDING durable
provider attempt = 1
SIGKILL before receiver effect
\`\`\`

Fresh FULL readback establishes zero effects.

Required:

\`\`\`text
NO_EFFECT
effect_count = 0
continuity = FRESH_AUTHORIZATION_REQUIRED
decision = NO_REDISPATCH_FRESH_AUTHORIZATION_REQUIRED
provider attempts remain 1
effects remain 0
\`\`\`

Verified absence does **not** itself execute the retry.

### C. unavailable_readback

The fixture intentionally records and independently confirms one receiver effect before SIGKILL.

The first recovery is denied access to readback semantics:

\`\`\`text
availability = UNAVAILABLE
external_outcome = INDETERMINATE
effect_count = null
continuity = REVALIDATE
decision = HOLD_REVALIDATE_NO_REDISPATCH
\`\`\`

The underlying fixture effect is deliberately not used by that recovery decision.

A later fresh recovery receives FULL readback and resolves the same PENDING action:

\`\`\`text
ONE_EFFECT_MATCHING
effect_count = 1
continuity = FINALIZE_EXISTING
provider attempts remain 1
effects remain 1
\`\`\`

This is the critical anti-inference case:

> hidden/unavailable evidence is not evidence of no effect.

## Record model

The durable receipt database retains:

\`\`\`text
PENDING
  action_id
  target
  payload_digest
  trace_id
  decision_id
  execution_id
  evidence_id

RECONCILIATION
  observation_availability
  external_outcome
  externally_verified
  effect_count
  continuity
  recovery_decision
\`\`\`

All records are chained with:

\`previous_record_sha256 -> record_sha256\`

## Independent verification

The hosted workflow preserves the actual SQLite databases.

A separate verifier:

- runs SQLite \`integrity_check\`;
- recomputes all receipt/reconciliation hashes;
- verifies the hash chain;
- checks fresh-process PENDING verification;
- checks receiver attempt/effect cardinality;
- proves every recovery leaves attempt count at exactly one;
- verifies UNAVAILABLE never leaks the known fixture effect into the decision;
- verifies later FULL readback can resolve the same action.

## Claim ceiling

This proof does **not** establish:

- host or power-loss durability;
- distributed consensus;
- Byzantine receiver correctness;
- production provider behavior;
- exactly-once external effects;
- recipient identity;
- payment/settlement binding.

The receiver DB is authoritative only for this harmless local fixture.

## Next boundary

The next meaningful layer is not another retry adapter.

It is to project this durable crash/recovery evidence into the canonical Evidence Plane:

\`\`\`text
durable PENDING
+ authoritative readback
+ reconciliation
        ↓
Canonical Evidence Envelope
        ↓
LiminalDB continuity
XTDB knowledge history
Neo4j explanation
\`\`\`
