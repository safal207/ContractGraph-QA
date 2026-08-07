# Invariants

Invariants are the acceptance criteria for reachable contract states.

ContractGraph-QA distinguishes three useful classes.

## Conservation invariants

Value or accounting cannot be created twice.

Example:

```text
releasedAmount + refundedAmount <= depositedAmount
```

## Authorization invariants

An actor without the required authority must never reach a privileged state transition.

Example:

```text
unauthorized actor -> release() -> NEVER succeeds
```

## Temporal invariants

A transition is valid only inside its allowed time window or epoch.

Example:

```text
block.timestamp < refundAfter -> refund() MUST revert
block.timestamp >= refundAfter -> refund() MAY succeed from FUNDED
```

## Terminal-state invariants

Mutually exclusive terminal outcomes cannot both occur.

For escrow:

```text
RELEASED XOR REFUNDED
```

Once one terminal outcome has occurred, the other must be unreachable.

## Invariant design rules

A useful invariant should be:

- independent of a particular happy-path test;
- stated in business/security language;
- machine-checkable where possible;
- valid over every reachable state in scope;
- accompanied by a clear failure meaning.

## From finding to regression

If a path violates an invariant:

1. preserve the minimal failing sequence;
2. fix the contract;
3. replay exactly the same sequence;
4. verify the invariant now holds;
5. keep the path as a regression test.
