// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Deliberately vulnerable toy fixture for invariant-detection tests.
/// It models business-state accounting only; do not deploy it.
contract VulnerableEscrow {
    enum State {
        Created,
        Funded,
        Released,
        Refunded
    }

    State public state;
    uint256 public depositedAmount;
    uint256 public releasedAmount;
    uint256 public refundedAmount;

    function fund(uint256 amount) external {
        require(state == State.Created, "invalid state");
        require(amount > 0, "invalid amount");
        depositedAmount = amount;
        state = State.Funded;
    }

    // BUG: state remains Funded after release.
    function release() external {
        require(state == State.Funded, "invalid state");
        releasedAmount = depositedAmount;
    }

    // Because release() does not close the state, refund remains reachable.
    function refund() external {
        require(state == State.Funded, "invalid state");
        refundedAmount = depositedAmount;
        state = State.Refunded;
    }

    function payoutInvariantHolds() external view returns (bool) {
        return releasedAmount + refundedAmount <= depositedAmount;
    }
}
