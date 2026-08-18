# Gonka → LiminalDB causal bridge

This bridge persists ContractGraph-QA Gonka reconciliation evidence into LiminalDB's native `TrustworthyTransitionLedger`.

It is intentionally a **verification-memory bridge**, not a claim that LiminalDB replaces Gonka's own state, accounting, settlement, or authorization model.

## Mapping

```text
ContractGraph-QA / Gonka                    LiminalDB
────────────────────────────────────────────────────────────────
local verification scope            ->     Authorization
logical_operation_id                ->     transition_id
internal_request_id + winner nonce  ->     Observation (one per execution)
response semantic fidelity          ->     ResponseIntegrity = NOT_EVALUATED
CGQA PASS / FAIL                     ->     CausalAudit = VALID / INVALID
safe next action                     ->     ContinuitySnapshot
completed local protocol effect      ->     side_effect_committed = true
```

Two timeout/retry executions under one logical operation are deliberately emitted as two independent `Observation` records. They are never collapsed into one canonical execution.

## Evidence boundary

For G-002A/G-002B, the bridge does **not** claim that model response content was independently verified. The response-integrity dimension is explicitly `NOT_EVALUATED` until a dedicated content/output fidelity witness exists.

The `Authorization` record represents authorization to execute the **local CGQA verification case** at the pinned test revision and safety scope. It does not represent a Gonka end-user spending or protocol authorization decision.

## Native durability proof

The workflow:

1. hashes the exact `reconciliation.json` bytes;
2. deterministically maps each logical operation into LiminalDB `TransitionEventInput` records;
3. checks out a pinned LiminalDB revision;
4. calls the real `TrustworthyTransitionLedger::append()` API;
5. writes a LiminalDB snapshot;
6. closes the ledger;
7. reopens it and performs full replay verification;
8. requires the recovered projections, event count, and chain head to match exactly;
9. emits `liminaldb-bridge-receipt.json` and preserves the tiny WAL/snapshot ledger in the evidence artifact.

Current pinned LiminalDB revision:

`0cd6e77d52787bb36a97b75ba1a37cb027268eb3`

No network database, cloud credential, or external mutation is required. The bridge remains local-first and safe for CI.

## Why this matters

The Gonka benchmark can now preserve causal continuity beyond one test process:

```text
logical operation
  -> transport ambiguity
  -> execution A
  -> execution B
  -> accounting reconciliation
  -> LiminalDB durable causal projection
  -> restart / replay
  -> future money + settlement reconciliation
```

This is the memory boundary between ContractGraph-QA's executable verification and later recovery, comparison, audit, and settlement reasoning.
