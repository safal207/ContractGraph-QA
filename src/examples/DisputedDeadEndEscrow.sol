// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Deliberately vulnerable lifecycle fixture for compiler-AST extraction tests.
/// It models business state only and must not be deployed.
contract DisputedDeadEndEscrow {
    enum State {
        Created,
        Funded,
        Released,
        Refunded,
        Disputed
    }

    State public state;
    uint256 public depositedAmount;

    constructor() {
        state = State.Created;
    }

    function fund(uint256 amount) external {
        if (state != State.Created) revert("invalid state");
        if (amount == 0) revert("invalid amount");
        depositedAmount = amount;
        state = State.Funded;
    }

    function release() external {
        if (state != State.Funded) revert("invalid state");
        state = State.Released;
    }

    function refund() external {
        if (state != State.Funded) revert("invalid state");
        state = State.Refunded;
    }

    function raiseDispute() external {
        if (state != State.Funded) revert("invalid state");
        state = State.Disputed;
    }

    // BUG: Disputed has no resolution transition.
}
