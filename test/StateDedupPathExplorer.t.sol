// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ConvergentStateMachine} from "../src/examples/ConvergentStateMachine.sol";
import {StateDedupPathExplorerHarness} from "../src/harness/StateDedupPathExplorerHarness.sol";

contract StateDedupPathExplorerTest is StateDedupPathExplorerHarness {
    uint8 internal constant ACTION_NOOP_A = 0;
    uint8 internal constant ACTION_NOOP_B = 1;
    uint8 internal constant ACTION_ADVANCE = 2;

    uint16 internal constant CASE_COUNT = 3;

    bool internal enforceTerminalInvariant;
    ConvergentStateMachine internal machine;

    function test_DedupFindsMinimalViolation() public {
        enforceTerminalInvariant = true;

        DedupSearchResult memory result = _exploreUniqueStates(CASE_COUNT, 5);

        assert(result.found);
        assert(result.path.length == 3);
        assert(result.path[0].action == ACTION_ADVANCE);
        assert(result.path[1].action == ACTION_ADVANCE);
        assert(result.path[2].action == ACTION_ADVANCE);
        assert(result.attemptedTransitions == 9);
        assert(result.uniqueStates == 3);
        assert(result.prunedStates == 6);

        bool invariantHoldsAfterReplay = _replayCases(result.path);
        assert(!invariantHoldsAfterReplay);
        assert(machine.phase() == 3);
    }

    function test_DedupCollapsesEquivalentStateSpace() public {
        enforceTerminalInvariant = false;

        DedupSearchResult memory result = _exploreUniqueStates(CASE_COUNT, 5);

        assert(!result.found);
        assert(result.path.length == 0);
        assert(result.attemptedTransitions == 12);
        assert(result.uniqueStates == 4);
        assert(result.prunedStates == 9);
        assert(result.attemptedTransitions < _exhaustiveCandidateCount(CASE_COUNT, 5));
    }

    function _resetTarget() internal override {
        machine = new ConvergentStateMachine();
    }

    function _stepCase(uint16 caseIndex) internal pure override returns (StepInput memory step) {
        if (caseIndex == 0) return StepInput({action: ACTION_NOOP_A, parameter: 0});
        if (caseIndex == 1) return StepInput({action: ACTION_NOOP_B, parameter: 0});
        if (caseIndex == 2) return StepInput({action: ACTION_ADVANCE, parameter: 0});
        revert("unknown case");
    }

    function _executeStep(StepInput memory step) internal override returns (bool accepted) {
        bytes memory callData;
        if (step.action == ACTION_NOOP_A) {
            callData = abi.encodeWithSelector(ConvergentStateMachine.noopA.selector);
        } else if (step.action == ACTION_NOOP_B) {
            callData = abi.encodeWithSelector(ConvergentStateMachine.noopB.selector);
        } else if (step.action == ACTION_ADVANCE) {
            callData = abi.encodeWithSelector(ConvergentStateMachine.advance.selector);
        } else {
            return false;
        }

        (accepted,) = address(machine).call(callData);
    }

    function _invariantHolds() internal view override returns (bool) {
        if (!enforceTerminalInvariant) {
            return true;
        }
        return machine.terminalInvariantHolds();
    }

    function _stateHash() internal view override returns (bytes32) {
        return keccak256(abi.encode(machine.phase()));
    }

    function _exhaustiveCandidateCount(uint16 branching, uint8 maxDepth)
        internal
        pure
        returns (uint256 total)
    {
        uint256 layer = 1;
        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            layer *= branching;
            total += layer;
        }
    }
}
