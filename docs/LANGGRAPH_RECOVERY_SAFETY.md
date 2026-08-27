# LangGraph recovery-safety benchmark

This benchmark turns the crash/recovery race reported in [`langchain-ai/langgraph#8039`](https://github.com/langchain-ai/langgraph/issues/8039) into an executable RS1–RS3 assertion layer.

It complements the existing LangGraph checkpoint/state conformance benchmark. The earlier benchmark proves a narrower positive result: generic LangGraph state/checkpoint primitives can carry an explicit append-only witness sequence without consulting ambient wall-clock time. It explicitly does **not** prove equivalent durability across checkpointers or exactly-once external effects.

Recovery Safety v0.1 measures that missing layer.

## Pinned property

Property source:

```text
vasilisnasopoulos/recovery-safety-property
22e34841226c41d80c8646b33f1439a87e8549af
CC BY 4.0
```

The mapped properties are:

- **RS1 — Input determinism:** equal durably received inputs yield equal observable state after recovery;
- **RS2 — Crash independence:** recovery depends on what was durably received, not when the crash occurred;
- **RS3 — At-most-once identity:** each externally visible logical action has a stable identity and no identity is admitted more than once across crash → resume.

RS1 and RS2 can be tested at the runtime boundary. RS3 crosses a system boundary: a protocol can derive a stable identity, but the external receiver must honour it.

## Runtime mapping

For this bounded fixture:

```text
received[n]
= explicit graph input durably supplied before worker execution

logical action plan
= ordered canonical actions declared before the fault experiment

State(n)
= recovered graph state + worker attempt counts + externally admitted action counts
```

A pair is comparable only when all three fixture bindings match:

```text
received_digest
+ logical_action_set_digest
+ crash_boundary
```

Derived checkpointer outcome records are intentionally not promoted into new input. Doing that would erase the exact distinction being tested: persisting inputs and re-deriving state versus persisting outcomes whose ordering can disagree with reality.

This is a declared fixture mapping, not a universal interpretation of every LangGraph application.

## Baseline counterexample

The public issue reproduction uses one injected crash boundary:

```text
entry to checkpoint.put where channel_values.sent == 2
```

It then forces the two persistence interleavings:

```text
writes-delay
  3 checkpoint rows
  0 pending-write rows at crash audit
  step2 admitted twice after resume

put-delay
  3 checkpoint rows
  6 pending-write rows at crash audit
  every step admitted once after resume
```

The explicit graph input, ordered semantic actions, and declared crash boundary are equal. Only persistence timing changes. The recovered observable state changes.

Committed machine result:

```text
RS1 FAIL — equal mapped durable inputs produce different observable states
RS2 FAIL — forced persistence timing changes recovery
RS3 FAIL — the stable `step2` fixture-action identity is admitted twice
```

RS2 is the primary runtime-local finding. With the explicit input, ordered
logical-action plan, runtime profile, append receiver, and injected crash boundary
held fixed, changing only the forced persistence interleaving changes the recovered
observable state. This finding requires no cooperating receiver and no assumption
about how an external system interprets idempotency. RS3 remains useful as the
cross-system boundary and receiver control, but a passing dedup control does not
repair or weaken the RS2 failure.

The committed result is reconstructed from the public issue output. ContractGraph-QA adds the semantic identity mapping to the declared actions; it does not claim that the original probe recorded action IDs.

## Stable semantic identity

The live probe maps the issue's `step2` payload to this canonical fixture action:

```json
{
  "kind": "fixture_external_effect",
  "logical_action": "step2",
  "workflow_instance": "langgraph-8039:t1"
}
```

It does not derive identity from checkpoint namespace, runtime position, process ID, attempt number, or wall-clock time.

This matters because recovery bookkeeping is the disputed state in #8039. A safety key derived from that bookkeeping can change after recovery and inherit the failure it is intended to prevent.

Here `logical_action` is the declared effect payload carried across recovery, not a checkpoint namespace, scheduler position, process-local attempt number, or wall-clock value. The observation also retains the issue's human-readable `step` field for trace review.

### Identity-granularity boundary

The v0.1 live fixture's canonical action contains only `kind`, `logical_action`,
and `workflow_instance`. That projection is sufficient for the declared plan of
three fixed actions, but it is not a general idempotency-key design. Two genuinely
distinct effects emitted from the same logical step in the same workflow instance
would receive the same identity if no business-distinguishing fields were added,
and a deduplicating receiver would suppress the second effect.

For a payload-bearing action, the mapping must declare which business-semantic
fields distinguish one intended effect from another and exercise both failure
directions: a retry of the same action must retain its identity, while a distinct
action must receive a different identity. Runtime position, attempt number, PID,
and wall-clock time remain unsuitable discriminators because recovery can change
them. Selecting and validating a production payload-identity policy is outside the
scope of this fixture.

## Observation integrity

Before evaluation, the implementation fails closed unless it can recompute:

- `received_digest` from the explicit input;
- `logical_action_set_digest` from the ordered action plan;
- each `action_id` from its canonical action;
- `recovered_state_digest` from the observable state;
- admission multiplicity as no greater than attempt multiplicity.

Different action plans are not treated as an RS1/RS2 pair merely because their graph inputs happen to match.

## Receiver control

The live probe supports two receiver modes:

```text
append
  every invocation is admitted

dedup
  SQLite receiver table uses action_id as PRIMARY KEY
  INSERT OR IGNORE admits one identity once
```

Attempts and admissions are recorded separately.

Expected forced control:

```text
writes-delay + append
  step2 attempts   = 2
  step2 admissions = 2

writes-delay + dedup
  step2 attempts   = 2
  step2 admissions = 1
```

A passing dedup control does not make RS1 or RS2 pass. It demonstrates the narrower RS3 boundary: runtime re-execution can remain observable while the external receiver prevents a duplicate effect.

## Reproduce locally

POSIX is required because the fault is an actual `SIGKILL`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . \
  "langgraph==1.2.4" \
  "langgraph-checkpoint-sqlite==3.1.0"

mkdir -p artifacts/langgraph-rs

python -m tools.langgraph_recovery_safety_probe \
  writes-delay --receiver append --expect duplicate \
  --json artifacts/langgraph-rs/writes-delay-append.json

python -m tools.langgraph_recovery_safety_probe \
  put-delay --receiver append --expect exactly-once \
  --json artifacts/langgraph-rs/put-delay-append.json

python -m tools.langgraph_recovery_safety_probe \
  writes-delay --receiver dedup --expect deduped-reexecution \
  --json artifacts/langgraph-rs/writes-delay-dedup.json

python -m tools.langgraph_recovery_safety_report \
  artifacts/langgraph-rs/writes-delay-append.json \
  artifacts/langgraph-rs/put-delay-append.json \
  artifacts/langgraph-rs/writes-delay-dedup.json \
  --output artifacts/langgraph-rs/report.json
```

Focused deterministic tests:

```bash
python -m unittest tools.tests.test_langgraph_recovery_safety -v
```

The current suite covers ten positive and negative evaluator cases.

## CI matrix

The dedicated workflow runs:

1. the pinned issue baseline (`langgraph==1.2.4`, SQLite checkpointer `3.1.0`), with exact expected outcomes and byte-for-byte regeneration of the committed report;
2. a publication-time comparison profile (`langgraph==1.2.11`, SQLite checkpointer `3.1.1`), without assuming whether upstream behavior changed.

Each job uploads the three observations and the RS1–RS3 report. Crash-frontier row counts are captured **before** the fresh-process resume, not reconstructed afterward. This keeps historical counterexample evidence separate from later-version observations.

## Claim boundary

A result from this benchmark does not prove:

- production exactly-once semantics;
- physical power-loss durability;
- correctness of every checkpointer backend;
- completeness or authenticity of external effects;
- that a stable ID is honoured by a real payment, email, ticket, or controller receiver;
- equivalence to the unbounded TLA+/TLAPS proof;
- that one passing interleaving establishes RS1 or RS2.

It proves only what the observed traces support under the declared versions, receiver policy, semantic action plan, and injected fault boundary.

## Safety

The probe uses temporary local SQLite databases and local append-only JSONL files. It performs no network call, sends no email, moves no funds, and touches no production system. The child process is intentionally killed and must not be embedded in an application process.
