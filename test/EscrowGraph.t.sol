// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Escrow} from "../src/examples/Escrow.sol";
import {CausalGraphHarness} from "../src/harness/CausalGraphHarness.sol";

interface Vm {
    function deal(address account, uint256 newBalance) external;
    function prank(address msgSender) external;
    function warp(uint256 newTimestamp) external;
}

contract EscrowGraphTest is CausalGraphHarness {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address internal buyer = address(0xB0B);
    address internal seller = address(0x5E11E);
    Escrow internal escrow;

    function setUp() public {
        vm.deal(buyer, 100 ether);
        vm.deal(seller, 1 ether);

        vm.prank(buyer);
        escrow = new Escrow(seller, 7 days);
    }

    function test_CausalPath_FundThenRelease() public {
        vm.prank(buyer);
        escrow.fund{value: 1 ether}();

        _recordTransition(
            keccak256("buyer-intent"),
            buyer,
            _actionId("fund"),
            _stateId("CREATED"),
            _stateId("FUNDED"),
            keccak256("escrow-funded")
        );

        vm.prank(buyer);
        escrow.release();

        _recordTransition(
            keccak256("buyer-accepts-delivery"),
            buyer,
            _actionId("release"),
            _stateId("FUNDED"),
            _stateId("RELEASED"),
            keccak256("seller-paid")
        );

        assert(uint256(escrow.state()) == uint256(Escrow.State.Released));
        assert(escrow.releasedAmount() == 1 ether);
        assert(escrow.refundedAmount() == 0);
        assert(escrow.payoutInvariantHolds());
    }

    function test_TemporalPath_RefundOnlyAfterDeadline() public {
        vm.prank(buyer);
        escrow.fund{value: 2 ether}();

        bool earlyRefundSucceeded;
        vm.prank(buyer);
        try escrow.refund() {
            earlyRefundSucceeded = true;
        } catch {
            earlyRefundSucceeded = false;
        }
        assert(!earlyRefundSucceeded);

        vm.warp(escrow.refundAfter());

        vm.prank(buyer);
        escrow.refund();

        _recordTransition(
            keccak256("refund-deadline-reached"),
            buyer,
            _actionId("refund"),
            _stateId("FUNDED"),
            _stateId("REFUNDED"),
            keccak256("buyer-refunded")
        );

        assert(uint256(escrow.state()) == uint256(Escrow.State.Refunded));
        assert(escrow.refundedAmount() == 2 ether);
        assert(escrow.releasedAmount() == 0);
        assert(escrow.payoutInvariantHolds());
    }

    function test_UnauthorizedActorCannotFund() public {
        bool sellerFunded;
        vm.prank(seller);
        try escrow.fund{value: 1 ether}() {
            sellerFunded = true;
        } catch {
            sellerFunded = false;
        }

        assert(!sellerFunded);
        assert(uint256(escrow.state()) == uint256(Escrow.State.Created));
    }

    function test_UnauthorizedActorCannotRelease() public {
        vm.prank(buyer);
        escrow.fund{value: 1 ether}();

        bool sellerReleased;
        vm.prank(seller);
        try escrow.release() {
            sellerReleased = true;
        } catch {
            sellerReleased = false;
        }

        assert(!sellerReleased);
        assert(uint256(escrow.state()) == uint256(Escrow.State.Funded));
        assert(escrow.releasedAmount() == 0);
        assert(escrow.refundedAmount() == 0);
        assert(escrow.payoutInvariantHolds());
    }

    function test_UnauthorizedActorCannotRefundAfterDeadline() public {
        vm.prank(buyer);
        escrow.fund{value: 1 ether}();
        vm.warp(escrow.refundAfter());

        bool sellerRefunded;
        vm.prank(seller);
        try escrow.refund() {
            sellerRefunded = true;
        } catch {
            sellerRefunded = false;
        }

        assert(!sellerRefunded);
        assert(uint256(escrow.state()) == uint256(Escrow.State.Funded));
        assert(escrow.releasedAmount() == 0);
        assert(escrow.refundedAmount() == 0);
        assert(escrow.payoutInvariantHolds());
    }

    function testFuzz_FundingPreservesPayoutInvariant(uint96 amount) public {
        if (amount == 0) return;

        vm.deal(buyer, uint256(amount));
        vm.prank(buyer);
        escrow.fund{value: uint256(amount)}();

        assert(escrow.depositedAmount() == uint256(amount));
        assert(escrow.payoutInvariantHolds());
    }
}
