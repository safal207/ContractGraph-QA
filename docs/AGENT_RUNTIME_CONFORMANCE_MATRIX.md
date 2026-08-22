# Agent Runtime Conformance Matrix v0.1

`Witness Projection Conformance v0.1` started as an eight-check semantic test. The runtime matrix adds a second layer: it separates **projection correctness** from the **storage/evidence guarantees** required to make that projection trustworthy in a real agent runtime.

Scores and axis values are **boundary-specific**. They are not overall framework rankings.

Machine-readable source of truth:

```text
benchmarks/agent-runtime-conformance-matrix-v0.1/matrix.json
```

Validator:

```text
contractgraph_qa/runtime_conformance_matrix.py
```

## Seven-axis matrix

Legend:

- `PASS` — measured boundary satisfies the capability.
- `FAIL` — measured boundary contradicts the capability.
- `ADAPTER` — the framework can host the capability, but adapter policy must enforce it.
- `N/M` — not measured by the pinned benchmark.
- destructive mutations are shown as `PRESENT`, `ABSENT`, or `N/M` rather than as a capability pass/fail.

| Runtime | Projection | Replay | Explicit absence | Deadline binding | Persistence | Append-only evidence | Destructive mutations |
|---|---:|---:|---:|---:|---:|---:|---:|
| CrewAI | **6/8 FAIL** | PASS | **FAIL** | **FAIL** | N/M | N/M | N/M |
| LangGraph | **8/8 PASS** | PASS | PASS | PASS | PASS | **ADAPTER** | N/M |
| AutoGen | **8/8 PASS** | PASS | PASS | PASS | PASS | **ADAPTER** | N/M |
| Microsoft Agent Framework | **8/8 PASS** | PASS | PASS | PASS | PASS | **ADAPTER** | N/M |
| OpenAI Agents SDK | **8/8 PASS** | PASS | PASS | PASS | PASS | **FAIL** | **PRESENT** (`pop_item`, `clear_session`) |

The matrix exposes an important distinction:

```text
projection conformance != persistence != append-only evidence
```

A runtime may replay the frozen projection perfectly while its underlying storage still permits evidence deletion or replacement.

## Pinned sources and measured boundaries

| Runtime | Pinned source | Boundary |
|---|---|---|
| CrewAI | `crewAIInc/crewAI@f4731f5025f861c78e3af0487cc80bf5e7c64782` | native tool-event evidence vocabulary |
| LangGraph | `langchain-ai/langgraph@f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f` | hosted StateGraph/checkpoint state |
| AutoGen | `microsoft/autogen@027ecf0a379bcc1d09956d46d12d44a3ad9cee14` | hosted JSON-serializable `save_state()/load_state()` |
| Microsoft Agent Framework | `microsoft/agent-framework@d9d3fb6252f7ae9e7f8104edce7266f0782a813c` | native `WorkflowCheckpoint.state` hosting domain witnesses |
| OpenAI Agents SDK | `openai/openai-agents-python@7f7a44f8dc0650296bd5ab6c745c9bcbaa6ac3b7` | restricted hosted witness envelope over `SQLiteSession` JSON items |

## Axis definitions

### Projection

Whether the measured adapter/boundary passes the eight checks in `witness-projection-conformance/v0.1`.

The eight checks are:

1. deterministic across evaluator time;
2. explicit absence enables transition;
3. replay stability;
4. prefix stability;
5. non-monotone state over monotone evidence;
6. deadline bound to evidence;
7. missing deadline fails closed;
8. projection does not mutate evidence.

### Replay

Whether the same recorded witness sequence produces the same projected outcome when evaluated again.

### Explicit absence

Whether a negative observation such as “no response in this inspected window” can exist as explicit evidence rather than being inferred from the evaluator's current clock.

### Deadline binding

Whether the deadline that changes the outcome is carried by evidence rather than read from ambient configuration during replay.

### Persistence

Whether the measured boundary provides a concrete persistence/restore path capable of carrying the witness contract. `N/M` means the benchmark did not test that question; it does not mean the runtime lacks persistence features elsewhere.

### Append-only evidence

Whether the evidence path itself is protected against destructive history changes.

`ADAPTER` means the measured framework substrate can host append-only witness semantics, but the guarantee comes from the adapter/reducer policy rather than from a proven immutable native storage contract.

### Destructive mutations

Whether the measured native persistence API exposes operations that can remove evidence history. For OpenAI Agents SDK the pinned `Session` protocol exposes `pop_item()` and `clear_session()`, so this axis is explicitly `PRESENT` even though hosted projection remains 8/8.

## Machine-checking discipline

`tools/tests/test_agent_runtime_conformance_matrix.py` cross-checks every runtime row against its source-pinned benchmark `result.json`:

- repository and commit pins must match;
- projection pass/fail score must match the eight underlying checks;
- replay, explicit-absence, and deadline-binding axes must agree with the benchmark result;
- an 8/8 projection cannot hide an independently observed storage mutation surface;
- `appendOnly=PASS` cannot coexist with known destructive mutations.

This makes the comparison table derived evidence rather than hand-maintained prose.

## Portable runtime profiles

External runtimes do not need to edit the central matrix to express a result. `Agent Runtime Conformance Profile v0.1` defines a portable single-runtime document with the same seven axes, an exact source pin, evidence references, and an explicit claim boundary.

Validate one profile with:

```bash
cgqa runtime-conformance-profile --input profile.json
```

Schema:

```text
contractgraph_qa/schemas/agent-runtime-conformance-profile-v0.1.schema.json
```

Canonical example:

```text
examples/openai-agents-runtime-conformance-profile-v0.1.json
```

See `docs/AGENT_RUNTIME_CONFORMANCE_PROFILE.md` for the submission contract and the distinction between `profileValid` and `projectionConformant`.

## Current interpretation

The first five runtimes already show three distinct architectural profiles:

1. **insufficient native evidence vocabulary** — CrewAI at the measured tool-event boundary cannot encode explicit absence/deadline evidence;
2. **conformant hosted state substrate** — LangGraph, AutoGen, and Microsoft Agent Framework can carry the complete contract, while append-only behavior remains an adapter responsibility;
3. **conformant projection over mutable persistence** — OpenAI Agents SDK can carry/replay the contract through `SQLiteSession`, but the native session API permits destructive history mutation.

The useful question is therefore no longer just “does this framework score 8/8?” It is:

> Which guarantees come from the runtime itself, which come from the adapter, and which remain unmeasured?

That is the claim boundary of Agent Runtime Conformance Matrix v0.1.
