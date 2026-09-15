# LangGraph recovery identity / authority adapter v0.1

This proof binds the framework-neutral identity/authority contract to a **real pinned LangGraph SQLite checkpoint/resume path**.

## Runtime pins

The pins match the immutable `mstevens843/crashpoint@606893ebb353df5dab3ac68738051eb5fbb7286e` lockfile used as the external reference environment:

- `langgraph==1.2.11`
- `langgraph-checkpoint==4.2.0`
- `langgraph-checkpoint-sqlite==3.1.1`

## Recovery boundary

The graph has two nodes:

`prepare(action_id) -> effect(action_id)`

`prepare` exists specifically so LangGraph durably checkpoints the stable `action_id` before the side-effecting node begins.

The first process then:

1. restores the same `action_id` into `effect`;
2. commits one external SQLite effect;
3. exits abruptly with code `79` before `effect` returns;
4. therefore leaves the effect node incomplete in the LangGraph checkpoint.

A fresh process recompiles the graph against the same checkpoint DB and calls `invoke(None, ...)`, causing recovery to re-enter the incomplete effect node.

## A/B

### Baseline

No external reconciliation is performed.

Expected recovery sequence:

`subject: effect_enter -> dispatch -> abrupt exit`

then

`recovery: effect_enter -> dispatch`

Expected external effect count: **2**.

Verdict: `DUPLICATED_ON_RECOVERY`.

### Guarded

Before the first dispatch a one-use permit is issued outside LangGraph runtime state. The first effect transaction atomically:

- consumes the permit;
- commits the external effect;
- writes a receipt keyed by the stable `action_id`.

On recovery, the effect node is still re-entered, but it performs authoritative receipt read-back **before** considering dispatch. A matching committed receipt returns the prior result.

Expected recovery sequence:

`subject: effect_enter -> dispatch -> abrupt exit`

then

`recovery: effect_enter -> return_prior`

Expected external effect count: **1**.

Verdict: `RECONCILED_NO_DUPLICATE`.

## Invariant

> Restored `action_id` identifies the recovering logical action; it does not grant fresh execution authority.

The safe decision order is:

`stable action identity -> external receipt/read-back -> authority decision -> optional dispatch`

A consumed permit is not reused. An `UNKNOWN` target state is not permission to redispatch.

## Claim ceiling

A PASS establishes only the behavior of this pinned local LangGraph SQLite checkpoint/resume fixture. It does **not** establish:

- LangGraph Cloud heartbeat/sweeper behavior;
- safety for every checkpointer;
- distributed-worker race safety;
- a LangGraph framework fix;
- global exactly-once side-effect execution.

Related evidence chain:

`#171 external CrewAI admission -> #173 identity != authority contract -> #175 real CrewAI runtime proof -> #180 LangGraph recovery adapter`

Files:

- `run_experiment.py` — deterministic A/B harness;
- `report.json` — committed machine-readable result after hosted execution;
- `.github/workflows/langgraph-identity-authority-adapter.yml` — pinned hosted verifier.
