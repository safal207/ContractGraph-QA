// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Fail-closed authorization metadata for fork-based QA runs.
library ForkAuthorization {
    struct Scope {
        string scopeId;
        string authorizationReference;
        uint256 chainId;
        address target;
        uint256 blockNumber;
        bool confirmed;
    }

    function validate(Scope memory scope) internal pure returns (bytes32 scopeHash) {
        require(scope.confirmed, "authorization not confirmed");
        require(bytes(scope.scopeId).length > 0, "scope id missing");
        require(bytes(scope.authorizationReference).length > 0, "authorization ref missing");
        require(scope.chainId > 0, "chain id missing");
        require(scope.target != address(0), "target missing");
        require(scope.blockNumber > 0, "block number missing");

        scopeHash = keccak256(
            abi.encode(
                scope.scopeId,
                scope.authorizationReference,
                scope.chainId,
                scope.target,
                scope.blockNumber
            )
        );
    }
}
