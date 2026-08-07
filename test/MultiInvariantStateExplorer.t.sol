// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AdapterFixtureMachine} from "../src/examples/AdapterFixtureMachine.sol";
import {
    MultiInvariantStateExplorerHarness
} from "../src/harness/MultiInvariantStateExplorerHarness.sol";

contract MultiInvariantStateExplorerTest is MultiInvariantStateExplorerHarness {
    uint8 internal constant ACTION_NOOP = 0;
    uint8 internal constant ACTION_ADVANCE = 1;
    uint16 internal constant CASE_COUNT = 2;
    uint16 internal constant INVARIANT_COUNT = 3;

    AdapterFixtureMachine internal machine;

    function setUp() public {
        machine = new AdapterFixtureMachine();
    }

    function test_OneSearchClassifiesAllInvariantOutcomes() public {
        MultiInvariantSearchResult memory result =
            _exploreAllInvariants(CASE_COUNT, 4, INVARIANT_COUNT, 64, 32);

        assert(result.completedBound);
        assert(result.attemptedTransitions == 8);
        assert(result.uniqueStates == 4);
        assert(result.prunedStates == 5);

        assert(result.outcomes[0].status == InvariantOutcomeStatus.Violated);
        assert(result.outcomes[0].path.length == 3);
        assert(result.outcomes[0].exploredCandidates == 6);
        assert(result.outcomes[1].status == InvariantOutcomeStatus.NotFoundWithinBound);
        assert(result.outcomes[1].exploredCandidates == 8);
        assert(result.outcomes[2].status == InvariantOutcomeStatus.Inconclusive);
        assert(result.outcomes[2].exploredCandidates == 8);
    }

    function test_IncompleteSearchFailsClosedToInconclusive() public {
        MultiInvariantSearchResult memory result =
            _exploreAllInvariants(CASE_COUNT, 4, INVARIANT_COUNT, 2, 32);

        assert(!result.completedBound);
        assert(result.attemptedTransitions == 2);
        assert(result.outcomes[0].status == InvariantOutcomeStatus.Inconclusive);
        assert(result.outcomes[1].status == InvariantOutcomeStatus.Inconclusive);
        assert(result.outcomes[2].status == InvariantOutcomeStatus.Inconclusive);
    }

    function _evaluateInvariant(uint256 invariantIndex)
        internal
        view
        override
        returns (InvariantEvaluation)
    {
        if (invariantIndex == 0) {
            return machine.phase() < 3 ? InvariantEvaluation.Holds : InvariantEvaluation.Violated;
        }
        if (invariantIndex == 1) return InvariantEvaluation.Holds;
        if (invariantIndex == 2) return InvariantEvaluation.Inconclusive;
        revert("unknown invariant");
    }

    function _resetTarget() internal override {
        machine.reset();
    }

    function _stepCase(uint16 caseIndex) internal pure override returns (StepInput memory step) {
        if (caseIndex == 0) return StepInput({action: ACTION_NOOP, parameter: 0});
        if (caseIndex == 1) return StepInput({action: ACTION_ADVANCE, parameter: 0});
        revert("unknown case");
    }

    function _executeStep(StepInput memory step) internal override returns (bool accepted) {
        bytes memory callData;
        if (step.action == ACTION_NOOP) {
            callData = abi.encodeWithSelector(AdapterFixtureMachine.noop.selector);
        } else if (step.action == ACTION_ADVANCE) {
            callData = abi.encodeWithSelector(AdapterFixtureMachine.advance.selector);
        } else {
            return false;
        }
        (accepted,) = address(machine).call(callData);
    }

    function _invariantHolds() internal pure override returns (bool) {
        return true;
    }

    function _multiStateHash() internal view override returns (bytes32) {
        return keccak256(abi.encode(machine.phase()));
    }
}
