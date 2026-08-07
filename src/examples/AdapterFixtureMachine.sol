// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Local-only deterministic fixture used to validate the adapter template in default CI.
contract AdapterFixtureMachine {
    uint8 public phase;

    function reset() external {
        phase = 0;
    }

    function noop() external {}

    function advance() external {
        if (phase < 3) {
            phase++;
        }
    }

    function terminalInvariantHolds() external view returns (bool) {
        return phase < 3;
    }
}
