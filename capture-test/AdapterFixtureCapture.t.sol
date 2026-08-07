// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AdapterFixtureMachine} from "../src/examples/AdapterFixtureMachine.sol";
import {ForkAdapterTemplate} from "../src/harness/ForkAdapterTemplate.sol";
import {DirectResultCaptureHarness} from "../src/harness/DirectResultCaptureHarness.sol";

contract AdapterFixtureCaptureTest is ForkAdapterTemplate, DirectResultCaptureHarness {
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

    function test_CaptureExplorerResult() public {
        DedupSearchResult memory result = _exploreUniqueStates(CASE_COUNT, 4);
        assert(result.found);
        assert(result.path.length == 3);
        assert(result.attemptedTransitions == 6);

        CaptureStep[] memory captured = new CaptureStep[](result.path.length);
        _resetTarget();

        for (uint256 i = 0; i < result.path.length; i++) {
            StepInput memory step = result.path[i];
            uint256 prePhase = machine.phase();
            bool accepted = _executeStep(step);
            assert(accepted);
            uint256 postPhase = machine.phase();

            captured[i] = CaptureStep({
                actionId: _actionIdFor(step),
                includeParameter: false,
                parameter: step.parameter,
                preState: string.concat("phase=", _uintToString(prePhase)),
                postState: string.concat("phase=", _uintToString(postPhase)),
                effect: _effectFor(i)
            });
        }

        assert(!_invariantHolds());

        CaptureMetadata memory metadata = CaptureMetadata({
            adapterId: "adapter-fixture-v0.8",
            scopeId: "local-v0.8-fixture",
            manifestSha256: vmFork.envString("CGQA_MANIFEST_SHA256"),
            findingId: "CGQA-005",
            invariantId: "adapter-terminal-state",
            replay: "forge test --match-test test_AdapterPreservesMinimalViolatingPathWithDedup -vvv",
            exploredCandidates: result.attemptedTransitions,
            notes: "This explorer-result fixture corresponds to the local v0.7 adapter regression and is used only to verify deterministic manifest-to-finding export."
        });

        _writeExplorerResult("results/generated/CGQA-005.result.json", metadata, captured);
    }

    function _actionIdFor(StepInput memory step) internal pure returns (string memory) {
        if (step.action == ACTION_ADVANCE) return "advance";
        if (step.action == ACTION_NOOP) return "noop";
        revert("unknown capture action");
    }

    function _effectFor(uint256 index) internal pure returns (string memory) {
        if (index == 0) return "future-relevant protocol state changes";
        if (index == 1) return "second unique protocol state is reached";
        if (index == 2) return "terminal invariant becomes false";
        revert("unknown capture step");
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
