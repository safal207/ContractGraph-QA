# Execution Binding Invariant

Status: design contract / executable reference

This note defines a preventive contract boundary for decisions that authorize a later side effect but do **not** themselves own the atomic execution step.

The motivating shape is:

```text
decision produced
      ↓
execution_binding = external
      ↓
caller may execute a side effect
```

The decision can be safe for immediate synchronous, undurable use while becoming insufficient once it escapes the call stack that produced it.

## Normative invariant

**EB-1 — external decisions do not survive a lifetime boundary by themselves.**

If `execution_binding == external` and the decision is cached, deferred, persisted, queued, transported, or reused by retry/replay, the decision MUST NOT directly authorize dispatch. The adapter MUST rebind or revalidate the authority against the execution context at the dispatch seam.

**EB-2 — consumable authority requires atomic consumption.**

If the underlying grant is single-use or otherwise consumable, revalidation alone is insufficient. Consumption and dispatch MUST share one atomic boundary (or an equivalent mechanism that closes the check-then-act race).

**EB-3 — synchronous undurable use does not require invented machinery.**

For a reusable, non-consumable decision used immediately in the same synchronous call stack, no durable consumption mechanism is required solely to satisfy this contract.

## Decision lifetime matrix

| Use mode | Escapes producing call stack? | Rebind/revalidate at dispatch? | Atomic consume required? | Direct use of external decision |
| --- | --- | --- | --- | --- |
| Immediate synchronous, reusable authority | No | Not required by EB-1 | No | Allowed |
| Immediate synchronous, consumable authority | No | Not required by EB-1 | Yes | Only with atomic consume |
| Cached | Yes | Yes | If consumable | Block without rebind |
| Deferred | Yes | Yes | If consumable | Block without rebind |
| Persisted | Yes | Yes | If consumable | Block without rebind |
| Queued | Yes | Yes | If consumable | Block without rebind |
| Transported across process/service boundary | Yes | Yes | If consumable | Block without rebind |
| Retry / replay | Yes | Yes | If consumable | Block without rebind; single-use authority also needs atomic consume |

## Why `execution_binding` matters

`execution_binding` describes who owns the final check-to-side-effect boundary.

- `internal`: the component that produced the authorization also owns the execution seam strongly enough to bind the check to the action.
- `external`: the producer returns a decision or grant, while another component performs the side effect later or separately.

`external` is therefore a disclosure, not a vulnerability verdict. It tells an adapter author where the proof stops.

## Minimal state-transition form

```text
actor
  → decision(check_context)
  → [optional lifetime boundary]
  → dispatch(current_context)
  → side effect
```

For `execution_binding = external`:

```text
lifetime boundary crossed
        ⇒
rebind(current_context) required at dispatch
```

For consumable authority:

```text
rebind(current_context)
        +
consume(authority) ⟂ dispatch(side_effect)
        ↓
     atomic seam
```

The symbol `⟂` here means the consume and dispatch operations must not be separable by an observable race window.

## Executable reference

`test/ExecutionBindingInvariant.t.sol` encodes this contract as a small Foundry corpus. It deliberately models the boundary rather than a provider-specific vulnerability:

- the pure lifetime matrix covers reusable decisions under EB-1 and EB-3;
- same-stack synchronous reusable decisions remain valid;
- every escaped external decision fails closed without dispatch-time rebinding;
- rebound reusable decisions may proceed;
- EB-2 uses a stateful single-use authority instead of a caller assertion;
- `consumeAndDispatch` records consumption before its modeled side effect in the
  same transaction, and the corpus proves the first dispatch succeeds while a
  second dispatch with the same authority fails;
- an escaped single-use authority cannot be consumed before dispatch-time
  rebinding succeeds.

The reference proves those state-machine properties for the executable corpus.
It does not prove atomicity for an adapter or provider that has a different
transaction, storage, process, or network boundary.

This keeps the invariant reusable across guardrails, agent payments, escrow release/refund flows, approval systems, queues, retries, and other stateful authorization paths.
