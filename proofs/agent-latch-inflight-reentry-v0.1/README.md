# Agent Latch in-flight re-entry characterization v0.1

This proof tracks the new overlap window surfaced in `langchain-ai/langgraph#7417`: a second dispatch of the same logical action arrives **while the first execution lease is still active**.

It is deliberately separate from ContractGraph-QA PR #179:

- PR #179: external effect happened, process/checkpoint boundary failed, then recovery must reconcile before redispatch.
- This vector: first execution is still active, so a concurrent re-entry must receive **no execution authority**.

## Pinned upstream

- repository: `AaronDai23/agent-latch`
- commit: `2c8b3c64b6c4e8cf3f91899a28251a5867947a57`
- surfaces: `packages/idempotency` and `examples/langgraph`

The verifier clones exactly that commit, runs the idempotency package tests, then runs the LangGraph-shaped dual-dispatch example.

## Required observations

- active lease blocks another worker;
- active lease blocks same-worker re-entry;
- finance mode does not convert an unresolved/expired claim into blind retry authority;
- reconcile hit returns the prior result without a second effect;
- the dual-dispatch example records exactly one external effect;
- concurrent redispatch is denied;
- a later post-commit dispatch is replayed.

## Claim ceiling

This is an **adapter characterization**, not a LangGraph Cloud proof. The upstream example intentionally has no LangGraph dependency.

The following remain UNTESTED here:

- real `@langchain/langgraph` node integration;
- LangGraph Cloud scheduler / `Runs.Sweep()` behavior;
- the reported ~180s production timing window;
- distributed-store failure modes beyond the pinned upstream tests.

Tracking: #197.
