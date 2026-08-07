// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Deliberately vulnerable local fixture for parameter and temporal QA exploration.
/// @dev Business-state model only. Do not deploy.
contract VulnerableTimedEscrow {
    enum State {
        Created,
        Funded,
        Refunded
    }

    uint256 public constant MAX_DEPOSIT = 100;
    uint256 public constant EXPECTED_REFUND_DELAY = 7 days;
    uint256 public constant ACTUAL_REFUND_DELAY = 1 days;

    State public state;
    uint256 public depositedAmount;
    uint256 public refundedAmount;
    uint256 public immutable refundAfter;
    uint256 public immutable expectedRefundAfter;

    constructor() {
        refundAfter = block.timestamp + ACTUAL_REFUND_DELAY;
        expectedRefundAfter = block.timestamp + EXPECTED_REFUND_DELAY;
    }

    function fund(uint256 amount) external {
        require(state == State.Created, "invalid state");
        require(amount > 0, "invalid amount");

        // BUG: the declared MAX_DEPOSIT business rule is not enforced.
        depositedAmount = amount;
        state = State.Funded;
    }

    function refund() external {
        require(state == State.Funded, "invalid state");
        require(block.timestamp >= refundAfter, "too early");

        refundedAmount = depositedAmount;
        state = State.Refunded;
    }

    function depositCapInvariantHolds() external view returns (bool) {
        return depositedAmount <= MAX_DEPOSIT;
    }

    function refundTimingInvariantHolds() external view returns (bool) {
        return state != State.Refunded || block.timestamp >= expectedRefundAfter;
    }
}
