// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Escrow} from "../src/examples/Escrow.sol";

interface SurplusVm {
    function deal(address account, uint256 newBalance) external;
    function prank(address sender) external;
    function warp(uint256 timestamp) external;
}

// Deliberately wrong local control: bookkeeping reports principal while the
// actual payout consumes custody surplus. Never deploy this synthetic fixture.
contract SurplusSweepControl {
    uint256 public principal;
    uint256 public reportedPayout;

    function fund() external payable {
        principal = msg.value;
    }

    function release(address payable recipient) external {
        reportedPayout = principal;
        (bool ok,) = recipient.call{value: address(this).balance}("");
        require(ok);
    }
}

contract EscrowSurplusInvariantTest {
    SurplusVm internal constant vm =
        SurplusVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address internal constant BUYER = address(0xB0B);
    address internal constant SELLER = address(0x5E11E);

    function _fund(uint256 principal) internal returns (Escrow escrow) {
        vm.deal(BUYER, principal);
        vm.deal(SELLER, 0);
        vm.prank(BUYER);
        escrow = new Escrow(SELLER, 7 days);
        vm.prank(BUYER);
        escrow.fund{value: principal}();
        assert(escrow.depositedAmount() == principal);
        assert(address(escrow).balance == principal);
    }

    // Independent oracle: the declared liability, actual recipient delta,
    // and post-action custody are measured separately.
    function _conserved(uint256 principal, uint256 surplus, uint256 paid, uint256 custody)
        internal
        pure
        returns (bool)
    {
        return paid == principal && custody == surplus;
    }

    function _snapshot(Escrow escrow) internal view returns (bytes32) {
        return keccak256(
            abi.encode(
                escrow.state(),
                escrow.depositedAmount(),
                escrow.releasedAmount(),
                escrow.refundedAmount(),
                address(escrow).balance,
                BUYER.balance,
                SELLER.balance
            )
        );
    }

    function _attempt(Escrow escrow, address actor, bool refund) internal returns (bool ok) {
        vm.prank(actor);
        (ok,) = address(escrow).call(
            abi.encodeWithSelector(refund ? Escrow.refund.selector : Escrow.release.selector)
        );
    }

    function _run(uint256 principal, uint256 surplus, bool refund, uint8 timing) internal {
        Escrow escrow = _fund(principal);
        // Model an exogenous balance change, not a particular delivery mechanism.
        vm.deal(address(escrow), principal + surplus);
        assert(escrow.depositedAmount() == principal);
        assert(escrow.state() == Escrow.State.Funded);
        assert(address(escrow).balance == principal + surplus);

        uint256 deadline = escrow.refundAfter();
        vm.warp(deadline - 1);
        bytes32 beforeRejected = _snapshot(escrow);
        assert(!_attempt(escrow, BUYER, true));
        assert(_snapshot(escrow) == beforeRejected);
        assert(!_attempt(escrow, SELLER, false));
        assert(_snapshot(escrow) == beforeRejected);

        if (refund || timing > 0) {
            vm.warp(deadline + (timing == 2 ? 1 : 0));
        }
        address recipient = refund ? BUYER : SELLER;
        address other = refund ? SELLER : BUYER;
        uint256 recipientBefore = recipient.balance;
        uint256 otherBefore = other.balance;
        assert(_attempt(escrow, BUYER, refund));
        assert(
            _conserved(principal, surplus, recipient.balance - recipientBefore, address(escrow).balance)
        );
        assert(other.balance == otherBefore);
        assert(escrow.depositedAmount() == principal);
        assert(escrow.releasedAmount() == (refund ? 0 : principal));
        assert(escrow.refundedAmount() == (refund ? principal : 0));
        assert(escrow.state() == (refund ? Escrow.State.Refunded : Escrow.State.Released));
        assert(escrow.payoutInvariantHolds());

        bytes32 terminal = _snapshot(escrow);
        // Both terminal operations must remain rejected, including after time advances.
        vm.warp(deadline + 2);
        assert(!_attempt(escrow, BUYER, refund));
        assert(_snapshot(escrow) == terminal);
        assert(!_attempt(escrow, BUYER, !refund));
        assert(_snapshot(escrow) == terminal);
    }

    function test_ReleasePreservesUnaccountedSurplus() public {
        _run(100, 50, false, 0);
    }

    function test_RefundAtDeadlinePreservesUnaccountedSurplus() public {
        _run(100, 50, true, 1);
    }

    function testFuzz_SurplusDoesNotIncreaseLiability(
        uint96 rawPrincipal,
        uint96 rawSurplus,
        bool refund,
        uint8 rawTiming
    ) public {
        _run(uint256(rawPrincipal) + 1, uint256(rawSurplus), refund, rawTiming % 3);
    }

    function test_NegativeControlDetectsSweepDespiteMatchingBookkeeping() public {
        SurplusSweepControl bad = new SurplusSweepControl();
        vm.deal(address(this), 100);
        vm.deal(SELLER, 0);
        bad.fund{value: 100}();
        vm.deal(address(bad), 150);
        bad.release(payable(SELLER));
        assert(bad.reportedPayout() == bad.principal());
        assert(SELLER.balance == 150);
        assert(address(bad).balance == 0);
        assert(!_conserved(100, 50, SELLER.balance, address(bad).balance));
    }
}
