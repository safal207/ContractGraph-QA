# Intuition `TrustSwapAndBridgeRouter` — bounded target plan v1

Status: **RULES VERIFIED — LOCAL-ONLY RESEARCH MAY PROCEED**

Rule snapshot date: **2026-08-09**

Official bounty program: `https://immunefi.com/bug-bounty/intuition/`

This document is a bounded research plan. It does not assert that any behavior is a vulnerability or that a bounty is owed.

## Current authorization / program gate

Verified from the current official Immunefi program on 2026-08-09:

- program is active;
- live since 2026-07-08, last updated 2026-07-17;
- `TrustSwapAndBridgeRouter - Base Mainnet` is explicitly listed as an asset in scope;
- smart-contract PoC is required;
- KYC is required;
- reward range currently shown for smart contracts is Low $1,000 flat, Medium $1,000–$2,500, High $2,500–$5,000, Critical $5,000–$100,000;
- testing against public mainnet or public testnet is explicitly out of scope — use a local fork;
- external systems integrated by the router (Aerodrome / Uniswap v3 routers and MetaLayer / Hyperlane) are out of scope except where Intuition's own integration logic is at fault;
- automated scanner output without a working PoC is out of scope;
- MEV/front-running/sandwich findings are out of scope under the current sequencing assumptions unless the issue defeats the user's configured slippage bound;
- previous unresolved audit findings are not reward-eligible.

Execution boundary remains stricter than the program minimum:

- exact source pin;
- local Foundry tests/mocks first;
- local fork only when needed;
- no public-network transactions;
- no real wallets/private keys;
- no real funds;
- no testing of third-party infrastructure.

## Pinned source

Official repository: `0xIntuition/intuition-contracts-v2-periphery`

Pinned commit: `bb34cc2625eb64fa1b10afab9e5e73f3c136845e`

Target:

`contracts/TrustSwapAndBridgeRouter.sol`

Current pinned blob SHA observed during review:

`27cdb7286d2768f984b32896e9ab21e32f343c27`

## Differential from the March 2026 Code4rena scope

Code4rena reviewed the periphery repository at:

`b026521fe26db8249cd0795b62ec480fd8c848e8`

Current pinned source is five commits ahead. For `TrustSwapAndBridgeRouter.sol`, the observed code delta is only **3 added lines**, while tests gained additional coverage. The current source includes:

```solidity
receive() external payable { }
```

with documentation that it accepts downstream swap-router ETH refunds.

Therefore the current router is overwhelmingly the same audited surface; novelty work should focus on behaviors not already captured by the March/April audit and on the narrow post-audit delta/regression interactions.

## Historical prior-art gate

This contract was in the March 2026 Code4rena scope. The final report contains multiple router findings that must be excluded as novelty targets.

Known / prior-art examples include:

1. **Bridge fee quoted using `minTrustOut` while the actual bridge uses `amountOut`.** Keep only as regression coverage.
2. **`quoteExactInput` catches quoter reverts and returns zero.** Already reported as low/informational; do not submit as new.
3. **`deadline: block.timestamp` makes deadline expiry ineffective.** Already reported; additionally MEV/front-running-based impact is excluded by the current Immunefi rules unless slippage protection itself is defeated.
4. **`_refundExcess()` can revert for callers that cannot receive ETH.** Already reported; do not submit as new.
5. **Downstream `refundETH` / ETH-receive behavior.** Repository history now includes the `receive()` path; treat as regression/post-fix behavior, not a fresh claim by default.
6. **Constant-configured router and Base-only deployment assumptions.** Explicitly documented as intentional.

A candidate must pass the prior-art gate before PoC effort is expanded.

## Contract flow model

### ETH path

`caller ETH`
→ validate recipient/path/pools
→ quote bridge fee using `minTrustOut`
→ `swapEth = msg.value - bridgeFee`
→ wrap ETH to WETH
→ approve Slipstream router
→ exact-input swap to TRUST
→ bridge actual `amountOut`
→ emit result

### ERC-20 path

`caller tokenIn + ETH bridge fee`
→ validate amount/recipient/token/path/pools
→ transferFrom caller
→ quote bridge fee
→ approve Slipstream router
→ exact-input swap to TRUST
→ bridge TRUST
→ refund excess ETH
→ emit result

### Direct TRUST path

`caller TRUST + ETH bridge fee`
→ validate amount/recipient
→ quote bridge fee
→ transferFrom caller
→ bridge TRUST
→ refund excess ETH
→ emit result

## Bounded source-review results — 2026-08-09

The following are **research conclusions/questions**, not vulnerability claims.

### R1 — path parsing currently appears fail-closed

The router checks:

- minimum packed path length;
- exact hop alignment `(path.length - 20) % 23 == 0`;
- expected first token;
- expected TRUST final token;
- every referenced pool through the configured Slipstream factory.

The signed `int24 tickSpacing` extraction is followed by a factory lookup, so malformed spacing must still map to an existing pool to proceed.

**Current classification:** `expected_behavior`; retain fuzz/regression tests rather than report.

### R2 — swap/bridge failure atomicity appears protected by EVM reversion + `nonReentrant`

Token transfer/approval, swap and bridge are performed inside one transaction. If modeled downstream calls revert, EVM state should roll back. All three value-moving entry points are `nonReentrant`.

**Current classification:** `expected_behavior`; verify locally with mocks.

