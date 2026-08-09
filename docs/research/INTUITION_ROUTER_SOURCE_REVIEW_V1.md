# Intuition TrustSwapAndBridgeRouter — bounded source review v1

Status: SOURCE REVIEW COMPLETE / LOCAL VALIDATION NEXT
Date: 2026-08-09

## Authorization and execution boundary

Current Immunefi program status was re-verified before target-specific work:

- `TrustSwapAndBridgeRouter` remains an asset in scope.
- PoC is required.
- KYC is required for payout.
- Testing on mainnet or public testnet is prohibited.
- Local forks are the allowed execution environment.
- Third-party systems are out of scope except where Intuition's own integration logic is at fault.
- Previously reported/publicly known findings are excluded.

This review therefore performs source inspection only. Any execution must remain in a local deterministic harness/local fork. No public-network transaction, real wallet, private key, or real funds are authorized.

## Source pin

Repository: `0xIntuition/intuition-contracts-v2-periphery`

Pinned commit:

`bb34cc2625eb64fa1b10afab9e5e73f3c136845e`

Target:

`contracts/TrustSwapAndBridgeRouter.sol`

## Router state/action graph

### ETH flow

`msg.value`
→ validate recipient/path/pools
→ quote bridge fee using `minTrustOut`
→ `swapEth = msg.value - bridgeFee`
→ WETH deposit
→ exact-input swap
→ receive actual `amountOut` TRUST
→ bridge actual `amountOut` using previously quoted `bridgeFee`

### ERC20 flow

`amountIn + msg.value`
→ validate token/recipient/path/pools
→ pull `amountIn`
→ quote bridge fee using `minTrustOut`
→ exact-input swap
→ receive actual `amountOut` TRUST
→ bridge actual `amountOut` using previously quoted `bridgeFee`
→ refund `msg.value - bridgeFee`

### Direct bridge

`trustAmount + msg.value`
→ quote fee using `trustAmount`
→ pull exact TRUST amount
→ bridge same `trustAmount`
→ refund excess ETH

The direct bridge flow has amount-consistent quote/execution semantics. Both swap flows intentionally or accidentally quote one amount (`minTrustOut`) and execute another (`amountOut`).

## Prior-art exclusions

Do not pursue the following as novel bounty findings:

1. `quoteExactInput` swallowing quoter failures and returning zero.
2. `deadline = block.timestamp` providing no meaningful user expiry.
3. Refund failure for callers unable to receive ETH.
4. Downstream swap-router ETH refund/dust DoS already covered by mitigation review.
5. Constant router/factory/quoter/hub/domain configuration and Base-only deployment semantics.
6. ERC20-flow excess-ETH refund vs ETH-flow value consumption: documented intended behavior.

## Candidate matrix

| ID | Candidate | Status | Reason |
|---|---|---|---|
| H1 | Bridge fee quoted for `minTrustOut` but `transferRemote` called for actual `amountOut` | VALIDATE LOCALLY | Amount is an explicit input to `quoteTransferRemote`; mismatch is in Intuition integration logic. Need prove direct impact with an amount-sensitive local hub model. |
| H2 | Allowance accumulation across bridge calls | DROP | Requires assumptions about third-party hub token-pull behavior; no direct Intuition-only impact established. |
| H3 | Fee-on-transfer / non-standard `tokenIn` causes residual accounting | DROP | Depends on arbitrary external token semantics and likely reverts in exact-input flow. |
| H4 | Repeated/cyclic packed paths bypass endpoint checks | LOW PRIORITY | Structural path arithmetic is internally consistent; existing-pool validation covers every encoded hop. Need a concrete semantic bypass before testing. |
| H5 | `quoteBridgeFee` permits zero recipient | DROP | Quote-only behavior; no demonstrated fund/accounting impact. Execution functions reject zero recipient. |
| H6 | ETH sent directly to router can remain unrecoverable | DROP | Receive-path residue alone does not establish an in-scope exploit or theft; likely informational/user-error class. |
| H7 | Wrong-chain deployment | DROP | Base-only deployment is explicitly documented as intended behavior/prior art. |

## H1 — amount-consistency invariant

### Observed code relationship

Swap flows:

`bridgeFee = quoteTransferRemote(domain, recipient, minTrustOut)`

then later:

`transferRemote{value: bridgeFee}(domain, recipient, amountOut, ...)`

with only:

`amountOut >= minTrustOut`

guaranteed by the swap router.

### Required invariant

For every successful swap-and-bridge execution:

`feePaid >= requiredBridgeFee(actualAmountBridged)`

where:

`actualAmountBridged = amountOut`.

### Local validation model

Build a deterministic mock `IMetaERC20Hub` where:

- `quoteTransferRemote(..., amount)` returns an amount-dependent fee;
- `transferRemote(..., amount, ...)` recomputes the required fee for the actual amount and reverts when `msg.value` is insufficient;
- no third-party network interaction exists.

Test sequence:

1. Set `minTrustOut = X`.
2. Configure/mock swap output `amountOut = X + delta`.
3. Ensure `quote(X) < quote(X + delta)`.
4. Call the router with exactly `quote(X)` allocated as bridge fee.
5. Observe whether swap succeeds and bridge reverts because fee was derived from the wrong amount.
6. Compare to direct `bridgeTrust`, which quotes and bridges the same amount and should pass under the same mock.

### What would make H1 reportable

H1 is not reportable merely because the amounts differ in source.

A report candidate requires all of the following:

- documented or reproducible amount-sensitive fee semantics;
- deterministic local PoC;
- failure caused by Intuition's quote/execution amount mismatch rather than an arbitrary third-party fault;
- in-scope impact under current Immunefi rules (e.g. a concrete fund loss/freezing/accounting consequence, not just inconvenience/gas loss unless that maps to an accepted impact);
- no match to known Code4rena / audit / already-fixed findings.

If the only result is a transaction revert with no qualifying impact, classify as NOT BOUNTY-WORTHY and stop.

## Next action

`H1 → LOCAL MOCK PoC → IMPACT GATE → PRIOR-ART GATE → REPORT / DROP`

Do not widen scope until H1 is resolved.
