# Aera V3 refund-window temporal hypothesis

Status: **INCONCLUSIVE — research hypothesis, not a vulnerability claim**

This research note applies ContractGraph-QA's causal-temporal modeling to a public Aera V3 source snapshot that is listed in the Aera Immunefi smart-contract bug-bounty scope.

## Safety and scope

- Program: Aera on Immunefi
- Asset family: `MultiDepositorVault` / `ProvisionerV2`
- Public source repository: `aera-finance/aera-contracts-public`
- Pinned source commit: `f0ebc15985b2f19d1e599b604370fdbaeb314180`
- Testing performed here: repository-source review plus an independent local semantic model only
- Mainnet/public-testnet execution: **none**
- Third-party oracle execution: **none**
- Private keys / privileged credentials: **none**

Immunefi rules prohibit testing deployed mainnet/public-testnet contracts. Any future execution must stay on a local deployment or an authorized local fixed-block fork.

## Source observations

At the pinned commit, `ProvisionerV2._syncDeposit` computes a per-deposit `refundableUntil`, stores the deposit hash, and then directly assigns:

```text
userUnitsRefundableUntil[receiver] = refundableUntil
```

`ProvisionerV2.areUserUnitsLocked(user)` reports the lock active while:

```text
userUnitsRefundableUntil[user] >= block.timestamp
```

`MultiDepositorVault._update` blocks normal unit transfers while the provisioner reports the sender's units locked.

`ProvisionerV2.setDepositDetails` is an authorized configuration operation and permits changing `depositRefundTimeout` to any value not exceeding `MAX_DEPOSIT_REFUND_TIMEOUT`; the observed validation does not require the new timeout to be greater than or equal to the previous timeout.

## Candidate temporal invariant

For a receiver with any still-active refundable synchronous deposit:

```text
active refundable sync deposit exists
    => receiver units remain transfer-locked
       until that deposit's refundableUntil
```

This is a model-derived candidate invariant. It is not stated here as an Aera specification requirement.

## Modeled path

The independent model uses the following finite action alphabet:

1. `syncDeposit` with a long refund timeout
2. authorized `configureShorterRefundTimeout`
3. another `syncDeposit` for the same receiver
4. advance modeled time beyond the second lock but before the first refund window closes

The modeled state transition is:

```text
first deposit:   first refundableUntil = 10, receiver lockUntil = 10
shorten timeout: configured timeout = 1
second deposit:  first refundableUntil = 10, receiver lockUntil = 1
advance time:    now = 2

first refund window open: true
receiver units locked:    false
```

`MultiInvariantStateExplorerHarness` is used to search the bounded model rather than hard-coding the violating path as the only test.

## Why this remains inconclusive

This path includes `configureShorterRefundTimeout`, which represents a `requiresAuth` operation in the real protocol. Aera's Immunefi scope excludes impacts that require privileged-address access in the prohibited way described by the program rules.

Therefore the model result is **not** being treated as a bounty finding unless all of the following are independently established:

1. the configuration transition is realistic under the protocol's intended operating model without attacker privilege;
2. an unprivileged actor can derive an in-scope impact after such a legitimate configuration transition;
3. the impact is reproducible against the pinned real implementation on a local deployment/fixed-block fork;
4. the behavior is not already documented, intended, mitigated, or covered by a known issue/audit;
5. the report fits current Immunefi scope and PoC rules.

## Next verification gate

The next safe step is a real-code local PoC that recreates only the relevant Aera contracts/dependencies or uses an explicitly authorized fixed-block local fork. The PoC should test whether the older refundable deposit can still be processed after the receiver's transfer lock has been shortened and units have been moved, and whether that creates an in-scope user-funds/yield impact.

Until that gate passes, this repository must describe the result only as a temporal-model hypothesis.

## External references

- Aera bug bounty scope: https://immunefi.com/bug-bounty/aera/scope/
- Aera bug bounty information: https://immunefi.com/bug-bounty/aera/information/
- Immunefi rules: https://immunefi.com/rules/
- Aera public source: https://github.com/aera-finance/aera-contracts-public
- Pinned `MultiDepositorVault.sol`: https://github.com/aera-finance/aera-contracts-public/blob/f0ebc15985b2f19d1e599b604370fdbaeb314180/v3/src/core/MultiDepositorVault.sol
- Pinned `ProvisionerV2.sol`: https://github.com/aera-finance/aera-contracts-public/blob/f0ebc15985b2f19d1e599b604370fdbaeb314180/v3/src/core/ProvisionerV2.sol
