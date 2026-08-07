// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {AdapterFixtureMachine} from "../src/examples/AdapterFixtureMachine.sol";
import {ForkAdapterTemplate} from "../src/harness/ForkAdapterTemplate.sol";
import {MultiInvariantStateExplorerHarness} from "../src/harness/MultiInvariantStateExplorerHarness.sol";
import {DirectEngagementCaptureHarness} from "../src/harness/DirectEngagementCaptureHarness.sol";

contract EngagementFixtureCaptureTest is
    ForkAdapterTemplate,
    MultiInvariantStateExplorerHarness,
    DirectEngagementCaptureHarness
{
    uint8 internal constant ACTION_NOOP = 0;
    uint8 internal constant ACTION_ADVANCE = 1;
    uint16 internal constant CASE_COUNT = 2;
    uint16 internal constant INVARIANT_COUNT = 3;

    AdapterFixtureMachine internal machine;

    function setUp() public {
        machine = new AdapterFixtureMachine();
        ForkContext memory localContext = ForkContext({
            forkId: 0,
            scopeHash: keccak256("local-v1.3-engagement-capture-scope"),
            target: address(machine),
            chainId: block.chainid,
            blockNumber: block.number
        });
        _bindAdapterContext(localContext);
    }

    function test_CaptureMultiInvariantEngagementResult() public {
        MultiInvariantSearchResult memory result = _exploreAllInvariants(
            CASE_COUNT,
            4,
            INVARIANT_COUNT,
            MULTI_MAX_ATTEMPTED_TRANSITIONS,
            MULTI_MAX_UNIQUE_STATES
        );

        assert(result.completedBound);
        assert(result.attemptedTransitions == 8);
        assert(result.outcomes.length == 3);
        assert(result.outcomes[0].status == InvariantOutcomeStatus.Violated);
        assert(result.outcomes[0].path.length == 3);
        assert(result.outcomes[0].exploredCandidates == 6);
        assert(result.outcomes[1].status == InvariantOutcomeStatus.NotFoundWithinBound);
        assert(result.outcomes[1].exploredCandidates == 8);
        assert(result.outcomes[2].status == InvariantOutcomeStatus.Inconclusive);
        assert(result.outcomes[2].exploredCandidates == 8);

        EngagementCheckCapture[] memory checks = new EngagementCheckCapture[](3);
        checks[0] = EngagementCheckCapture({
            invariantId: "terminal-state-bound",
            status: "violated",
            includeFindingId: true,
            findingId: "CGQA-E-001-F01",
            exploredCandidates: result.outcomes[0].exploredCandidates,
            notes: "The repository-local fixture reaches the modeled terminal state through the shortest three-step advance path.",
            path: _captureObservedPath(result.outcomes[0].path)
        });
        checks[1] = EngagementCheckCapture({
            invariantId: "phase-nonnegative",
            status: "not_found_within_bound",
            includeFindingId: false,
            findingId: "",
            exploredCandidates: result.outcomes[1].exploredCandidates,
            notes: "No negative phase was found within the declared local action corpus and maxDepth=4 bounded model.",
            path: new CaptureStep[](0)
        });
        checks[2] = EngagementCheckCapture({
            invariantId: "budget-sensitive-branch",
            status: "inconclusive",
            includeFindingId: false,
            findingId: "",
            exploredCandidates: result.outcomes[2].exploredCandidates,
            notes: "The local evaluator intentionally returns inconclusive so unresolved evidence is not presented as a clean check.",
            path: new CaptureStep[](0)
        });

        EngagementCaptureMetadata memory metadata = EngagementCaptureMetadata({
            engagementId: "CGQA-E-001",
            adapterId: "engagement-fixture-v1.3",
            scopeId: "local-v1.3-engagement-fixture",
            manifestSha256: vmFork.envString("CGQA_ENGAGEMENT_MANIFEST_SHA256"),
            searchRunId: "local-engagement-search-001",
            replay: "forge test --match-test test_CaptureMultiInvariantEngagementResult -vvv"
        });

        _writeEngagementResult(
            vmFork.envString("CGQA_ENGAGEMENT_RESULT_PATH"), metadata, checks
        );
    }

    function _captureObservedPath(StepInput[] memory path)
        internal
        returns (CaptureStep[] memory captured)
    {
        captured = new CaptureStep[](path.length);
        _resetTarget();
        for (uint256 i = 0; i < path.length; i++) {
            uint256 prePhase = machine.phase();
            bool accepted = _executeStep(path[i]);
            assert(accepted);
            uint256 postPhase = machine.phase();
            captured[i] = CaptureStep({
                actionId: _actionIdFor(path[i]),
                includeParameter: false,
                parameter: path[i].parameter,
                preState: string.concat("phase=", _uintToString(prePhase)),
                postState: string.concat("phase=", _uintToString(postPhase)),
                effect: _effectFor(i)
            });
        }
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

    function _actionIdFor(StepInput memory step) internal pure returns (string memory) {
        if (step.action == ACTION_ADVANCE) return "advance";
        if (step.action == ACTION_NOOP) return "noop";
        revert("unknown capture action");
    }

    function _effectFor(uint256 index) internal pure returns (string memory) {
        if (index == 0) return "first future-relevant protocol state is reached";
        if (index == 1) return "second future-relevant protocol state is reached";
        if (index == 2) return "terminal-state invariant becomes false";
        revert("unknown capture step");
    }

    function _resetTarget() internal override {
        machine.reset();
    }

    function _stepCase(uint16 caseIndex)
        internal
        pure
        override
        returns (StepInput memory step)
    {
        if (caseIndex == 0) return StepInput({action: ACTION_NOOP, parameter: 0});
        if (caseIndex == 1) return StepInput({action: ACTION_ADVANCE, parameter: 0});
        revert("unknown case");
    }

    function _executeStep(StepInput memory step)
        internal
        override
        returns (bool accepted)
    {
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

    // Legacy single-invariant hook required by ForkAdapterTemplate; v1.3 capture uses `_evaluateInvariant`.
    function _invariantHolds() internal pure override returns (bool) {
        return true;
    }

    function _stateHash() internal view override returns (bytes32) {
        return _multiStateHash();
    }

    function _multiStateHash() internal view override returns (bytes32) {
        return _forkAdapterStateHash(keccak256(abi.encode(machine.phase())));
    }
}
