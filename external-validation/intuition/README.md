# Intuition — local-only validation harness

Status: **AUTHORIZED FOR LOCAL-ONLY RESEARCH UNDER CURRENT IMMUNEFI RULES**

Rule snapshot: 2026-08-09

Target: `TrustSwapAndBridgeRouter.sol`

Pinned upstream repository:

`0xIntuition/intuition-contracts-v2-periphery`

Pinned source commit:

`bb34cc2625eb64fa1b10afab9e5e73f3c136845e`

## Safety boundary

This harness is intentionally local-only.

Allowed:

- source inspection;
- local Foundry tests;
- mocks / `vm.etch` at the router's constant dependency addresses;
- local fork only when needed and permitted by the current Immunefi program;
- synthetic accounts and synthetic balances.

Not allowed:

- public mainnet/testnet transactions;
- real user funds;
- real private keys;
- testing Aerodrome, MetaLayer/Hyperlane, or other third-party infrastructure itself;
- volumetric testing;
- public disclosure of an unpatched candidate issue.

## Why a dedicated harness

The router embeds dependency addresses as constants. A deterministic local unit harness should therefore prefer Foundry code injection/mocks at those constant addresses rather than live calls.

Dependencies that need local modeling include:

- WETH;
- TRUST;
- Slipstream factory;
- Slipstream swap router;
- MetaERC20Hub;
- optionally quoter for quote-only regression tests.

## First test families

### T1 — seeded-balance state independence

Seed the router with stray ETH, TRUST, and input ERC20 balances. Execute a fresh user flow and assert that only call-scoped value is swapped, bridged, or refunded.

### T2 — repeated call after revert

Force swap or bridge failure after earlier steps and assert full EVM rollback. Then run a second caller and verify no stale balance/allowance dependency.

### T3 — multi-hop packed-path fuzzing

Fuzz around the 43-byte minimum and every +23-byte hop boundary. Include signed int24 spacing extremes and only allow progress when the mocked factory reports every pool as existing.

### T4 — post-`receive()` interaction

The current source added a payable `receive()` after the March 2026 Code4rena review. Model ETH arriving from the swap router during execution and assert no next-caller contamination or unintended extraction path.

### T5 — allowance post-state

Measure WETH/input-token/TRUST allowance state after successful and reverted calls under standard downstream semantics. Escalate only if Intuition integration logic itself allows direct in-scope impact.

## Prior-art exclusions

Do not submit these as new findings:

- bridge fee quoted from `minTrustOut` while bridging `amountOut`;
- `quoteExactInput` swallowing quoter reverts and returning zero;
- `deadline: block.timestamp` ineffective expiry;
- `_refundExcess` failure for non-payable callers;
- historical refundETH/ETH-receive issue;
- constant configuration / Base-only deployment assumptions.

## Candidate escalation gate

A behavior can advance from test result to bounty candidate only when all are true:

1. runnable local PoC passes;
2. direct impact matches a current Immunefi in-scope impact;
3. no prohibited live/third-party testing is needed;
4. the behavior is not present in Code4rena, prior audits, known issues, or repository history;
5. it does not rely on malicious behavior by an out-of-scope external dependency;
6. current program rules are re-checked immediately before submission.

## Evidence chain

`pinned source`
→ `test preconditions`
→ `state/action graph`
→ `local execution`
→ `observed state delta`
→ `expected invariant`
→ `prior-art check`
→ `impact mapping`
→ `classification`

Initial classifications:

- `expected_behavior`
- `known_or_duplicate`
- `candidate_business_logic_defect`
- `inconclusive`
