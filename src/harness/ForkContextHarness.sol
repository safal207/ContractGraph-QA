// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ForkAuthorization} from "./ForkAuthorization.sol";

interface VmFork {
    function envString(string calldata name) external returns (string memory value);
    function envUint(string calldata name) external returns (uint256 value);
    function envAddress(string calldata name) external returns (address value);
    function createSelectFork(string calldata urlOrAlias, uint256 blockNumber)
        external
        returns (uint256 forkId);
}

/// @notice Opens a deterministic fork only after explicit authorization metadata is present.
abstract contract ForkContextHarness {
    string internal constant AUTHORIZED_RPC_ALIAS = "authorized";

    VmFork internal constant vmFork =
        VmFork(address(uint160(uint256(keccak256("hevm cheat code")))));

    struct ForkContext {
        uint256 forkId;
        bytes32 scopeHash;
        address target;
        uint256 chainId;
        uint256 blockNumber;
    }

    function _openAuthorizedForkFromEnv() internal returns (ForkContext memory context) {
        string memory confirmation = vmFork.envString("CGQA_AUTHORIZED");

        ForkAuthorization.Scope memory scope = ForkAuthorization.Scope({
            scopeId: vmFork.envString("CGQA_SCOPE_ID"),
            authorizationReference: vmFork.envString("CGQA_AUTHORIZATION_REFERENCE"),
            chainId: vmFork.envUint("CGQA_CHAIN_ID"),
            target: vmFork.envAddress("CGQA_TARGET"),
            blockNumber: vmFork.envUint("CGQA_BLOCK_NUMBER"),
            confirmed: keccak256(bytes(confirmation)) == keccak256(bytes("YES"))
        });

        bytes32 scopeHash = ForkAuthorization.validate(scope);
        uint256 forkId = vmFork.createSelectFork(AUTHORIZED_RPC_ALIAS, scope.blockNumber);

        require(block.chainid == scope.chainId, "chain mismatch");
        require(block.number == scope.blockNumber, "block mismatch");
        require(scope.target.code.length > 0, "target has no code");

        context = ForkContext({
            forkId: forkId,
            scopeHash: scopeHash,
            target: scope.target,
            chainId: scope.chainId,
            blockNumber: scope.blockNumber
        });
    }

    /// @notice Minimal read-only fingerprint for fork provenance, not a full future-state hash.
    function _forkSnapshotHash(address target) internal view returns (bytes32) {
        return
            keccak256(
                abi.encode(block.chainid, block.number, target, target.codehash, target.balance)
            );
    }
}
