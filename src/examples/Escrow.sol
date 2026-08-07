// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

contract Escrow {
    enum State {
        Created,
        Funded,
        Released,
        Refunded
    }

    address public immutable buyer;
    address public immutable seller;
    uint256 public immutable refundAfter;

    State public state;
    uint256 public depositedAmount;
    uint256 public releasedAmount;
    uint256 public refundedAmount;

    error Unauthorized();
    error InvalidState();
    error InvalidAmount();
    error TooEarly();
    error TransferFailed();

    constructor(address seller_, uint256 refundDelay) {
        if (seller_ == address(0)) revert InvalidAmount();
        buyer = msg.sender;
        seller = seller_;
        refundAfter = block.timestamp + refundDelay;
        state = State.Created;
    }

    function fund() external payable {
        if (msg.sender != buyer) revert Unauthorized();
        if (state != State.Created) revert InvalidState();
        if (msg.value == 0) revert InvalidAmount();

        depositedAmount = msg.value;
        state = State.Funded;
    }

    function release() external {
        if (msg.sender != buyer) revert Unauthorized();
        if (state != State.Funded) revert InvalidState();

        uint256 amount = depositedAmount;
        releasedAmount = amount;
        state = State.Released;

        (bool ok,) = seller.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function refund() external {
        if (msg.sender != buyer) revert Unauthorized();
        if (state != State.Funded) revert InvalidState();
        if (block.timestamp < refundAfter) revert TooEarly();

        uint256 amount = depositedAmount;
        refundedAmount = amount;
        state = State.Refunded;

        (bool ok,) = buyer.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    function payoutInvariantHolds() external view returns (bool) {
        return releasedAmount + refundedAmount <= depositedAmount;
    }
}
