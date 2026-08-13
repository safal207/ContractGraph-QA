# Gonka Scenario Matrix v0.1

| ID | Scenario | Expected invariant behavior | Priority |
|---|---|---|---|
| G-001 | Normal inference within valid devshard | Exactly one execution, one usage effect, reconcilable settlement | P0 |
| G-002 | Retry after client/gateway timeout | Same logical operation must not create unintended duplicate billing | P0 |
| G-003 | Duplicate request delivery | Duplicate billable mutation suppressed or explicitly distinguished by protocol identity | P0 |
| G-004 | Settlement retry after ambiguous chain response | Final state contains at most one settlement effect | P0 |
| G-005 | Gateway restart with pending usage | Pending usage recovers without loss or duplication | P0 |
| G-006 | Request at epoch/devshard rotation boundary | Usage attributed to exactly one valid settlement interval | P0 |
| G-007 | Rejected/unauthorized request | No inference-side or financial mutation | P1 |
| G-008 | Expired/invalid devshard | No unintended billable execution; explicit failure disposition | P1 |
| G-009 | Chain unavailable during settlement | Deferred/retryable state remains internally consistent | P1 |
| G-010 | Host reward claim retry during valid window | No duplicate reward; retry converges to one final state | P1 |
| G-011 | Missing terminal reward-verification prerequisite | Explicit terminal failure; no false claimed state | P1 |
| G-012 | New epoch activity after prior epoch close | Closed-epoch accounting remains immutable except protocol-defined finalization | P1 |

## Executable contracts

- `cases/G-001-normal-inference.yaml` — control contract and evidence requirements.
- `cases/G-002-timeout-retry.yaml` — ambiguous timeout/retry contract, causal IDs, pass/fail rules, and private finding classification.
- `upstream-gap-map.md` — maps this profile against Gonka's own Docker-backed `devshard/testenv` coverage so CGQA focuses on missing cross-boundary guarantees rather than duplicating existing tests.

## Execution order

Start with G-001 as the control. Then execute G-002, G-004, G-005, and G-006 because they exercise the highest-value cross-boundary state transitions without requiring adversarial mainnet behavior.

The current first independent delta is **G-002**. Gonka already has strong local integration coverage for gateway chat, restart persistence, epoch switching, HA, and transport behavior; the CGQA layer adds semantic correlation between one logical user operation, multiple transport attempts, usage/accounting effects, and settlement evidence.

## Hypotheses, not findings

### H1 — ambiguous timeout + retry could separate execution identity from billing identity
If a request executes successfully but the client/gateway loses the response, a retry path must preserve logical-operation identity strongly enough to prevent a second unintended billable effect or make multiple protocol-permitted executions explicit and reconcilable.

### H2 — settlement retry could expose an exactly-once gap
If submission succeeds on-chain but the gateway does not observe confirmation, recovery must recognize the already-finalized settlement before replaying it.

### H3 — epoch/devshard rotation could orphan or duplicate pending usage
Usage accumulated near rotation needs one authoritative ownership rule across old and new devshards.

### H4 — gateway restart could recover protocol state but lose local causal linkage
Persistent state may restore balances/session data while losing the mapping between logical request, execution attempt, and settlement item.

These are verification hypotheses only. They are not vulnerability claims.