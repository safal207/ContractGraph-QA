// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {GitlawbBounty} from "../src/GitlawbBounty.sol";
import {LocalMockERC20} from "./LocalMockERC20.sol";

interface Vm {
    function prank(address msgSender) external;
    function warp(uint256 newTimestamp) external;
}

/// @notice Local-only reproduction against Gitlawb/contracts pinned at
/// b60de4973c568b34975c20f18cde1afd71a59f1b. No RPC or deployed target is used.
contract GitlawbBountyTemporalTest {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    GitlawbBounty internal bounty;
    LocalMockERC20 internal token;

    address internal constant TREASURY = address(0xFEE);
    address internal constant CREATOR = address(0xA11CE);
    address internal constant AGENT = address(0xA6E47);
    address internal constant THIRD_PARTY = address(0xB0B);
    uint256 internal constant AMOUNT = 100_000 ether;

    function setUp() public {
        token = new LocalMockERC20();
        bounty = new GitlawbBounty(address(token), TREASURY);
        token.mint(CREATOR, AMOUNT);

        vm.prank(CREATOR);
        token.approve(address(bounty), AMOUNT);
    }

    function test_timelySubmissionCanBeReopenedByThirdPartyAfterClaimDeadline() public {
        vm.prank(CREATOR);
        uint256 id = bounty.createBounty(AMOUNT, "gitlawb", "contracts", "issue", "title");

        uint256 claimTime = block.timestamp;
        vm.prank(AGENT);
        bounty.claimBounty(id, "did:key:agent");

        vm.warp(claimTime + 7 days - 1);
        vm.prank(AGENT);
        bounty.submitBounty(id, "pr-123");

        (,, string memory prBefore,,,) = bounty.getBountyClaim(id);
        (,,, GitlawbBounty.Status statusBefore,,) = bounty.getBountyCore(id);
        assert(keccak256(bytes(prBefore)) == keccak256(bytes("pr-123")));
        assert(uint8(statusBefore) == uint8(GitlawbBounty.Status.Submitted));

        vm.warp(claimTime + 7 days + 1);
        vm.prank(THIRD_PARTY);
        bounty.disputeBounty(id);

        (string memory didAfter, address claimantAfter, string memory prAfter,,,) =
            bounty.getBountyClaim(id);
        (,,, GitlawbBounty.Status statusAfter,,) = bounty.getBountyCore(id);

        assert(uint8(statusAfter) == uint8(GitlawbBounty.Status.Open));
        assert(bytes(didAfter).length == 0);
        assert(claimantAfter == address(0));
        assert(bytes(prAfter).length == 0);
        assert(token.balanceOf(address(bounty)) == AMOUNT);

        bool approvalSucceeded;
        vm.prank(CREATOR);
        try bounty.approveBounty(id) {
            approvalSucceeded = true;
        } catch {
            approvalSucceeded = false;
        }
        assert(!approvalSucceeded);
    }
}
