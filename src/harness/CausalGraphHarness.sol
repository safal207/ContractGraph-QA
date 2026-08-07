// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

abstract contract CausalGraphHarness {
    uint256 public graphStep;

    event TransitionObserved(
        uint256 indexed step,
        bytes32 indexed cause,
        address indexed actor,
        bytes32 action,
        bytes32 preState,
        bytes32 postState,
        uint256 timestamp,
        bytes32 effect
    );

    function _recordTransition(
        bytes32 cause,
        address actor,
        bytes32 action,
        bytes32 preState,
        bytes32 postState,
        bytes32 effect
    ) internal {
        unchecked {
            graphStep++;
        }

        emit TransitionObserved(
            graphStep,
            cause,
            actor,
            action,
            preState,
            postState,
            block.timestamp,
            effect
        );
    }

    function _stateId(string memory label) internal pure returns (bytes32) {
        return keccak256(bytes(label));
    }

    function _actionId(string memory label) internal pure returns (bytes32) {
        return keccak256(bytes(label));
    }
}
