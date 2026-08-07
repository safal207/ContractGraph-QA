// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ForkContextHarness} from "../src/harness/ForkContextHarness.sol";

/// @notice Read-only smoke test for an explicitly authorized fork target.
contract AuthorizedForkSmokeTest is ForkContextHarness {
    function test_AuthorizedForkTargetExistsAndSnapshotIsStable() public {
        ForkContext memory context = _openAuthorizedForkFromEnv();

        bytes32 first = _forkSnapshotHash(context.target);
        bytes32 second = _forkSnapshotHash(context.target);

        assert(context.scopeHash != bytes32(0));
        assert(context.target.code.length > 0);
        assert(block.chainid == context.chainId);
        assert(block.number == context.blockNumber);
        assert(first != bytes32(0));
        assert(first == second);
    }
}
