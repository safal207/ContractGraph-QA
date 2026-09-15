# LangGraph b1 receipt visibility — v0.2

This proof extends the merged LangGraph b1 identity/authority adapter with a narrower question:

> What should recovery do when the external effect may already be committed, but the authoritative receipt is temporarily unavailable or does not match the intended target?

## Runtime pins

- `langgraph==1.2.11`
- `langgraph-checkpoint==4.2.0`
- `langgraph-checkpoint-sqlite==3.1.1`
- crash boundary: `b1_after_effect_before_pending_writes`

Predecessor: `proofs/langgraph-b1-identity-authority-v0.1/`.

## Cases

### CONFIRMED

The original effect commits and its matching receipt is visible during recovery.

Expected:

`dispatch -> return_prior`

Recovery re-enters the node, but effect count stays one.

### UNKNOWN_THEN_CONFIRMED

The original effect commits, but the receipt row is deliberately hidden on the first recovery attempt.

Expected first recovery:

`dispatch -> fail_closed_unknown`

No second effect is allowed and the consumed permit is not refreshed.

The exact same stored receipt is then made visible, simulating delayed read-back visibility without changing receipt bytes.

Expected second recovery:

`... -> return_prior`

The same stable `action_id` is observed on all node entries and effect count remains one.

### TARGET_MISMATCH

The original effect commits, but the visible receipt names a different target.

Expected:

`dispatch -> fail_closed_mismatch`

No redispatch is allowed.

## Invariant

> Missing visibility is not proof of non-execution.

`UNKNOWN` and target mismatch are both non-authorizing states. They cannot be converted into a fresh dispatch merely because LangGraph recovery re-enters the node.

The decision order remains:

`stable action_id -> authoritative read-back -> reconciliation verdict -> optional fresh authority -> dispatch`

## Claim ceiling

A PASS applies only to this pinned local SQLite target/checkpointer fixture. It does not establish:

- correctness for arbitrary eventual-consistency models;
- Byzantine receipt-provider correctness;
- LangGraph Cloud heartbeat/sweeper behavior;
- global exactly-once execution.

Files:

- `run_visibility.py` — executable fresh-process recovery experiment;
- `report.json` — frozen hosted result after acquisition;
- `.github/workflows/langgraph-b1-receipt-visibility.yml` — pinned hosted verification.

Tracking issue: #182.
