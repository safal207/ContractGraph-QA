// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ParameterizedPathExplorerHarness} from "./ParameterizedPathExplorerHarness.sol";

/// @notice Breadth-first explorer that keeps one shortest representative path per state hash.
/// @dev Correct pruning requires `_stateHash()` to include every modeled value that can affect future behavior.
abstract contract StateDedupPathExplorerHarness is ParameterizedPathExplorerHarness {
    uint256 internal constant MAX_SEARCH_STATES = 4_096;

    struct DedupSearchResult {
        bool found;
        StepInput[] path;
        uint256 attemptedTransitions;
        uint256 uniqueStates;
        uint256 prunedStates;
    }

    event UniqueStateDiscovered(bytes32 indexed stateHash, uint256 depth, uint256 uniqueStates);
    event EquivalentStatePruned(bytes32 indexed stateHash, uint256 depth, uint256 prunedStates);

    /// @notice Explore a finite parameterized step corpus while pruning equivalent reachable states.
    /// @dev Breadth-first traversal preserves a shortest representative path for every discovered hash.
    function _exploreUniqueStates(uint16 stepCaseCount, uint8 maxDepth)
        internal
        returns (DedupSearchResult memory result)
    {
        require(stepCaseCount > 0, "stepCaseCount=0");
        require(maxDepth > 0, "maxDepth=0");

        uint256 capacity = _boundedSearchCapacity(stepCaseCount, maxDepth);
        bytes32[] memory seenHashes = new bytes32[](capacity + 1);
        bytes[] memory frontier = new bytes[](capacity + 1);

        _resetTarget();
        bytes32 initialHash = _stateHash();
        seenHashes[0] = initialHash;
        uint256 seenCount = 1;
        frontier[0] = abi.encode(new StepInput[](0));
        uint256 frontierCount = 1;

        uint256 attemptedTransitions;
        uint256 prunedStates;

        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            bytes[] memory nextFrontier = new bytes[](capacity + 1);
            uint256 nextCount;

            for (uint256 parentIndex = 0; parentIndex < frontierCount; parentIndex++) {
                StepInput[] memory parentPath = abi.decode(frontier[parentIndex], (StepInput[]));

                for (uint16 caseIndex = 0; caseIndex < stepCaseCount; caseIndex++) {
                    _resetTarget();
                    require(_replayAcceptedPrefix(parentPath), "replay drift");

                    StepInput memory candidateStep = _stepCase(caseIndex);
                    attemptedTransitions++;
                    bool accepted = _executeStep(candidateStep);
                    if (!accepted) {
                        continue;
                    }

                    StepInput[] memory childPath = _appendStep(parentPath, candidateStep);
                    if (!_invariantHolds()) {
                        return DedupSearchResult({
                            found: true,
                            path: childPath,
                            attemptedTransitions: attemptedTransitions,
                            uniqueStates: seenCount,
                            prunedStates: prunedStates
                        });
                    }

                    bytes32 stateHash = _stateHash();
                    if (_containsHash(seenHashes, seenCount, stateHash)) {
                        prunedStates++;
                        emit EquivalentStatePruned(stateHash, depth, prunedStates);
                        continue;
                    }

                    seenHashes[seenCount] = stateHash;
                    seenCount++;
                    nextFrontier[nextCount] = abi.encode(childPath);
                    nextCount++;
                    emit UniqueStateDiscovered(stateHash, depth, seenCount);
                }
            }

            frontier = nextFrontier;
            frontierCount = nextCount;
            if (frontierCount == 0) {
                break;
            }
        }

        return DedupSearchResult({
            found: false,
            path: new StepInput[](0),
            attemptedTransitions: attemptedTransitions,
            uniqueStates: seenCount,
            prunedStates: prunedStates
        });
    }

    function _replayAcceptedPrefix(StepInput[] memory path) internal returns (bool accepted) {
        for (uint256 step = 0; step < path.length; step++) {
            if (!_executeStep(path[step])) {
                return false;
            }
        }
        return true;
    }

    function _appendStep(StepInput[] memory path, StepInput memory step)
        internal
        pure
        returns (StepInput[] memory extended)
    {
        extended = new StepInput[](path.length + 1);
        for (uint256 i = 0; i < path.length; i++) {
            extended[i] = path[i];
        }
        extended[path.length] = step;
    }

    function _containsHash(bytes32[] memory hashes, uint256 count, bytes32 candidate)
        internal
        pure
        returns (bool)
    {
        for (uint256 i = 0; i < count; i++) {
            if (hashes[i] == candidate) {
                return true;
            }
        }
        return false;
    }

    function _boundedSearchCapacity(uint16 stepCaseCount, uint8 maxDepth)
        internal
        pure
        returns (uint256 total)
    {
        uint256 layerSize = 1;
        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            layerSize *= stepCaseCount;
            total += layerSize;
            require(total <= MAX_SEARCH_STATES, "search state cap");
        }
    }

    /// @notice Hash the complete modeled state that determines future behavior.
    function _stateHash() internal view virtual returns (bytes32);
}
