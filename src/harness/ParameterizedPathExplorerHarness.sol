// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Breadth-first explorer over a finite corpus of parameterized smart-contract steps.
/// @dev A step may represent a contract call, parameter choice, time jump, or another modeled input.
abstract contract ParameterizedPathExplorerHarness {
    struct StepInput {
        uint8 action;
        uint256 parameter;
    }

    struct SearchResult {
        bool found;
        StepInput[] path;
        uint256 exploredCandidates;
    }

    event ParameterizedPathCandidate(uint256 indexed candidate, uint256 depth);
    event ParameterizedPathStep(
        uint256 indexed step,
        uint8 indexed action,
        uint256 parameter,
        bool accepted,
        bool invariantHolds
    );
    event ParameterizedViolatingPathFound(uint256 depth, uint256 exploredCandidates);

    /// @notice Explore all sequences from a finite parameterized step corpus up to maxDepth.
    /// @dev Breadth-first ordering makes the first violation minimal by step count.
    function _exploreCases(uint16 stepCaseCount, uint8 maxDepth)
        internal
        returns (SearchResult memory result)
    {
        require(stepCaseCount > 0, "stepCaseCount=0");
        require(maxDepth > 0, "maxDepth=0");

        uint256 explored;

        for (uint8 depth = 1; depth <= maxDepth; depth++) {
            uint256 candidates = _pow(stepCaseCount, depth);

            for (uint256 candidate = 0; candidate < candidates; candidate++) {
                explored++;
                emit ParameterizedPathCandidate(candidate, depth);

                _resetTarget();
                StepInput[] memory path = _decodeCasePath(candidate, stepCaseCount, depth);

                for (uint256 step = 0; step < path.length; step++) {
                    bool accepted = _executeStep(path[step]);
                    bool invariantHolds = _invariantHolds();
                    emit ParameterizedPathStep(
                        step,
                        path[step].action,
                        path[step].parameter,
                        accepted,
                        invariantHolds
                    );

                    if (!accepted) {
                        break;
                    }

                    if (!invariantHolds) {
                        StepInput[] memory minimalPath = _prefix(path, step + 1);
                        emit ParameterizedViolatingPathFound(minimalPath.length, explored);
                        return SearchResult({
                            found: true, path: minimalPath, exploredCandidates: explored
                        });
                    }
                }
            }
        }

        return SearchResult({
            found: false,
            path: new StepInput[](0),
            exploredCandidates: explored
        });
    }

    /// @notice Deterministically replay a discovered parameterized path against a fresh target.
    function _replayCases(StepInput[] memory path) internal returns (bool invariantHolds) {
        _resetTarget();

        for (uint256 step = 0; step < path.length; step++) {
            bool accepted = _executeStep(path[step]);
            bool holds = _invariantHolds();
            emit ParameterizedPathStep(
                step,
                path[step].action,
                path[step].parameter,
                accepted,
                holds
            );

            if (!accepted) {
                return true;
            }

            if (!holds) {
                return false;
            }
        }

        return _invariantHolds();
    }

    function _decodeCasePath(uint256 candidate, uint16 stepCaseCount, uint8 depth)
        internal
        view
        returns (StepInput[] memory path)
    {
        path = new StepInput[](depth);

        for (uint256 i = depth; i > 0; i--) {
            uint16 caseIndex = uint16(candidate % stepCaseCount);
            path[i - 1] = _stepCase(caseIndex);
            candidate /= stepCaseCount;
        }
    }

    function _prefix(StepInput[] memory path, uint256 length)
        internal
        pure
        returns (StepInput[] memory prefix)
    {
        prefix = new StepInput[](length);
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

    function _stepCase(uint16 caseIndex) internal view virtual returns (StepInput memory);

    function _executeStep(StepInput memory step) internal virtual returns (bool accepted);

    function _invariantHolds() internal view virtual returns (bool);
}
