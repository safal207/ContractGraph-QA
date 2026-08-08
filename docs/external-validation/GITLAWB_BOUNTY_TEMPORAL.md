# External validation: GitlawbBounty timely-submission dispute path

Status: **reproduced behavior / candidate business-logic finding**

This note does not label the behavior a confirmed vulnerability until upstream maintainers confirm the intended deadline semantics for a bounty that has already entered `Submitted`.

## Authorization and safety boundary

- Upstream repository: `Gitlawb/contracts`
- Upstream repository explicitly permits forking and auditing its open-source contracts.
- Pinned upstream commit: `b60de4973c568b34975c20f18cde1afd71a59f1b`
- Target source: `src/GitlawbBounty.sol`
- Validation is local-only.
- No RPC endpoint is used.
- No deployed testnet or mainnet contract is called.
- No wallet, private key, token, or real funds are used.

The validation workflow first compares the pinned local source bytes with the raw upstream file at the exact commit and fails closed if they differ.

## Observed state path

```text
Open
  -> claim
Claimed
  -> wait until claim deadline - 1 second
  -> submit PR
Submitted
  -> wait until original claim deadline + 1 second
  -> unrelated third party calls disputeBounty
Open
```

After the final transition, the contract clears:

- `claimantDid`;
- `claimantAddress`;
- `prId`;
- `claimedAt`;
- `submittedAt`.

The original creator can no longer call `approveBounty` for that timely submission because the bounty is no longer in `Submitted` state.

## Why this is noteworthy

`submitBounty` accepts a submission while `block.timestamp <= claimedAt + deadline`.

The contract documentation describes `disputeBounty` as the path used when an agent **missed the deadline**, but the implementation allows the same dispute transition from both `Claimed` and `Submitted` after the original claim deadline.

Therefore an agent can submit on time and still lose the submitted state solely because the original claim deadline later elapses before the creator approves the work.

## Candidate invariant

> Once a claimant has successfully submitted before the claim deadline, expiry of that original claim deadline alone should not invalidate the submitted work unless the protocol explicitly defines a separate review/approval expiry policy.

This is an inferred business invariant and must be confirmed with upstream maintainers before the behavior is described as a vulnerability.

## Reproduction

The isolated Foundry project is under:

```text
external-validation/gitlawb/
```

It uses the upstream compiler settings:

```toml
via_ir = true
optimizer = true
optimizer_runs = 200
```

Regression test:

```text
test_timelySubmissionCanBeReopenedByThirdPartyAfterClaimDeadline
```

Verified GitHub Actions run:

```text
31249551058
```

Result:

```text
1 passed; 0 failed; 0 skipped
```

The main ContractGraph-QA Product, CI, Finding report, and Portability workflows also remained green on the same head.

## Impact demonstrated

Demonstrated:

- an unrelated caller can erase a timely submitted state after the original claim deadline;
- the original claimant metadata and PR reference are cleared;
- the creator loses the ability to approve that cleared submission;
- escrowed tokens remain in the bounty contract and the bounty returns to `Open`.

Not demonstrated:

- direct theft of escrowed funds;
- unauthorized token transfer;
- mainnet/testnet exploitation;
- any claim about impact beyond the locally reproduced state transition.

## Possible remediation, if upstream confirms the invariant

Two straightforward policy options are:

1. allow deadline disputes only while the bounty remains `Claimed`; or
2. define a separate review deadline after `submittedAt` and make the post-submission transition explicit.

The correct fix depends on the intended product semantics.

## Next action

Ask the upstream maintainer one narrow question before assigning severity:

> Is a bounty that was successfully submitted before the claim deadline intended to remain reviewable by the creator after that deadline, or is `Submitted` intentionally allowed to expire using the original claim deadline?

If the intended answer is that timely submissions must remain reviewable, this reproduction becomes a confirmed temporal/business-logic finding.
