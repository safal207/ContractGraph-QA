# Fork adapter template

v0.7 connects the authorized fixed-block fork context to the existing parameter/time explorer, state deduplication, invariant checks, deterministic replay, and finding-report workflow.

## Safety boundary

A fork adapter is not permission to test an arbitrary public contract.

Use an adapter only when the target is:

- owned by you;
- explicitly included in a client testing agreement;
- or in scope under a published bug-bounty safe-harbor policy.

The v0.6 authorization preflight remains the outer gate. A concrete adapter should initialize through `_initializeAuthorizedAdapterFromEnv()` and run through the manual `authorized-fork` workflow.

## Adapter lifecycle

```text
scope + authorization
        ↓
fixed-block fork
        ↓
ForkAdapterTemplate
        ↓
_resetTarget()
        ↓
actions + parameter corpus
        ↓
protocol state hash
        ↓
fork provenance binding
        ↓
deduplicating BFS
        ↓
invariant failure
        ↓
minimal replayable path
        ↓
CGQA finding/report
```

## Required adapter hooks

A concrete adapter supplies five pieces.

### 1. Deterministic reset

`_resetTarget()` should reopen the exact authorized fork baseline before each candidate:

```solidity
function _resetTarget() internal override {
    _reopenAuthorizedForkBaseline();
    // Optional in-scope actor/setup logic.
}
```

Do not change the fork block during a search. If a test requires time movement, model it as an explicit action/parameter so the path remains replayable.

### 2. Finite action/parameter corpus

`_stepCase()` maps a bounded corpus to `(action, parameter)` pairs. Keep every case within the written testing scope.

Examples may represent:

- a permitted contract call;
- an amount boundary;
- an actor/role choice;
- a time delta;
- an oracle/governance input when explicitly authorized and locally simulated on the fork.

### 3. Step execution

`_executeStep()` performs exactly one modeled step and returns whether that transition was accepted.

A rejected call is evidence about reachability, not automatically a vulnerability.

### 4. Invariant

`_invariantHolds()` expresses the business/security property that must remain true after every accepted transition.

Good invariants cover properties such as:

- conservation/accounting;
- authorization;
- mutually exclusive terminal states;
- timing/epoch constraints;
- collateralization or share/asset relationships;
- protocol-specific state consistency.

### 5. Complete protocol state hash

`_stateHash()` must include every modeled value that can change future reachability.

The adapter first hashes protocol-specific state and then binds it to fork provenance:

```solidity
bytes32 protocolStateHash = keccak256(
    abi.encode(
        /* future-relevant storage/accounting */
        /* actor/role state */
        /* time/epoch/oracle context */
        /* relevant external dependency state */
    )
);
return _forkAdapterStateHash(protocolStateHash);
```

`_forkAdapterStateHash()` additionally binds:

- authorization `scopeHash`;
- chain ID;
- fixed block number;
- target address;
- target code hash.

An incomplete protocol state hash can make deduplication unsound and hide a reachable path. Review the state hash with the same care as an invariant.

## Copyable skeleton

Start from:

`fork-test/AuthorizedAdapterTemplate.t.sol.example`

Copy it to a `.t.sol` file only after an authorized target and engagement scope exist, then replace every `TODO` before execution.

## Default-CI regression

Default CI does not open an external fork. `test/ForkAdapterTemplate.t.sol` uses a local deterministic fixture to verify that:

- adapter state hashes change when future-relevant protocol state changes;
- fork/scope provenance is included in the adapter hash;
- equivalent states are deduplicated;
- the shortest violating path is preserved;
- replay reproduces the same invariant failure.

## Client adapter review checklist

Before running a real adapter, review:

1. authorization reference and exact target;
2. fixed chain and block;
3. all modeled actors and permissions;
4. every action and parameter case;
5. time/oracle/governance assumptions;
6. state-hash completeness;
7. invariant validity;
8. search depth and transition budgets;
9. replay determinism;
10. finding/report scope wording.

## Non-goals

v0.7 does not claim automatic understanding of an arbitrary protocol, automatic invariant synthesis, or exhaustive formal verification. The adapter is an explicit, reviewable mapping from an authorized protocol surface into ContractGraph-QA's search and evidence model.
