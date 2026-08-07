// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Breadth-first action-sequence explorer for deterministic smart-contract QA models.
/// @dev A concrete test harness provides target reset, action execution and invariant checks.
abstract contract PathExplorerHarness {
    struct SearchResult {
        bool found;
        uint8[] path;
        uint256 exploredCandidates;
    }

    event PathCandidate(uint256 indexed candidate, uint256 depth);
    event PathStep(uint256 indexed step, uint8 indexed action, bool accepted, bool invariantHolds);
    event ViolatingPathFound(uint256 depth, uint256 exploredCandidates);

    /// @notice Explore all action sequences in breadth-first order up to maxDepth.
    /// @dev The first violation found is minimal by action count.
    function _explore(uint8 actionCount, uint8 maxDepth)
        internal
        returns (SearchResult memory result)
    {
        require(actionCount > 0, "actionCount=0");
        require(maxDepth > 0, "maxDepth=0");

        uint256 explored;

        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            uint256 candidates = _pow(actionCount, depth);

            for (uint256 candidate = 0; candidate < candidates; candidate++) {
                explored++;
                emit PathCandidate(candidate, depth);

                _resetTarget();
                uint8[] memory path = _decodePath(candidate, actionCount, depth);

                for (uint256 step = 0; step < path.length; step++) {
                    bool accepted = _executeAction(path[step]);
                    bool invariantHolds = _invariantHolds();
                    emit PathStep(step, path[step], accepted, invariantHolds);

                    if (!accepted) {
                        break;
                    }

                    if (!invariantHolds) {
                        uint8[] memory minimalPath = _prefix(path, step + 1);
                        emit ViolatingPathFound(minimalPath.length, explored);
                        return SearchResult({
                            found: true, path: minimalPath, exploredCandidates: explored
                        });
                    }
                }
            }
        }

        return SearchResult({found: false, path: new uint8[](0), exploredCandidates: explored});
    }

    /// @notice Deterministically replay a previously discovered path against a fresh target.
    function _replay(uint8[] memory path) internal returns (bool invariantHolds) {
        _resetTarget();

        for (uint256 step = 0; step < path.length; step++) {
            bool accepted = _executeAction(path[step]);
            bool holds = _invariantHolds();
            emit PathStep(step, path[step], accepted, holds);

            if (!accepted) {
                return true;
            }

            if (!holds) {
                return false;
            }
        }

        return _invariantHolds();
    }

    function _decodePath(uint256 candidate, uint8 actionCount, uint8 depth)
        internal
        pure
        returns (uint8[] memory path)
    {
        path = new uint8[](depth);

        for (uint256 i = depth; i > 0; i--) {
            path[i - 1] = uint8(candidate % actionCount);
            candidate /= actionCount;
        }
    }

    function _prefix(uint8[] memory path, uint256 length)
        internal
        pure
        returns (uint8[] memory prefix)
    {
        prefix = new uint8[](length);
        for (uint256 i = 0; i < length; i++) {
            prefix[i] = path[i];
        }
    }

    function _pow(uint256 base, uint256 exponent) internal pure returns (uint256 result) {
        result = 1;
        for (uint256 i = 0; i < exponent; i++) {
            result *= base;
        }
    }

    function _resetTarget() internal virtual;

    function _executeAction(uint8 action) internal virtual returns (bool accepted);

    function _invariantHolds() internal view virtual returns (bool);
}
