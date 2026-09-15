# AutoGen runtime recovery-authority adapter v0.1

This experiment binds the merged recovery-authority contract to AutoGen's real runtime state boundary:

`SingleThreadedAgentRuntime.save_state() -> JSON -> fresh process -> load_state()`

It deliberately does **not** treat the earlier AutoGen saved-state witness benchmark (#81) as authorization evidence. That benchmark established that AutoGen's state boundary can host a frozen witness log. This experiment asks the separate question:

> Can logical action identity survive AutoGen runtime state restoration without restoring execution authority with it?

## Runtime pin

- upstream repository: `microsoft/autogen`;
- source commit: `027ecf0a379bcc1d09956d46d12d44a3ad9cee14`;
- `autogen-core==0.7.5` (the version declared at that commit);
- Python 3.12 in hosted CI.

At the pinned commit, the `Agent` protocol requires JSON-serializable `save_state()` / `load_state()`, and `SingleThreadedAgentRuntime.save_state()` delegates to each instantiated agent before `load_state()` reconstructs registered agent state.

## State boundary

The application-side AutoGen agent persists only:

- `action_id`;
- normalized `intent_hash`;
- target identity;
- state schema identifier.

The serialized agent state is asserted to contain exactly those fields. It carries **no permit ID, no permit-consumption state and no derived “execute again” authority**.

Permits, external effects, receipts and authoritative read-back live in caller-owned SQLite outside AutoGen runtime state.

## Four conformance rows

Each case performs the subject phase in one OS process, saves AutoGen runtime state to JSON, then creates a fresh process and a fresh `SingleThreadedAgentRuntime`, registers a new agent instance, loads the saved state and performs recovery.

### CONFIRMED

The original dispatch consumes permit generation 1, commits one external effect and stores a matching visible receipt, then simulates a lost response.

Recovery restores the same `action_id`, reads the external receipt and returns the prior result.

Expected:

`dispatch -> return_prior`

External effect count remains `1`; permit generation 1 remains consumed exactly once.

### UNKNOWN

The original effect and receipt exist, but receipt visibility is disabled.

First fresh-process recovery:

`dispatch -> fail_closed_unknown`

No second effect and no new permit are allowed.

The exact same receipt is then made visible and another fresh-process restore performs:

`... -> return_prior`

Effect count remains `1` across all three agent entries.

### MISMATCH

The external effect commits, but the visible receipt names another target.

Recovery performs:

`dispatch -> fail_closed_mismatch`

No second effect is emitted and the original permit is not reused.

### NOT_EXECUTED

The subject consumes permit generation 1 but the target fixture records authoritative `NOT_EXECUTED` before any effect occurs.

Recovery restores the same action identity, records `fresh_authorization_required`, issues and consumes **permit generation 2**, then performs exactly one external effect.

The original permit is never reused.

## Evidence acquisition

The first hosted run intentionally has no committed expected `report.json`. It installs exact `autogen-core==0.7.5`, executes all four fresh-process cases and uploads the observed report. Once the runtime result is inspected, that exact report can be frozen and CI tightened to require byte-for-byte reproduction.

## Claim ceiling

A PASS is an **application-side authority adapter over AutoGen 0.7.5 runtime save/load**. It does not establish that AutoGen itself implements external-effect reconciliation, retry deduplication, crash recovery of runtime internals, or global exactly-once execution.

Tracking issue: [#186](https://github.com/safal207/ContractGraph-QA/issues/186).
