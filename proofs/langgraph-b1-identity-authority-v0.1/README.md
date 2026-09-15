# LangGraph b1 identity / authority A/B — v0.1

**Result: PASS.** On a real pinned LangGraph SQLite checkpoint/recovery path, the same `b1` crash boundary produces a discriminating A/B result:

- baseline: **2 node entries -> 2 external effects -> `DUPLICATED`**;
- guarded: **2 node entries -> 1 external effect -> `RECONCILED_NO_DUPLICATE`**.

The runtime still re-enters the node after recovery. The guard does not suppress LangGraph recovery. It changes what the re-entered node is authorized to do.

## Runtime pins

| Field | Pin |
|---|---|
| LangGraph | `1.2.11` |
| LangGraph SQLite checkpointer | `3.1.1` |
| Python | `3.12` in hosted CI |
| External comparison repository | `mstevens843/crashpoint@606893ebb353df5dab3ac68738051eb5fbb7286e` |
| External LangGraph adapter blob | `9dea189cae3ebbcc573786c1df878094c61207fd` |
| Boundary | `b1`: effect committed, pending writes not yet persisted |

The external Crashpoint matrix records naive `b1` as 50/50 `duplicated`, while its idempotent and two-phase arms are 50/50 `exactly_once`. This proof does not import Crashpoint code; it uses the published boundary as an independently inspectable comparison point.

## Experiment

Each arm runs in two processes against the same LangGraph checkpoint DB and the same caller-owned external DB.

1. Subject process enters the graph node.
2. The node performs an external effect.
3. A `SqliteSaver.put_writes` wrapper self-SIGKILLs **before** pending writes persist.
4. A fresh recovery process calls `app.invoke(None, same_thread_id, durability="sync")`.
5. LangGraph re-enters the node because the node result was not durably recorded.

### Baseline

The node has no external reconciliation guard.

Observed:

- before recovery: `1` node entry, `1` effect;
- after recovery: `2` node entries, `2` effects;
- decisions: `dispatch -> dispatch`;
- verdict: `DUPLICATED`.

### Guarded

The node derives/restores one stable `action_id` and uses caller-owned SQLite state:

`action_id -> one-use permit -> dispatch -> external receipt`

On recovery re-entry it reads the external receipt **before** considering dispatch.

Observed:

- before recovery: `1` node entry, `1` effect;
- after recovery: `2` node entries, still `1` effect;
- decisions: `dispatch -> return_prior`;
- the same `action_id` appears in both node entries;
- the permit is consumed exactly once and never reused;
- the receipt matches the original target/result;
- verdict: `RECONCILED_NO_DUPLICATE`.

## What this proves

At this pinned local LangGraph `b1` recovery boundary, a recovery/replay can preserve logical action identity without treating recovered runtime state as fresh authority for another side effect.

The executable invariant is:

> Recovery may re-enter the node; re-entry alone must not authorize redispatch.

A matching external receipt converts the second node entry into `return_prior` rather than a second effect.

## Claim ceiling

This proof does **not** establish:

- the exact LangGraph Cloud ~180-second sweeper behavior from issue #7417;
- global exactly-once execution;
- distributed authorization or consensus;
- external target availability or Byzantine correctness;
- safety when the receipt provider is stale, ambiguous, or unavailable;
- that LangGraph itself implements this guard.

The guard is an application-side ContractGraph-QA boundary layered around a real LangGraph recovery path.

## Reproduce

Hosted CI installs the exact runtime pins, regenerates `report.json`, and requires byte-for-byte equality:

```bash
python proofs/langgraph-b1-identity-authority-v0.1/run_ab.py \
  --write-report /tmp/langgraph-b1-report.json

diff -u \
  proofs/langgraph-b1-identity-authority-v0.1/report.json \
  /tmp/langgraph-b1-report.json
```

## Evidence chain

`external Crashpoint b1 evidence -> CrewAI admission/runtime proofs -> identity/authority contract -> LangGraph b1 A/B`

Files:

- [`run_ab.py`](./run_ab.py) — executable A/B harness;
- [`report.json`](./report.json) — frozen machine result;
- [issue #176](https://github.com/safal207/ContractGraph-QA/issues/176) — experiment boundary;
- [issue #177](https://github.com/safal207/ContractGraph-QA/issues/177) — acquisition/freeze record.
