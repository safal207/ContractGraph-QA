// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {VulnerableTimedEscrow} from "../src/examples/VulnerableTimedEscrow.sol";
import {
    ParameterizedPathExplorerHarness
} from "../src/harness/ParameterizedPathExplorerHarness.sol";

interface VmTemporal {
    function warp(uint256 newTimestamp) external;
}

contract ParameterizedTemporalExplorerTest is ParameterizedPathExplorerHarness {
    VmTemporal internal constant vm =
        VmTemporal(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint8 internal constant ACTION_FUND = 0;
    uint8 internal constant ACTION_WAIT = 1;
    uint8 internal constant ACTION_REFUND = 2;

    uint16 internal constant CASE_FUND_1 = 0;
    uint16 internal constant CASE_FUND_100 = 1;
    uint16 internal constant CASE_FUND_101 = 2;
    uint16 internal constant CASE_WAIT_1_DAY = 3;
    uint16 internal constant CASE_WAIT_7_DAYS = 4;
    uint16 internal constant CASE_REFUND = 5;
    uint16 internal constant CASE_COUNT = 6;

    uint256 internal constant BASE_TIME = 1_800_000_000;

    enum InvariantMode {
        DepositCap,
        RefundTiming
    }

    InvariantMode internal mode;
    VulnerableTimedEscrow internal escrow;

    function test_ParameterCorpusFindsOversizedDeposit() public {
        mode = InvariantMode.DepositCap;

        SearchResult memory result = _exploreCases(CASE_COUNT, 1);

        assert(result.found);
        assert(result.path.length == 1);
        assert(result.path[0].action == ACTION_FUND);
        assert(result.path[0].parameter == 101);
        assert(result.exploredCandidates == 3);

        bool invariantHoldsAfterReplay = _replayCases(result.path);
        assert(!invariantHoldsAfterReplay);
        assert(escrow.depositedAmount() == 101);
    }

    function test_TemporalCorpusFindsEarlyRefundPath() public {
        mode = InvariantMode.RefundTiming;

        SearchResult memory result = _exploreCases(CASE_COUNT, 3);

        assert(result.found);
        assert(result.path.length == 3);
        assert(result.path[0].action == ACTION_FUND);
        assert(result.path[0].parameter == 1);
        assert(result.path[1].action == ACTION_WAIT);
        assert(result.path[1].parameter == 1 days);
        assert(result.path[2].action == ACTION_REFUND);
        assert(result.path[2].parameter == 0);

        bool invariantHoldsAfterReplay = _replayCases(result.path);
        assert(!invariantHoldsAfterReplay);
        assert(uint256(escrow.state()) == uint256(VulnerableTimedEscrow.State.Refunded));
        assert(block.timestamp < escrow.expectedRefundAfter());
    }

    function test_SevenDayWaitPreservesTimingInvariant() public {
        mode = InvariantMode.RefundTiming;
        _resetTarget();

        StepInput[] memory path = new StepInput[](3);
        path[0] = StepInput({action: ACTION_FUND, parameter: 100});
        path[1] = StepInput({action: ACTION_WAIT, parameter: 7 days});
        path[2] = StepInput({action: ACTION_REFUND, parameter: 0});

        bool invariantHoldsAfterReplay = _replayCases(path);
        assert(invariantHoldsAfterReplay);
        assert(uint256(escrow.state()) == uint256(VulnerableTimedEscrow.State.Refunded));
        assert(block.timestamp >= escrow.expectedRefundAfter());
    }

    function _resetTarget() internal override {
        vm.warp(BASE_TIME);
        escrow = new VulnerableTimedEscrow();
    }

    function _stepCase(uint16 caseIndex) internal pure override returns (StepInput memory step) {
        if (caseIndex == CASE_FUND_1) return StepInput({action: ACTION_FUND, parameter: 1});
        if (caseIndex == CASE_FUND_100) return StepInput({action: ACTION_FUND, parameter: 100});
        if (caseIndex == CASE_FUND_101) return StepInput({action: ACTION_FUND, parameter: 101});
        if (caseIndex == CASE_WAIT_1_DAY) {
            return StepInput({action: ACTION_WAIT, parameter: 1 days});
        }
        if (caseIndex == CASE_WAIT_7_DAYS) {
            return StepInput({action: ACTION_WAIT, parameter: 7 days});
        }
        if (caseIndex == CASE_REFUND) return StepInput({action: ACTION_REFUND, parameter: 0});
        revert("unknown case");
    }

    function _executeStep(StepInput memory step) internal override returns (bool accepted) {
        if (step.action == ACTION_WAIT) {
            vm.warp(block.timestamp + step.parameter);
            return true;
        }

        bytes memory callData;
        if (step.action == ACTION_FUND) {
            callData = abi.encodeWithSelector(VulnerableTimedEscrow.fund.selector, step.parameter);
        } else if (step.action == ACTION_REFUND) {
            callData = abi.encodeWithSelector(VulnerableTimedEscrow.refund.selector);
        } else {
            return false;
        }

        (accepted,) = address(escrow).call(callData);
    }

    function _invariantHolds() internal view override returns (bool) {
        if (mode == InvariantMode.DepositCap) {
            return escrow.depositCapInvariantHolds();
        }
        return escrow.refundTimingInvariantHolds();
    }
}
