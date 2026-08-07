// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ForkContextHarness} from "./ForkContextHarness.sol";
import {StateDedupPathExplorerHarness} from "./StateDedupPathExplorerHarness.sol";

/// @notice Base class for contract-specific QA adapters on an explicitly authorized fixed-block fork.
/// @dev Concrete adapters define actions, parameters, invariants, and the complete future-relevant protocol state hash.
abstract contract ForkAdapterTemplate is ForkContextHarness, StateDedupPathExplorerHarness {
    ForkContext internal adapterForkContext;
    bool internal adapterInitialized;

    event ForkAdapterBound(
        bytes32 indexed scopeHash, address indexed target, uint256 chainId, uint256 blockNumber
    );

    /// @notice Open and bind the explicitly authorized fork declared by the v0.6 environment contract.
    function _initializeAuthorizedAdapterFromEnv() internal returns (ForkContext memory context) {
        context = _openAuthorizedForkFromEnv();
        _bindAdapterContext(context);
    }

    /// @notice Bind a previously validated fork context to this adapter.
    /// @dev Production adapters should bind only a context returned by `_openAuthorizedForkFromEnv()`.
    function _bindAdapterContext(ForkContext memory context) internal {
        require(context.scopeHash != bytes32(0), "scope hash missing");
        require(context.chainId > 0, "chain id missing");
        require(context.blockNumber > 0, "block number missing");
        require(context.target != address(0), "target missing");
        require(context.target.code.length > 0, "target has no code");

        adapterForkContext = context;
        adapterInitialized = true;

        emit ForkAdapterBound(
            context.scopeHash, context.target, context.chainId, context.blockNumber
        );
    }

    /// @notice Re-open the exact authorized fixed-block fork before replaying a candidate path.
    /// @dev Concrete fork adapters normally call this from `_resetTarget()` before actor/setup hooks.
    function _reopenAuthorizedForkBaseline() internal returns (ForkContext memory context) {
        _requireAdapterInitialized();

        uint256 forkId =
            vmFork.createSelectFork(AUTHORIZED_RPC_ALIAS, adapterForkContext.blockNumber);

        require(block.chainid == adapterForkContext.chainId, "chain mismatch");
        require(block.number == adapterForkContext.blockNumber, "block mismatch");
        require(adapterForkContext.target.code.length > 0, "target has no code");

        adapterForkContext.forkId = forkId;
        context = adapterForkContext;
    }

    /// @notice Bind a protocol-specific state digest to immutable fork provenance and authorization scope.
    /// @dev `protocolStateHash` must include every modeled value that can change future reachability.
    function _forkAdapterStateHash(bytes32 protocolStateHash) internal view returns (bytes32) {
        _requireAdapterInitialized();

        return keccak256(
            abi.encode(
                adapterForkContext.scopeHash,
                adapterForkContext.chainId,
                adapterForkContext.blockNumber,
                adapterForkContext.target,
                adapterForkContext.target.codehash,
                protocolStateHash
            )
        );
    }

    function _adapterTarget() internal view returns (address) {
        _requireAdapterInitialized();
        return adapterForkContext.target;
    }

    function _adapterScopeHash() internal view returns (bytes32) {
        _requireAdapterInitialized();
        return adapterForkContext.scopeHash;
    }

    function _requireAdapterInitialized() internal view {
        require(adapterInitialized, "adapter not initialized");
    }
}
