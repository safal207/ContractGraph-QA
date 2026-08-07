// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ParameterizedPathExplorerHarness} from "./ParameterizedPathExplorerHarness.sol";

/// @notice Bounded breadth-first explorer that evaluates every declared invariant in one state-space walk.
/// @dev Equivalent-state pruning is sound only when `_multiStateHash()` is complete for future behavior.
abstract contract MultiInvariantStateExplorerHarness is ParameterizedPathExplorerHarness {
    uint256 internal constant MULTI_MAX_UNIQUE_STATES = 4_096;
    uint256 internal constant MULTI_MAX_ATTEMPTED_TRANSITIONS = 65_536;

    enum InvariantEvaluation {
        Holds,
        Violated,
        Inconclusive
    }

    enum InvariantOutcomeStatus {
        Unresolved,
        Violated,
        NotFoundWithinBound,
        Inconclusive
    }

    struct InvariantOutcome {
        InvariantOutcomeStatus status;
        StepInput[] path;
        uint256 exploredCandidates;
        bool sawInconclusive;
    }

    struct MultiInvariantSearchResult {
        InvariantOutcome[] outcomes;
        uint256 attemptedTransitions;
        uint256 uniqueStates;
        uint256 prunedStates;
        bool completedBound;
    }

    struct MultiSearchStats {
        uint256 attemptedTransitions;
        uint256 seenCount;
        uint256 prunedStates;
        uint256 nextCount;
        bool completedBound;
    }

    function _exploreAllInvariants(
        uint16 stepCaseCount,
        uint8 maxDepth,
        uint16 invariantCount,
        uint256 transitionBudget,
        uint256 uniqueStateBudget
    ) internal returns (MultiInvariantSearchResult memory result) {
        require(stepCaseCount > 0, "stepCaseCount=0");
        require(maxDepth > 0, "maxDepth=0");
        require(invariantCount > 0, "invariantCount=0");
        require(transitionBudget > 0 && transitionBudget <= MULTI_MAX_ATTEMPTED_TRANSITIONS, "bad transition budget");
        require(uniqueStateBudget > 0 && uniqueStateBudget <= MULTI_MAX_UNIQUE_STATES, "bad state budget");

        InvariantOutcome[] memory outcomes = new InvariantOutcome[](invariantCount);
        bytes32[] memory seenHashes = new bytes32[](uniqueStateBudget);
        bytes[] memory frontier = new bytes[](uniqueStateBudget);
        MultiSearchStats memory stats;
        stats.completedBound = true;

        _resetTarget();
        seenHashes[0] = _multiStateHash();
        stats.seenCount = 1;
        frontier[0] = abi.encode(new StepInput[](0));
        uint256 frontierCount = 1;

        for (uint8 depth = 1; depth <= maxDepth && stats.completedBound; depth++) {
            bytes[] memory nextFrontier = new bytes[](uniqueStateBudget);
            stats.nextCount = 0;

            for (uint256 parentIndex = 0; parentIndex < frontierCount && stats.completedBound; parentIndex++) {
                StepInput[] memory parentPath = abi.decode(frontier[parentIndex], (StepInput[]));

                for (uint16 caseIndex = 0; caseIndex < stepCaseCount; caseIndex++) {
                    if (stats.attemptedTransitions >= transitionBudget) {
                        stats.completedBound = false;
                        break;
                    }

                    _resetTarget();
                    require(_multiReplayAcceptedPrefix(parentPath), "multi replay drift");

                    StepInput memory candidateStep = _stepCase(caseIndex);
                    stats.attemptedTransitions++;
                    if (!_executeStep(candidateStep)) continue;

                    StepInput[] memory childPath = _multiAppendStep(parentPath, candidateStep);
                    _evaluateAllInvariants(outcomes, childPath, stats.attemptedTransitions);

                    bytes32 stateHash = _multiStateHash();
                    if (_multiContainsHash(seenHashes, stats.seenCount, stateHash)) {
                        stats.prunedStates++;
                        continue;
                    }

                    if (stats.seenCount >= uniqueStateBudget || stats.nextCount >= uniqueStateBudget) {
                        stats.completedBound = false;
                        break;
                    }

                    seenHashes[stats.seenCount++] = stateHash;
                    nextFrontier[stats.nextCount++] = abi.encode(childPath);
                }
            }

            frontier = nextFrontier;
            frontierCount = stats.nextCount;
            if (frontierCount == 0) break;
        }

        for (uint256 i = 0; i < outcomes.length; i++) {
            if (outcomes[i].status == InvariantOutcomeStatus.Violated) continue;
            if (!stats.completedBound || outcomes[i].sawInconclusive) {
                outcomes[i].status = InvariantOutcomeStatus.Inconclusive;
            } else {
                outcomes[i].status = InvariantOutcomeStatus.NotFoundWithinBound;
            }
            outcomes[i].exploredCandidates = stats.attemptedTransitions;
        }

        return MultiInvariantSearchResult({
            outcomes: outcomes,
            attemptedTransitions: stats.attemptedTransitions,
            uniqueStates: stats.seenCount,
            prunedStates: stats.prunedStates,
            completedBound: stats.completedBound
        });
    }

    function _evaluateAllInvariants(
        InvariantOutcome[] memory outcomes,
        StepInput[] memory path,
        uint256 exploredCandidates
    ) internal view {
        for (uint256 i = 0; i < outcomes.length; i++) {
            if (outcomes[i].status == InvariantOutcomeStatus.Violated) continue;

            InvariantEvaluation evaluation = _evaluateInvariant(i);
            if (evaluation == InvariantEvaluation.Violated) {
                outcomes[i].status = InvariantOutcomeStatus.Violated;
                outcomes[i].path = path;
                outcomes[i].exploredCandidates = exploredCandidates;
            } else if (evaluation == InvariantEvaluation.Inconclusive) {
                outcomes[i].sawInconclusive = true;
            }
        }
    }

    function _multiReplayAcceptedPrefix(StepInput[] memory path) internal returns (bool accepted) {
        for (uint256 i = 0; i < path.length; i++) {
            if (!_executeStep(path[i])) return false;
        }
        return true;
    }

    function _multiAppendStep(StepInput[] memory path, StepInput memory step)
        internal
        pure
        returns (StepInput[] memory extended)
    {
        extended = new StepInput[](path.length + 1);
        for (uint256 i = 0; i < path.length; i++) extended[i] = path[i];
        extended[path.length] = step;
    }

    function _multiContainsHash(bytes32[] memory hashes, uint256 count, bytes32 candidate)
        internal
        pure
        returns (bool)
    {
        for (uint256 i = 0; i < count; i++) {
            if (hashes[i] == candidate) return true;
        }
        return false;
    }

    function _evaluateInvariant(uint256 invariantIndex)
        internal
        view
        virtual
        returns (InvariantEvaluation);

    function _multiStateHash() internal view virtual returns (bytes32);
}
