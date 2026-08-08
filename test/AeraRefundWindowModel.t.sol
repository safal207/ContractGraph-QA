// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AeraRefundWindowModel} from "../src/examples/AeraRefundWindowModel.sol";
import {
    MultiInvariantStateExplorerHarness
} from "../src/harness/MultiInvariantStateExplorerHarness.sol";

contract AeraRefundWindowModelTest is MultiInvariantStateExplorerHarness {
    uint8 internal constant ACTION_SYNC_DEPOSIT = 0;
    uint8 internal constant ACTION_SHORTEN_TIMEOUT = 1;
    uint8 internal constant ACTION_ADVANCE_TIME = 2;

    uint16 internal constant CASE_COUNT = 3;
    uint16 internal constant INVARIANT_COUNT = 1;

    AeraRefundWindowModel internal model;

    function setUp() public {
        model = new AeraRefundWindowModel();
    }

    function test_ExplorerFindsMinimalRefundWindowLockMismatch() public {
        MultiInvariantSearchResult memory result =
            _exploreAllInvariants(CASE_COUNT, 4, INVARIANT_COUNT, 256, 64);

        assert(result.outcomes[0].status == InvariantOutcomeStatus.Violated);
        assert(result.outcomes[0].path.length == 4);
        assert(result.outcomes[0].path[0].action == ACTION_SYNC_DEPOSIT);
        assert(result.outcomes[0].path[1].action == ACTION_SHORTEN_TIMEOUT);
        assert(result.outcomes[0].path[2].action == ACTION_SYNC_DEPOSIT);
        assert(result.outcomes[0].path[3].action == ACTION_ADVANCE_TIME);
    }

    function test_ReplayShowsOlderRefundWindowOpenAfterLockEnds() public {
        model.syncDeposit();
        model.configureShorterRefundTimeout();
        model.syncDeposit();
        model.advanceTime();

        assert(model.firstRefundWindowOpen());
        assert(!model.unitsLocked());
        assert(!model.temporalLockInvariantHolds());
    }

    function test_SameTimeoutDoesNotShortenExistingLock() public {
        model.syncDeposit();
        model.syncDeposit();
        model.advanceTime();

        assert(model.firstRefundWindowOpen());
        assert(model.unitsLocked());
        assert(model.temporalLockInvariantHolds());
    }

    function _evaluateInvariant(uint256 invariantIndex)
        internal
        view
        override
        returns (InvariantEvaluation)
    {
        if (invariantIndex != 0) revert("unknown invariant");
        return model.temporalLockInvariantHolds()
            ? InvariantEvaluation.Holds
            : InvariantEvaluation.Violated;
    }

    function _resetTarget() internal override {
        model.reset();
    }

    function _stepCase(uint16 caseIndex) internal pure override returns (StepInput memory step) {
        if (caseIndex == 0) return StepInput({action: ACTION_SYNC_DEPOSIT, parameter: 0});
        if (caseIndex == 1) return StepInput({action: ACTION_SHORTEN_TIMEOUT, parameter: 0});
        if (caseIndex == 2) return StepInput({action: ACTION_ADVANCE_TIME, parameter: 0});
        revert("unknown case");
    }

    function _executeStep(StepInput memory step) internal override returns (bool accepted) {
        bytes memory callData;
        if (step.action == ACTION_SYNC_DEPOSIT) {
            callData = abi.encodeWithSelector(AeraRefundWindowModel.syncDeposit.selector);
        } else if (step.action == ACTION_SHORTEN_TIMEOUT) {
            callData = abi.encodeWithSelector(AeraRefundWindowModel.configureShorterRefundTimeout.selector);
        } else if (step.action == ACTION_ADVANCE_TIME) {
            callData = abi.encodeWithSelector(AeraRefundWindowModel.advanceTime.selector);
        } else {
            return false;
        }

        (accepted,) = address(model).call(callData);
    }

    function _invariantHolds() internal pure override returns (bool) {
        return true;
    }

    function _multiStateHash() internal view override returns (bytes32) {
        return keccak256(
            abi.encode(
                model.nowTs(),
                model.depositRefundTimeout(),
                model.userUnitsRefundableUntil(),
                model.firstDepositActive(),
                model.firstDepositRefundableUntil(),
                model.depositCount()
            )
        );
    }
}
