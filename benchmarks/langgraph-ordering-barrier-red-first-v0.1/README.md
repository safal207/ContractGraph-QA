# LangGraph #8039 — invariant-shaped RED→GREEN guard

This artifact isolates a bounded invariant from
[langchain-ai/langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039):

> An ordinary write must be drained before actual superseding saver `put` / `aput` entry.

The directory is retained for existing links; the revised JSON schema is
`cgqa.langgraph.ordering-barrier-red-first/v0.2`.

## Two separate axes

**Ordering** is the top-level RED/GREEN verdict. Only the observed sync and async
saver-entry checks contribute. `ordinary_future_registered`,
`registered_in_same_sync_and_async_barrier`, and barrier names are diagnostics.
Neither a particular attribute nor a `wait` / `gather` event label is required
for GREEN. The probe does not choose or populate a barrier based on source text.

**Failed-write propagation** is a separate result. An already-failed ordinary
write must propagate its *original exception object* before the checkpoint
helper enters `put` / `aput`. A successful wait alone is not success on this axis.
The async API is a control; all four cases use `durability="sync"`.

This follows [tonydzi's independent pin verification and detector caveat](https://github.com/langchain-ai/langgraph/issues/8039#issuecomment-5753330889)
and [mstevens843's sync failure-propagation report](https://github.com/langchain-ai/langgraph/issues/8039#issuecomment-5771584655).
The latter's [pinned correction](https://github.com/mstevens843/langgraph/commit/fc0e1c9ffdf92bc5bfd17811b3543fefd475d267)
adds result retrieval after the sync wait; its parent is the existing #8055 pin.
These links attribute prior work, not a claim that this probe reproduces the
entire graph-level test suite in that patch.

## Exact pinned expectations

The existing workflow and original two subject SHAs are retained. The third
subject adds the failure-propagation correction as a positive control.

| Subject | Full SHA | Ordering sync / async | Failed write sync / async |
|---|---|---|---|
| `langchain-ai/langgraph` (historical main) | `aa742fb31e2827d569b843e3600aeda2e0528e4b` | RED / RED | RED / RED |
| `i-anubhav-anand/langgraph` (#8055 head) | `1c2cf39b406f9207ab96b8ffca5e96abf75a4920` | GREEN / GREEN | RED / GREEN |
| `mstevens843/langgraph` (follow-up) | `fc0e1c9ffdf92bc5bfd17811b3543fefd475d267` | GREEN / GREEN | GREEN / GREEN |

**Ordering GREEN on #8055 must not be described as failure-propagation GREEN.**
These are source pins, not claims about a current release or whether a fix has
landed upstream. CI verifies the checkout SHA and byte-compares the installed
`_loop.py` with the pinned source. Transitive dependencies are resolved by the
existing pip workflow; this is not a fully locked dependency environment.

Expected RED is an observation, not a failing workflow. Each ordering API path
and each failure-propagation control must match its explicit expectation; a
partial RED or a harness ERROR cannot satisfy an expected two-path RED.

## How the probe works

`tools/langgraph_ordering_barrier_probe.py` creates minimal loop objects and calls
the production `put_writes()` and `_checkpointer_put_after_previous()` methods.
It submits one ordinary non-`DeltaChannel` write through a real thread-executor
future (sync) or real asyncio task (async), retaining the exact object returned
to `put_writes`. The subject itself decides how to retain or await that object.
No future is injected into a discovered barrier attribute.

For the ordering cases the background saver write is held by an event. Observers
release it only when the subject requests a wait on that exact future/task,
then delegate to the real stdlib wait, gather, result, or await operation.
The recording saver snapshots write completion and future terminal state **at
actual `put` / `aput` entry**. An unbarriered subject reaches the saver with an
unfinished write and deterministically goes RED. Cleanup releases it only after
the entry snapshot. A sync inline write also passes without registration.

For failure cases the real submitted future/task is allowed to fail *before*
the checkpoint helper is invoked. The test does not retrieve its result on the
subject's behalf. GREEN requires both original-exception propagation and zero
superseding saver entries. Exceptions read during cleanup cannot satisfy this.

No sleeps, retries, SIGKILL, host-speed assumptions, or probabilistic effect counts
are used. Watchdogs bound hangs; a timeout, unsupported fixture, or unexpected
exception produces `ERROR` / exit 2, never an accepted RED.

The setup is an adapter for the pinned loop interfaces and instrumented saver
entrypoints, not a universal adapter for every future LangGraph implementation.
The 12 stdlib self-tests cover detector logic, including renamed/different/no
barriers, direct result/await, inline sync writes, unrelated futures, missing
saver calls, swallowed failures, and fail-closed harness/expectation handling.
They are distinct from the real pinned-subject executions.

## Run

Against the installed #8055 source pin:

```bash
python -m unittest discover -s tests -p test_langgraph_ordering_barrier_probe.py -v
python -m tools.langgraph_ordering_barrier_probe \
  --expect green \
  --expect-sync-failure-propagation red \
  --expect-async-failure-propagation green \
  --json artifacts/langgraph-ordering-barrier/pr-8055-head-green.json
```

Use the table's expectations for the other pins. Omit expectation flags for
observation only. The workflow publishes JSON, detector self-test output, and
separate summary rows for each axis, including on expectation mismatch. JSON
records installed loop and probe SHA-256 hashes.

## Claim boundary

Ordering GREEN establishes only the bounded ordinary-write completion-before-
saver-entry invariant observed here. Failed-write propagation GREEN establishes
only the one original-exception / no-saver-entry case per API path.

Neither means disk/fsync durability, general cancellation correctness, every
failure permutation, full-graph behavior, or SIGKILL crash/recovery safety. This
artifact does **not** replace `langgraph-recovery-safety-v0.1`.

It **does not establish exactly-once external effects**. A process can still
crash after an external system accepts an action but before the runtime durably
records the local receipt. External effect identity, receiver deduplication,
and reconciliation remain separate boundaries.
