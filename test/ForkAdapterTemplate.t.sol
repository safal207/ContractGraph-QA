// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AdapterFixtureMachine} from "../src/examples/AdapterFixtureMachine.sol";
import {ForkAdapterTemplate} from "../src/harness/ForkAdapterTemplate.sol";

contract ForkAdapterTemplateTest is ForkAdapterTemplate {
    uint8 internal constant ACTION_NOOP = 0;
    uint8 internal constant ACTION_ADVANCE = 1;
    uint16 internal constant CASE_COUNT = 2;

    AdapterFixtureMachine internal machine;

    function setUp() public {
        machine = new AdapterFixtureMachine();

        ForkContext memory localContext = ForkContext({
            forkId: 0,
            scopeHash: keccak256("local-adapter-fixture-scope"),
            target: address(machine),
            chainId: block.chainid,
            blockNumber: block.number
        });
        _bindAdapterContext(localContext);
    }

    function test_AdapterPreservesMinimalViolatingPathWithDedup() public {
        DedupSearchResult memory result = _exploreUniqueStates(CASE_COUNT, 4);

        assert(result.found);
        assert(result.path.length == 3);
        assert(result.path[0].action == ACTION_ADVANCE);
        assert(result.path[1].action == ACTION_ADVANCE);
        assert(result.path[2].action == ACTION_ADVANCE);
        assert(result.attemptedTransitions == 6);
        assert(result.uniqueStates == 3);
        assert(result.prunedStates == 3);

        bool invariantHoldsAfterReplay = _replayCases(result.path);
        assert(!invariantHoldsAfterReplay);
        assert(machine.phase() == 3);
    }

    function test_StateHashBindsProtocolStateToForkProvenance() public {
        _resetTarget();
        bytes32 initial = _stateHash();

        machine.advance();
        bytes32 advanced = _stateHash();

        assert(initial != bytes32(0));
        assert(advanced != bytes32(0));
        assert(initial != advanced);
        assert(_adapterTarget() == address(machine));
        assert(_adapterScopeHash() == keccak256("local-adapter-fixture-scope"));
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

    function _invariantHolds() internal view override returns (bool) {
        return machine.terminalInvariantHolds();
    }

    function _stateHash() internal view override returns (bytes32) {
        bytes32 protocolStateHash = keccak256(abi.encode(machine.phase()));
        return _forkAdapterStateHash(protocolStateHash);
    }
}
