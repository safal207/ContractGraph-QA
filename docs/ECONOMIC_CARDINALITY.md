# Economic Effect Cardinality

ContractGraph-QA can verify the safety invariant:

> one logical action/effect slot must produce at most one distinct confirmed economic occurrence.

This is the executable form of `CGQ-SAFE-001 — AT_MOST_ONCE_ECONOMIC_EFFECT` and the benchmark case `CGQ-B002 — Replay Without Theft`.

## Why this is different from request deduplication

A repeated API request, webhook, or log line is not itself economic loss. The verifier therefore does **not** count observations. It counts distinct confirmed `occurrenceId` values for each `(actionId, effectKey)` pair.

Examples:

- the same settlement `tx-123` observed by webhook and polling → PASS;
- a retry attempt rejected before settlement → PASS;
- two different settlement IDs for the same release action → FAIL;
- one action legitimately producing a seller payout and a platform fee → PASS when represented by separate `effectKey` values.

## Model fields

Each event declares:

- `eventId` — unique evidence-row identity;
- `actionId` — stable logical business action identity;
- `effectKey` — the economic effect slot being protected;
- `occurrenceId` — identity of the confirmed external or ledger effect, such as transaction hash or settlement ID;
- `applied` — whether the effect actually occurred.

The verifier deduplicates repeated observations that share the same `occurrenceId`.

## Run

```bash
cgqa economic-cardinality --model scenarios/replay-duplicate-economic-effect.json
```

The canonical B002 fixture returns `status=fail` because `release:A` / `escrow-release-settlement` has two distinct applied settlement occurrences.

A failing CLI run exits with the validation exit code. A passing model exits successfully.

## Evidence semantics

The result includes:

- deterministic `modelSha256`;
- number of applied evidence events checked;
- number of `(actionId, effectKey)` pairs checked;
- all violating pairs;
- all distinct occurrence IDs for each violation;
- a deterministic minimal two-event counterexample.

## Claim boundary

The check is exact over the normalized events supplied to it. It does not by itself prove that the source system emitted every relevant settlement, transfer, or ledger event. Source-to-event completeness must be established by capture/provenance controls.