### R3 — cross-call stale state has no obvious dedicated accounting variable

The router keeps no per-user/per-call accounting storage. It relies on token balances/allowances and external return values. This reduces stale-state surface, but means local tests should explicitly seed the router with stray ETH/TRUST/input-token balances and verify that a later caller cannot accidentally consume another caller's residue under standard-token assumptions.

**Current classification:** `candidate_test_family`, no defect established.

### R4 — allowance lifecycle deserves bounded regression testing, but no direct exploit is established from source inspection

The router uses `safeIncreaseAllowance` for WETH/input tokens and TRUST. Under standard exact-input and bridge semantics, intended downstream contracts should consume the approved amount. If an approved downstream contract consumes less, allowance can remain; however impact relying solely on third-party or privileged downstream behavior is not a valid Intuition finding.

**Current classification:** `candidate_test_family`, likely expected/integration-dependent.

### R5 — arbitrary ETH can now be received and has no generic recovery path

The post-audit `receive()` function allows ETH to be sent to the router. Normal ETH flow spends only `msg.value - bridgeFee`, not the contract's prior ETH balance, and ERC20/direct bridge refund calculations are also based on the current call's `msg.value`. Therefore stray ETH appears not to contaminate normal per-call accounting, but may remain stuck because there is no rescue function.

A generic "stuck donation" is not by itself an in-scope fund-loss claim, especially when caused by unsolicited transfers. Keep this only as a state-independence regression check.

**Current classification:** `expected_behavior / non-reportable unless a user-flow PoC shows direct in-scope impact`.

### R6 — fee-on-transfer / hostile token behavior is not currently a strong target

`swapAndBridgeWithERC20` accepts arbitrary `tokenIn`, but a token that transfers less than `amountIn` will generally make downstream exact-input execution fail/revert unless the integration explicitly supports such semantics. No direct Intuition-fund impact is established, and external token behavior is a weak basis under the current rules.

**Current classification:** `deprioritized`.

## Highest-value remaining local test families

Given the prior-art exclusions, prioritize these bounded families:

### T1 — seeded-balance state independence

Seed router with stray:

- ETH;
- TRUST;
- an input ERC20.

Then run a fresh caller flow and prove whether only the fresh caller's intended amounts can be swapped/bridged/refunded.

Goal: rule out cross-user residual-balance contamination.

### T2 — repeated call after downstream revert

Model:

1. input transfer succeeds;
2. swap or bridge mock reverts;
3. transaction rolls back;
4. second caller executes a clean flow.

Assert balances, allowances and bridged amount are independent of the failed call.

### T3 — multi-hop parser fuzzing

Generate structurally valid and invalid packed paths around:

- 43-byte minimum;
- every `+23` hop boundary;
- negative/positive `int24` spacing extremes;
- repeated token addresses;
- zero token addresses;
- paths whose every pool lookup returns nonzero only under explicitly configured mocks.

Goal: find parser/factory disagreement, not mere malformed-input reverts.

### T4 — post-`receive()` refund interaction regression

Model ETH refunds arriving from the swap router during an ETH-path exact-input call and verify:

- no unexpected bridge-value shift;
- no contamination of the next caller;
- no ability for a later caller to extract seeded ETH through `_refundExcess()`.

This is the most relevant post-Code4rena delta family.

### T5 — exact bridge allowance post-state

With a standard TRUST mock and bridge-hub mock, test whether successful/reverted bridge calls leave allowances exactly as expected and whether a later call can spend anything beyond its own intended amount.

Only escalate if the PoC demonstrates Intuition integration logic causing direct in-scope fund/accounting impact without relying on malicious behavior by the trusted bridge hub.

## First local-only test matrix

1. happy-path direct TRUST bridge with mocks;
2. ERC-20 single-hop happy path;
3. ETH single-hop happy path;
4. malformed path length / hop alignment;
5. wrong token start / wrong TRUST end;
6. missing pool;
7. swap revert → full state rollback;
8. bridge revert → full state rollback;
9. repeated call after revert;
10. seeded ETH before a fresh ERC20/direct bridge call;
11. seeded TRUST before a fresh swap/bridge call;
12. seeded input token before a fresh ERC20 swap;
13. downstream ETH refund into `receive()` during ETH flow;
14. multi-hop parser fuzzing;
15. standard-token allowance post-state;
16. prior-known fee/minimum issue as **regression only**, never novelty;
17. prior-known refund failure as **regression only**, never novelty.

## Evidence format

For any candidate behavior:

`source commit`
→ `preconditions`
→ `bounded action sequence`
→ `observed state`
→ `expected state / semantics question`
→ `local reproduction evidence`
→ `prior-art check`
→ `program-rule check`
→ `classification`

Allowed classifications before a valid PoC and prior-art check are complete:

- `expected_behavior`
- `known_or_duplicate`
- `candidate_business_logic_defect`
- `inconclusive`

Do not label a vulnerability from source inspection alone.

## Next gate

Rules are now verified. The next authorized step is to build a **local mock/Foundry harness** for T1–T5 on the pinned source.

Do not submit anything unless:

1. the local PoC runs successfully;
2. it demonstrates a current in-scope impact;
3. it does not rely on prohibited public-network testing or third-party-system testing;
4. it survives Code4rena / audit prior-art review;
5. the current Immunefi rules are re-checked again immediately before submission.
