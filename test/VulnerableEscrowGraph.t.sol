// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {VulnerableEscrow} from "../src/examples/VulnerableEscrow.sol";
import {CausalGraphHarness} from "../src/harness/CausalGraphHarness.sol";

contract VulnerableEscrowGraphTest is CausalGraphHarness {
    function test_DetectsMinimalPathToDoublePayoutInvariantViolation() public {
        VulnerableEscrow escrow = new VulnerableEscrow();

        escrow.fund(100);
        _recordTransition(
            keccak256("buyer-funds"),
            address(this),
            _actionId("fund"),
            _stateId("CREATED"),
            _stateId("FUNDED"),
            keccak256("deposit-recorded")
        );

        escrow.release();
        _recordTransition(
            keccak256("release-request"),
            address(this),
            _actionId("release"),
            _stateId("FUNDED"),
            _stateId("FUNDED"),
            keccak256("released-without-closing-state")
        );

        escrow.refund();
        _recordTransition(
            keccak256("refund-still-reachable"),
            address(this),
            _actionId("refund"),
            _stateId("FUNDED"),
            _stateId("REFUNDED"),
            keccak256("second-payout-recorded")
        );

        assert(escrow.releasedAmount() == 100);
        assert(escrow.refundedAmount() == 100);
        assert(escrow.depositedAmount() == 100);
        assert(!escrow.payoutInvariantHolds());
    }
}
