// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ForkAuthorization} from "../src/harness/ForkAuthorization.sol";

contract ForkAuthorizationTest {
    function test_ValidScopeReturnsDeterministicHash() public pure {
        ForkAuthorization.Scope memory scope = ForkAuthorization.Scope({
            scopeId: "client-scope-001",
            authorizationReference: "signed-sow-2026-08-07",
            chainId: 1,
            target: address(0x1234),
            blockNumber: 20_000_000,
            confirmed: true
        });

        bytes32 first = ForkAuthorization.validate(scope);
        bytes32 second = ForkAuthorization.validate(scope);
        assert(first != bytes32(0));
        assert(first == second);
    }

    function test_MissingConfirmationFailsClosed() public {
        (bool ok,) = address(this).call(
            abi.encodeWithSelector(
                this.validateExternal.selector,
                "scope",
                "authorization-ref",
                uint256(1),
                address(0x1234),
                uint256(1),
                false
            )
        );
        assert(!ok);
    }

    function test_MissingAuthorizationReferenceFailsClosed() public {
        (bool ok,) = address(this).call(
            abi.encodeWithSelector(
                this.validateExternal.selector,
                "scope",
                "",
                uint256(1),
                address(0x1234),
                uint256(1),
                true
            )
        );
        assert(!ok);
    }

    function validateExternal(
        string memory scopeId,
        string memory authorizationReference,
        uint256 chainId,
        address target,
        uint256 blockNumber,
        bool confirmed
    ) external pure returns (bytes32) {
        ForkAuthorization.Scope memory scope = ForkAuthorization.Scope({
            scopeId: scopeId,
            authorizationReference: authorizationReference,
            chainId: chainId,
            target: target,
            blockNumber: blockNumber,
            confirmed: confirmed
        });
        return ForkAuthorization.validate(scope);
    }
}
