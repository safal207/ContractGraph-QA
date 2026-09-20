# LangGraph #8039 ordering barrier — RED→GREEN v0.1

This artifact isolates one mechanism-level invariant from
[langchain-ai/langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039):

> An ordinary pending-write future must enter the checkpoint barrier, and that
> same barrier must be drained before the actual superseding saver `put` begins.

It is intentionally narrower than the existing
`langgraph-recovery-safety-v0.1` benchmark.

## Why this exists

The existing crash/recovery fixtures in this repository and in the #8039 thread
show the externally visible consequence of the race: forced persistence
interleavings can change whether recovery replays durable writes or re-executes
a node.

Those fixtures are valuable acceptance evidence, but the forced ordering uses
delays. This artifact removes scheduler timing from the regression detector and
checks the ordering mechanism directly.

## RED→GREEN subjects

The CI workflow pins two exact source subjects:

| Subject | Pin | Expected |
|---|---|---|
| upstream `main` at review time | `langchain-ai/langgraph@aa742fb31e2827d569b843e3600aeda2e0528e4b` | **RED** |
| closed/unmerged #8055 head | `i-anubhav-anand/langgraph@1c2cf39b406f9207ab96b8ffca5e96abf75a4920` | **GREEN** |

RED is an expected observation for the unfixed subject, not a failing workflow.
The job fails only if the observed verdict differs from the pinned expectation.

## What the probe does

`tools/langgraph_ordering_barrier_probe.py`:

1. creates a minimal `SyncPregelLoop` instance without running a graph;
2. calls the real `PregelLoop.put_writes()` with an ordinary,
   non-`DeltaChannel` write;
3. captures the sentinel future returned by `submit()`;
4. checks whether that future is registered in a write-future barrier;
5. verifies that the *same barrier attribute* is referenced by both sync and
   async `_checkpointer_put_after_previous`;
6. executes those real drain methods with instrumented stdlib
   `wait`/`gather` and saver `put`/`aput` calls to prove the causal order:

```text
ordinary put_writes future registered
              |
              v
checkpoint barrier drain
              |
              v
actual saver put / aput
```

No sleeps, retry loops, SIGKILL, CPU-count assumptions, or effect-count
probabilities are used.

## Run

Against any installed LangGraph source tree:

```bash
python -m tools.langgraph_ordering_barrier_probe
```

To make a subject expectation executable:

```bash
python -m tools.langgraph_ordering_barrier_probe --expect red
python -m tools.langgraph_ordering_barrier_probe --expect green
```

Machine-readable output:

```bash
python -m tools.langgraph_ordering_barrier_probe \
  --expect red \
  --json artifacts/langgraph-ordering-barrier/result.json
```

## Claim boundary

A GREEN result means only that this persistence-ordering mechanism is present:
ordinary pending writes are barriered before the actual superseding saver
`put`.

It **does not** establish exactly-once external effects. A process can still
crash after an external system accepts an action but before the runtime
durably records the corresponding local receipt. That is the separate
side-effect identity/reconciliation boundary exercised by the existing
recovery-safety and receiver-control artifacts.
