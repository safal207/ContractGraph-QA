# Intuition `TrustSwapAndBridgeRouter` — bounded target plan v1

Status: **HOLD — CURRENT BOUNTY RULES MUST BE VERIFIED BEFORE EXECUTION OR SUBMISSION**

This document is a research plan only. It does not assert that the target is currently eligible for a bounty, that any behavior is a vulnerability, or that external execution is authorized.

## Pinned source

Official repository: `0xIntuition/intuition-contracts-v2-periphery`

Pinned commit: `bb34cc2625eb64fa1b10afab9e5e73f3c136845e`

Target:

`contracts/TrustSwapAndBridgeRouter.sol`

The pinned commit is the latest commit observed in the official repository during preparation of this plan.

## Authorization gate

Before any target-specific execution intended for bounty submission, verify from the **current official bounty page**:

- program is active;
- this exact contract/repository/version is in scope;
- accepted testing environments;
- local fork / local reproduction rules;
- PoC requirements;
- exclusions and known-issue policy;
- duplicate / previously disclosed issue rules;
- severity/payment rules.

Until that check is complete, status remains `HOLD`.

Even after authorization, default execution boundary is:

- source copy pinned to an exact commit;
- local Foundry tests and mocks first;
- local fork only if the current program explicitly permits it;
- no mainnet or public-testnet transactions;
- no wallet/private-key use;
- no real funds;
- no interaction with unrelated third-party systems.

## Historical prior-art gate

This contract appeared in the March 2026 Code4rena Intuition contest scope. Prior findings must therefore be treated as duplicate/known until proven otherwise.

At minimum, exclude as novelty targets:

1. **Bridge fee quoted from slippage minimum** — prior report already describes quoting `quoteTransferRemote` with `minTrustOut` and bridging `amountOut`.
2. **SwapRouter refundETH dust DoS / refund handling** — the official repository history contains a dedicated fix for S-324 and later accepts ETH via `receive()`.

These may be retained only as local regression checks, not presented as new findings.

## Contract flow model

### ETH path

`caller ETH`
→ validate recipient/path/pools
→ quote bridge fee
→ `swapEth = msg.value - bridgeFee`
→ wrap ETH to WETH
→ approve Slipstream router
→ exact-input swap to TRUST
→ bridge actual TRUST amount
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

## Invariant families for bounded local validation

The following are **research questions**, not vulnerability claims.

### I1 — successful-call value conservation

For an authorized local model, after a successful call:

- user input is accounted for exactly once;
- bridged TRUST equals the router-reported bridged amount;
- no unintended residual input token remains in the router;
- no unintended residual ETH remains because of the successful path under the modeled downstream behavior.

### I2 — failure atomicity

If swap or bridge execution reverts in the modeled environment, caller-visible token/ETH state should revert consistently with EVM transaction semantics. Any non-standard token behavior must be isolated and explicitly declared rather than generalized.

### I3 — recipient consistency

The same intended recipient must remain consistent through formatting, fee quotation, bridge execution, and emitted evidence.

### I4 — path structural consistency

Malformed packed paths, wrong first token, wrong final TRUST token, invalid hop alignment, or missing pools should fail closed before a successful value-moving path completes.

### I5 — slippage contract

`amountOutMinimum = minTrustOut` must remain the effective minimum for swap completion. This is a regression/property check only; it does not re-open the known fee/minimum issue.

### I6 — allowance lifecycle

Under modeled standard-token and approved-router semantics, successful and reverted calls should not create an unexpected residual approval state that contradicts the intended integration contract. If residual allowance is by design, document it rather than classify it as a defect.

### I7 — repeated-call state independence

A previous successful or reverted call should not cause the next authorized local call to consume another user's residual token/ETH state or observe stale per-call accounting assumptions.

### I8 — zero / malformed boundary behavior

Zero amount, zero recipient, invalid token, short path, and malformed multi-hop path should preserve the documented fail-closed behavior.

## First local-only test matrix after rules verification

1. happy-path direct TRUST bridge with mocks;
2. ERC-20 single-hop happy path;
3. ETH single-hop happy path;
4. malformed path length / hop alignment;
5. wrong token start / wrong TRUST end;
6. missing pool;
7. swap revert → state rollback;
8. bridge revert → state rollback;
9. repeated call after revert;
10. excess ETH refund on ERC-20/direct bridge;
11. recipient evidence consistency;
12. standard-token allowance post-state;
13. multi-hop path structural regression;
14. prior-known fee/minimum issue as **regression only**, never novelty.

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

Allowed classifications before maintainer/program intent is confirmed:

- `expected_behavior`
- `known_or_duplicate`
- `candidate_business_logic_defect`
- `inconclusive`

Do not label a vulnerability from source inspection alone.

## Next gate

No target execution should start from this plan until the current official bounty rules are re-checked. Once verified, fill:

- official bounty URL;
- rule snapshot date;
- exact in-scope asset reference;
- approved environment;
- PoC requirement;
- exclusions/known issues;
- reporting channel.

Then freeze the scope and create the local reproduction harness.
