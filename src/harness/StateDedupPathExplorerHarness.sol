// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ParameterizedPathExplorerHarness} from "./ParameterizedPathExplorerHarness.sol";

/// @notice Breadth-first explorer that keeps one shortest representative path per state hash.
/// @dev Correct pruning requires `_stateHash()` to include every modeled value that can affect future behavior.
abstract contract StateDedupPathExplorerHarness is ParameterizedPathExplorerHarness {
    uint256 internal constant MAX_UNIQUE_STATES = 4_096;
    uint256 internal constant MAX_ATTEMPTED_TRANSITIONS = 65_536;

    struct DedupSearchResult {
        bool found;
        StepInput[] path;
        uint256 attemptedTransitions;
        uint256 uniqueStates;
        uint256 prunedStates;
    }

    struct SearchStats {
        uint256 attemptedTransitions;
        uint256 seenCount;
        uint256 prunedStates;
        uint256 nextCount;
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

        bytes32[] memory seenHashes = new bytes32[](MAX_UNIQUE_STATES);
        bytes[] memory frontier = new bytes[](MAX_UNIQUE_STATES);
        SearchStats memory stats;

        _resetTarget();
        seenHashes[0] = _stateHash();
        stats.seenCount = 1;
        frontier[0] = abi.encode(new StepInput[](0));
        uint256 frontierCount = 1;

        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            bytes[] memory nextFrontier = new bytes[](MAX_UNIQUE_STATES);
            stats.nextCount = 0;

            for (uint256 parentIndex = 0; parentIndex < frontierCount; parentIndex++) {
                StepInput[] memory parentPath = abi.decode(frontier[parentIndex], (StepInput[]));
                StepInput[] memory violatingPath = _expandParent(
                    parentPath, stepCaseCount, depth, seenHashes, nextFrontier, stats
                );

                if (violatingPath.length > 0) {
                    return DedupSearchResult({
                        found: true,
                        path: violatingPath,
                        attemptedTransitions: stats.attemptedTransitions,
                        uniqueStates: stats.seenCount,
                        prunedStates: stats.prunedStates
                    });
                }
            }

            frontier = nextFrontier;
            frontierCount = stats.nextCount;
            if (frontierCount == 0) {
                break;
            }
        }

        return DedupSearchResult({
            found: false,
            path: new StepInput[](0),
            attemptedTransitions: stats.attemptedTransitions,
            uniqueStates: stats.seenCount,
            prunedStates: stats.prunedStates
        });
    }

    function _expandParent(
        StepInput[] memory parentPath,
        uint16 stepCaseCount,
        uint8 depth,
        bytes32[] memory seenHashes,
        bytes[] memory nextFrontier,
        SearchStats memory stats
    ) internal returns (StepInput[] memory violatingPath) {
        for (uint16 caseIndex = 0; caseIndex < stepCaseCount; caseIndex++) {
            _resetTarget();
            require(_replayAcceptedPrefix(parentPath), "replay drift");

            require(
                stats.attemptedTransitions < MAX_ATTEMPTED_TRANSITIONS,
                "transition budget"
            );
            StepInput memory candidateStep = _stepCase(caseIndex);
            stats.attemptedTransitions++;
            if (!_executeStep(candidateStep)) {
                continue;
            }

            StepInput[] memory childPath = _appendStep(parentPath, candidateStep);
            if (!_invariantHolds()) {
                return childPath;
            }

            bytes32 stateHash = _stateHash();
            if (_containsHash(seenHashes, stats.seenCount, stateHash)) {
                stats.prunedStates++;
                emit EquivalentStatePruned(stateHash, depth, stats.prunedStates);
                continue;
            }

            require(stats.seenCount < MAX_UNIQUE_STATES, "unique state cap");
            require(stats.nextCount < MAX_UNIQUE_STATES, "frontier state cap");
            seenHashes[stats.seenCount] = stateHash;
            stats.seenCount++;
            nextFrontier[stats.nextCount] = abi.encode(childPath);
            stats.nextCount++;
            emit UniqueStateDiscovered(stateHash, depth, stats.seenCount);
        }

        return new StepInput[](0);
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

    /// @notice Hash the complete modeled state that determines future behavior.
    function _stateHash() internal view virtual returns (bytes32);
}
