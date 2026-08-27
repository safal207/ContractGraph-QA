// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

contract ExecutionBindingInvariantTest {
    enum Transit {
        ImmediateSync,
        Cached,
        Deferred,
        Persisted,
        Queued,
        Transported,
        RetryReplay
    }

    error RebindRequired();
    error AuthorityAlreadyConsumed();

    mapping(bytes32 authorityId => bool consumed) public authorityConsumed;
    mapping(bytes32 authorityId => uint256 count) public dispatchCount;

    function test_ImmediateReusableExternalDecisionMayDispatch() public pure {
        assert(_reusableExternalDispatchAllowed(Transit.ImmediateSync, false));
    }

    function test_CachedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.Cached, false));
    }

    function test_DeferredExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.Deferred, false));
    }

    function test_PersistedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.Persisted, false));
    }

    function test_QueuedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.Queued, false));
    }

    function test_TransportedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.Transported, false));
    }

    function test_RetryReplayExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_reusableExternalDispatchAllowed(Transit.RetryReplay, false));
    }

    function test_ReboundReusableDeferredDecisionMayDispatch() public pure {
        assert(_reusableExternalDispatchAllowed(Transit.Deferred, true));
    }

    function test_ConsumableAuthorityDispatchesExactlyOnce() public {
        bytes32 authorityId = keccak256("single-use-immediate");

        this.consumeAndDispatch(authorityId, Transit.ImmediateSync, false);

        assert(authorityConsumed[authorityId]);
        assert(dispatchCount[authorityId] == 1);

        bool secondDispatchSucceeded;
        try this.consumeAndDispatch(authorityId, Transit.ImmediateSync, false) {
            secondDispatchSucceeded = true;
        } catch {}

        assert(!secondDispatchSucceeded);
        assert(dispatchCount[authorityId] == 1);
    }

    function test_EscapedConsumableAuthorityRequiresRebindBeforeConsume() public {
        bytes32 authorityId = keccak256("single-use-deferred");

        bool unboundDispatchSucceeded;
        try this.consumeAndDispatch(authorityId, Transit.Deferred, false) {
            unboundDispatchSucceeded = true;
        } catch {}

        assert(!unboundDispatchSucceeded);
        assert(!authorityConsumed[authorityId]);
        assert(dispatchCount[authorityId] == 0);

        this.consumeAndDispatch(authorityId, Transit.Deferred, true);
        assert(authorityConsumed[authorityId]);
        assert(dispatchCount[authorityId] == 1);
    }

    function testFuzz_AnyEscapedExternalDecisionRequiresRebind(uint8 transitSeed) public pure {
        Transit transit = Transit((transitSeed % 6) + 1);

        assert(!_reusableExternalDispatchAllowed(transit, false));
    }

    function testFuzz_ReboundReusableEscapedDecisionMayDispatch(uint8 transitSeed) public pure {
        Transit transit = Transit((transitSeed % 6) + 1);

        assert(_reusableExternalDispatchAllowed(transit, true));
    }

    function consumeAndDispatch(bytes32 authorityId, Transit transit, bool reboundAtDispatch)
        external
    {
        bool escapedProducingCallStack = transit != Transit.ImmediateSync;
        if (escapedProducingCallStack && !reboundAtDispatch) {
            revert RebindRequired();
        }
        if (authorityConsumed[authorityId]) {
            revert AuthorityAlreadyConsumed();
        }

        // Consumption precedes the modeled side effect in the same transaction.
        authorityConsumed[authorityId] = true;
        dispatchCount[authorityId] += 1;
    }

    function _reusableExternalDispatchAllowed(Transit transit, bool reboundAtDispatch)
        internal
        pure
        returns (bool)
    {
        return transit == Transit.ImmediateSync || reboundAtDispatch;
    }
}
