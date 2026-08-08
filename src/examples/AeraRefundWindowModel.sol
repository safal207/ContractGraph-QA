// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title AeraRefundWindowModel
/// @notice Minimal independent model of the temporal relationship between a sync-deposit refund window
/// and a receiver's transfer lock as observed in Aera V3 ProvisionerV2 / MultiDepositorVault.
/// @dev This is NOT Aera source code and is NOT a vulnerability claim. It models only the state variables
/// needed to test one temporal hypothesis against a pinned public source snapshot.
contract AeraRefundWindowModel {
    uint32 internal constant LONG_REFUND_TIMEOUT = 10;
    uint32 internal constant SHORT_REFUND_TIMEOUT = 1;
    uint256 internal constant TIME_STEP = 2;

    uint256 public nowTs;
    uint32 public depositRefundTimeout;
    uint256 public userUnitsRefundableUntil;
    bool public firstDepositActive;
    uint256 public firstDepositRefundableUntil;
    uint256 public depositCount;

    constructor() {
        _reset();
    }

    function reset() external {
        _reset();
    }

    /// @notice Models a synchronous deposit.
    /// @dev The model intentionally uses direct assignment for the receiver lock because the pinned
    /// ProvisionerV2 source does the same in _syncDeposit.
    function syncDeposit() external {
        uint256 refundableUntil = nowTs + depositRefundTimeout;

        if (!firstDepositActive) {
            firstDepositActive = true;
            firstDepositRefundableUntil = refundableUntil;
        }

        userUnitsRefundableUntil = refundableUntil;
        depositCount++;
    }

    /// @notice Models an authorized configuration change that decreases the refund timeout.
    /// @dev This action is explicitly privileged in the real contract and therefore makes any bounty
    /// relevance of the modeled path inconclusive until scope/impact are independently established.
    function configureShorterRefundTimeout() external {
        depositRefundTimeout = SHORT_REFUND_TIMEOUT;
    }

    function advanceTime() external {
        nowTs += TIME_STEP;
    }

    function firstRefundWindowOpen() external view returns (bool) {
        return firstDepositActive && firstDepositRefundableUntil >= nowTs;
    }

    function unitsLocked() external view returns (bool) {
        return userUnitsRefundableUntil >= nowTs;
    }

    function temporalLockInvariantHolds() external view returns (bool) {
        if (!firstDepositActive || firstDepositRefundableUntil < nowTs) return true;
        return userUnitsRefundableUntil >= nowTs;
    }

    function _reset() internal {
        nowTs = 0;
        depositRefundTimeout = LONG_REFUND_TIMEOUT;
        userUnitsRefundableUntil = 0;
        firstDepositActive = false;
        firstDepositRefundableUntil = 0;
        depositCount = 0;
    }
}
