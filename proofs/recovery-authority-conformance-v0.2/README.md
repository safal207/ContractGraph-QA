# Recovery Authority Conformance Vector v0.2

v0.2 extends the frozen v0.1 compatibility surface with **AutoGen core 0.7.5** while preserving every previous PASS/UNTESTED row unchanged.

The profile remains a vector. There is deliberately no scalar “safe framework” verdict.

## Normative rows

| External state | Required decision | Automatic redispatch? |
|---|---|---|
| `CONFIRMED` matching receipt | `return_prior` | No |
| `UNKNOWN` / unavailable read-back | `fail_closed_unknown` | No |
| `MISMATCH` target/result/intent | `fail_closed_mismatch` | No |
| `NOT_EXECUTED` with authoritative proof | `fresh_authorization_required` | Only after a new authorization decision |

A consumed permit is never reusable.

## v0.2 evidence vector

| Runtime surface | CONFIRMED | UNKNOWN | MISMATCH | NOT_EXECUTED |
|---|---|---|---|---|
| CrewAI `1.15.21` synchronous `ToolUsage._use` retry | **PASS** | **UNTESTED** | **UNTESTED** | **UNTESTED** |
| LangGraph `1.2.11` + SQLite `3.1.1` fresh-process `b1` recovery | **PASS** | **PASS** | **PASS** | **UNTESTED** |
| AutoGen core `0.7.5` fresh-process runtime save/load | **PASS** | **PASS** | **PASS** | **PASS** |

Aggregate counts: **8 PASS / 4 UNTESTED / 0 FAIL / 0 UNSUPPORTED**.

`scalar_verdict` remains `null`.

## AutoGen addition

The AutoGen rows come from the merged runtime proof #187, not from the older saved-state host-capability benchmark #81.

The runtime proof uses:

`SingleThreadedAgentRuntime.save_state() -> JSON -> fresh OS process -> load_state()`

and structurally restricts persisted agent state to `{schema, action_id, intent_hash, target}`. Permit IDs and permit-consumption authority remain in caller-owned external storage.

The `NOT_EXECUTED` row demonstrates the strongest authority distinction in the current matrix: the old generation-1 permit stays consumed, recovery records `fresh_authorization_required`, and a distinct generation-2 permit authorizes the single recovery effect.

## Immutable evidence

`verify_profile.py` reads all evidence from exact historical merge commits and verifies each report's Git blob identity before checking the semantics behind a PASS row.

Sources:

- framework-neutral contract #173;
- CrewAI runtime #175;
- LangGraph b1 runtime #179;
- LangGraph receipt visibility #183;
- AutoGen runtime state authority #187.

The v0.1 profile directory remains unchanged and independently reproducible.

## Reproduce

CI checks out full history and runs:

```bash
python proofs/recovery-authority-conformance-v0.2/verify_profile.py
```

Expected summary:

```json
{"profile_verified":true,"runtime_rows":{"FAIL":0,"PASS":8,"UNSUPPORTED":0,"UNTESTED":4},"scalar_verdict":null,"schema":"contractgraph.recovery-authority-conformance.v0.2","source_blobs_verified":5}
```

## Claim ceiling

This profile reports bounded evidence at named runtime surfaces. It is not a framework ranking, certification, global exactly-once guarantee, distributed-consensus result, or claim that UNTESTED rows are safe.

Tracking issue: [#188](https://github.com/safal207/ContractGraph-QA/issues/188).
