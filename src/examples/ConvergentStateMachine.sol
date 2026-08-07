// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Local deterministic fixture with multiple actions converging to the same state.
contract ConvergentStateMachine {
    uint8 public phase;

    function noopA() external {}

    function noopB() external {}

    function advance() external {
        if (phase < 3) {
            phase++;
        }
    }

    function terminalInvariantHolds() external view returns (bool) {
        return phase < 3;
    }
}
