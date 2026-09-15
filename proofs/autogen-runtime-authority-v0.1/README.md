# AutoGen runtime recovery-authority adapter v0.1

**Result: 4/4 PASS.** Hosted CI installed exact `autogen-core==0.7.5`, exercised AutoGen's real runtime state boundary across fresh OS processes, froze the observed machine report, and reproduced it byte-for-byte on the next run.

The tested boundary is:

`SingleThreadedAgentRuntime.save_state() -> JSON -> fresh process -> load_state()`

This proof deliberately does **not** treat the earlier AutoGen saved-state witness benchmark (#81) as authorization evidence. That benchmark established that AutoGen's state boundary can host a frozen witness log. This experiment asks the separate question:

> Can logical action identity survive AutoGen runtime state restoration without restoring execution authority with it?

## Runtime pin

- upstream repository: `microsoft/autogen`;
- source commit: `027ecf0a379bcc1d09956d46d12d44a3ad9cee14`;
- `autogen-core==0.7.5` (the version declared at that commit);
- Python 3.12 in hosted CI.

At the pinned commit, the `Agent` protocol requires JSON-serializable `save_state()` / `load_state()`, and `SingleThreadedAgentRuntime.save_state()` delegates to each instantiated agent before `load_state()` reconstructs registered agent state.

## State boundary

The application-side AutoGen agent persists exactly:

- `action_id`;
- normalized `intent_hash`;
- target identity;
- state schema identifier.

The serialized agent state is structurally asserted to contain only those fields. It carries **no permit ID, no permit-consumption state and no derived “execute again” authority**.

Permits, external effects, receipts and authoritative read-back live in caller-owned SQLite outside AutoGen runtime state.

## Observed conformance rows

Each case runs the subject phase in one OS process, saves AutoGen runtime state to JSON, then creates a fresh process and fresh `SingleThreadedAgentRuntime`, registers a new agent instance, loads the saved state and performs recovery.

| External state | Observed recovery | External effects | Permit behavior | Result |
|---|---|---:|---|---|
| `CONFIRMED` | `dispatch -> return_prior` | `1` | generation 1 consumed once | PASS |
| `UNKNOWN` | `dispatch -> fail_closed_unknown -> return_prior` after the same receipt becomes visible | `1` | generation 1 consumed once; no new permit while unknown | PASS |
| `MISMATCH` | `dispatch -> fail_closed_mismatch` | `1` | generation 1 consumed once | PASS |
| `NOT_EXECUTED` | `dispatch -> fresh_authorization_required -> dispatch` | `1` | generation 1 remains consumed; distinct generation 2 authorizes the recovery dispatch | PASS |

The stable `action_id` survives every fresh-process state restore.

## NOT_EXECUTED discriminator

The `NOT_EXECUTED` row is intentionally stronger than merely retrying with the same key. The subject consumes permit generation 1, but authoritative external evidence proves that no effect occurred. Recovery restores only the action identity, records `fresh_authorization_required`, issues a **different permit generation 2**, and then performs the single external effect.

Both permits show `consume_count = 1`; generation 1 is never reused.

## Evidence

- [`report.json`](./report.json) — frozen hosted result; SHA-256 `568949586f114c055114c4089e7a583f72c90cb9b3f807c831a28461d8b1b56a`.
- [`run_experiment_v2.py`](./run_experiment_v2.py) — executable fresh-process runtime experiment.
- `.github/workflows/autogen-runtime-authority.yml` — installs exact AutoGen runtime, regenerates the report and requires byte-for-byte equality.
- [tracking issue #186](https://github.com/safal207/ContractGraph-QA/issues/186).

The first acquisition attempt used AutoGen's typed `RoutedAgent.message_handler` with a generic mapping response and failed during class decoration because the pinned API requires a recognized return message type. That fixture was removed. The successful proof uses `BaseAgent.on_message_impl` for direct RPC while retaining the same runtime `save_state/load_state` boundary and unchanged authority semantics.

## Claim ceiling

A PASS is an **application-side authority adapter over AutoGen 0.7.5 runtime save/load**. It does not establish that AutoGen itself implements external-effect reconciliation, retry deduplication, crash recovery of runtime internals, or global exactly-once execution.
