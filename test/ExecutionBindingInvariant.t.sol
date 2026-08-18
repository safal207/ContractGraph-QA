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

    function test_ImmediateReusableExternalDecisionMayDispatch() public pure {
        assert(_externalDispatchAllowed(Transit.ImmediateSync, false, false, false));
    }

    function test_CachedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.Cached, false, false, false));
    }

    function test_DeferredExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.Deferred, false, false, false));
    }

    function test_PersistedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.Persisted, false, false, false));
    }

    function test_QueuedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.Queued, false, false, false));
    }

    function test_TransportedExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.Transported, false, false, false));
    }

    function test_RetryReplayExternalDecisionFailsClosedWithoutRebind() public pure {
        assert(!_externalDispatchAllowed(Transit.RetryReplay, false, false, false));
    }

    function test_ReboundReusableDeferredDecisionMayDispatch() public pure {
        assert(_externalDispatchAllowed(Transit.Deferred, true, false, false));
    }

    function test_ReboundConsumableDecisionStillNeedsAtomicConsume() public pure {
        assert(!_externalDispatchAllowed(Transit.Deferred, true, true, false));
    }

    function test_ReboundAndAtomicallyConsumedDecisionMayDispatch() public pure {
        assert(_externalDispatchAllowed(Transit.Deferred, true, true, true));
    }

    function test_ImmediateConsumableDecisionNeedsAtomicConsume() public pure {
        assert(!_externalDispatchAllowed(Transit.ImmediateSync, false, true, false));
        assert(_externalDispatchAllowed(Transit.ImmediateSync, false, true, true));
    }

    function testFuzz_AnyEscapedExternalDecisionRequiresRebind(
        uint8 transitSeed,
        bool consumable,
        bool consumedAtomically
    ) public pure {
        Transit transit = Transit((transitSeed % 6) + 1);

        assert(!_externalDispatchAllowed(transit, false, consumable, consumedAtomically));
    }

    function testFuzz_ReboundReusableEscapedDecisionMayDispatch(uint8 transitSeed) public pure {
        Transit transit = Transit((transitSeed % 6) + 1);

        assert(_externalDispatchAllowed(transit, true, false, false));
    }

    function _externalDispatchAllowed(
        Transit transit,
        bool reboundAtDispatch,
        bool consumable,
        bool consumedAtomically
    ) internal pure returns (bool) {
        bool escapedProducingCallStack = transit != Transit.ImmediateSync;

        if (escapedProducingCallStack && !reboundAtDispatch) {
            return false;
        }

        if (consumable && !consumedAtomically) {
            return false;
        }

        return true;
    }
}
