// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {VulnerableEscrow} from "../src/examples/VulnerableEscrow.sol";
import {PathExplorerHarness} from "../src/harness/PathExplorerHarness.sol";

contract PathExplorerTest is PathExplorerHarness {
    uint8 internal constant ACTION_FUND = 0;
    uint8 internal constant ACTION_RELEASE = 1;
    uint8 internal constant ACTION_REFUND = 2;

    VulnerableEscrow internal escrow;

    function test_NoViolationReachableWithinTwoActions() public {
        SearchResult memory result = _explore(3, 2);
        assert(!result.found);
        assert(result.path.length == 0);
    }

    function test_AutomaticallyFindsMinimalDoublePayoutPath() public {
        SearchResult memory result = _explore(3, 3);

        assert(result.found);
        assert(result.path.length == 3);
        assert(result.path[0] == ACTION_FUND);
        assert(result.path[1] == ACTION_RELEASE);
        assert(result.path[2] == ACTION_REFUND);
        assert(result.exploredCandidates > 0);

        bool invariantHoldsAfterReplay = _replay(result.path);
        assert(!invariantHoldsAfterReplay);
        assert(escrow.depositedAmount() == 100);
        assert(escrow.releasedAmount() == 100);
        assert(escrow.refundedAmount() == 100);
    }

    function _resetTarget() internal override {
        escrow = new VulnerableEscrow();
    }

    function _executeAction(uint8 action) internal override returns (bool accepted) {
        bytes memory callData;

        if (action == ACTION_FUND) {
            callData = abi.encodeWithSelector(VulnerableEscrow.fund.selector, 100);
        } else if (action == ACTION_RELEASE) {
            callData = abi.encodeWithSelector(VulnerableEscrow.release.selector);
        } else if (action == ACTION_REFUND) {
            callData = abi.encodeWithSelector(VulnerableEscrow.refund.selector);
        } else {
            return false;
        }

        (accepted,) = address(escrow).call(callData);
    }

    function _invariantHolds() internal view override returns (bool) {
        return escrow.payoutInvariantHolds();
    }
}
