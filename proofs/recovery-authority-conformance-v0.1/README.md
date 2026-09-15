# Recovery Authority Conformance Vector v0.1

This profile compares **bounded recovery / retry authority evidence** across agent runtimes without turning the result into a framework ranking or one scalar safety verdict.

The normative boundary is:

`stable action identity -> external reconciliation -> authority decision -> optional dispatch`

A recovered action identity answers **which logical action is this?** It does not answer **may it execute again?**

## Normative rows

| External state | Required decision | Automatic redispatch? |
|---|---|---|
| `CONFIRMED` matching receipt | `return_prior` | No |
| `UNKNOWN` / unavailable read-back | `fail_closed_unknown` | No |
| `MISMATCH` target/result/intent | `fail_closed_mismatch` | No |
| `NOT_EXECUTED` with authoritative proof | fresh authorization required | Only after a new authorization decision |

A consumed permit is never reusable.

## Current vector

| Runtime surface | CONFIRMED | UNKNOWN | MISMATCH | NOT_EXECUTED |
|---|---|---|---|---|
| CrewAI `1.15.21` synchronous `ToolUsage._use` retry | **PASS** | **UNTESTED** | **UNTESTED** | **UNTESTED** |
| LangGraph `1.2.11` + SQLite `3.1.1` fresh-process `b1` recovery | **PASS** | **PASS** | **PASS** | **UNTESTED** |

`UNTESTED` is intentional evidence, not a failure and not an inherited PASS.

## Immutable evidence pins

The vector does not trust the mutable working-tree copies of predecessor reports. `verify_profile.py` reads each report from its exact merged commit and verifies the Git blob identity before checking semantics.

| Source | Merge commit | Report blob |
|---|---|---|
| Framework-neutral identity/authority contract (#173) | `6d7873c40d792f3ec031b52819c83a246df9b54e` | `2001c3bc97e3cef7cb14e9227b640a4d7457efd8` |
| CrewAI runtime adapter (#175) | `9498b696f095db37406b174a2388349087cdd960` | `2ce696e28857193423a6cf4757246adba4587f9a` |
| LangGraph b1 adapter (#179) | `2a22b82cd02f8a56d7c41d071f618f72a7ed3839` | `94bd3e9ad88ebc69b3f34a065484a0adc4c5a70a` |
| LangGraph receipt visibility (#183) | `bb3aeada02ae392d518f685ebfd2dbfb9b3ac408` | `9b1350d31d223274710a0bd0f0b1d7e7cc7b6e66` |

## What the verifier checks

1. the four immutable report objects exist at the pinned merge commits;
2. their Git blob SHA-1 values match the declared evidence pins;
3. the framework-neutral contract still contains the required recovery cases and unsafe-mutant discrimination;
4. the CrewAI PASS row is supported by two tool entries, one guarded effect, `dispatch -> return_prior`, and a consumed permit;
5. the LangGraph confirmed row is supported by fresh-process node re-entry with one guarded effect and `return_prior`;
6. the LangGraph visibility proof supports `UNKNOWN -> fail_closed_unknown` and target mismatch -> `fail_closed_mismatch` without another effect;
7. every unexercised runtime row remains explicitly `UNTESTED` and carries no evidence pointer;
8. the aggregate remains a vector with `scalar_verdict = null`.

## Reproduce

The CI workflow checks out full history because immutable predecessor commits are part of the evidence boundary:

```bash
python proofs/recovery-authority-conformance-v0.1/verify_profile.py
```

Expected summary at v0.1:

```json
{"profile_verified":true,"runtime_rows":{"FAIL":0,"PASS":4,"UNSUPPORTED":0,"UNTESTED":4},"scalar_verdict":null,"schema":"contractgraph.recovery-authority-conformance.v0.1","source_blobs_verified":4}
```

## Claim ceiling

This profile says only which declared rows have runtime evidence at the named surfaces. It does not establish global exactly-once execution, general framework safety, arbitrary target correctness, distributed consensus, or equivalence between different retry/recovery mechanisms.

Tracking issue: [#184](https://github.com/safal207/ContractGraph-QA/issues/184).
