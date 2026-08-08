// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import {IERC20} from "forge-std/interfaces/IERC20.sol";
import {GitlawbBounty} from "../../external/gitlawb/GitlawbBounty.sol";

contract LocalMockERC20 is IERC20 {
    string public name = "LocalMock";
    string public symbol = "LMOCK";
    uint8 public decimals = 18;
    uint256 public override totalSupply;

    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public override allowance;

    function mint(address to, uint256 amount) external {
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function transfer(address to, uint256 amount) external override returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external override returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= amount, "allowance");
        if (allowed != type(uint256).max) {
            allowance[from][msg.sender] = allowed - amount;
        }
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}

/// @notice External, local-only validation of Gitlawb/contracts at
/// b60de4973c568b34975c20f18cde1afd71a59f1b. No RPC or deployed target is used.
contract GitlawbBountyTemporalTest is Test {
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

    /// Candidate temporal/business-logic finding:
    /// a claimant submits before the advertised claim deadline, but after that
    /// same deadline elapses any third party can reset Submitted -> Open,
    /// clearing the claimant and PR before the creator approves it.
    function test_timelySubmissionCanBeReopenedByThirdPartyAfterClaimDeadline() public {
        vm.prank(CREATOR);
        uint256 id = bounty.createBounty(AMOUNT, "gitlawb", "contracts", "issue", "title");

        uint256 claimTime = block.timestamp;
        vm.prank(AGENT);
        bounty.claimBounty(id, "did:key:agent");

        // Agent submits on time: one second before the 7-day claim deadline.
        vm.warp(claimTime + 7 days - 1);
        vm.prank(AGENT);
        bounty.submitBounty(id, "pr-123");

        (,, string memory prBefore,,,) = bounty.getBountyClaim(id);
        (,,, GitlawbBounty.Status statusBefore,,) = bounty.getBountyCore(id);
        assertEq(prBefore, "pr-123");
        assertEq(uint8(statusBefore), uint8(GitlawbBounty.Status.Submitted));

        // Once the original claim deadline passes, an unrelated address can
        // erase the timely submission and reopen the bounty.
        vm.warp(claimTime + 7 days + 1);
        vm.prank(THIRD_PARTY);
        bounty.disputeBounty(id);

        (string memory didAfter, address claimantAfter, string memory prAfter,,,) =
            bounty.getBountyClaim(id);
        (,,, GitlawbBounty.Status statusAfter,,) = bounty.getBountyCore(id);

        assertEq(uint8(statusAfter), uint8(GitlawbBounty.Status.Open));
        assertEq(bytes(didAfter).length, 0);
        assertEq(claimantAfter, address(0));
        assertEq(bytes(prAfter).length, 0);
        assertEq(token.balanceOf(address(bounty)), AMOUNT);

        // The creator can no longer approve the timely submission because the
        // state has already been reset to Open.
        vm.expectRevert(
            abi.encodeWithSelector(
                GitlawbBounty.InvalidStatus.selector,
                id,
                GitlawbBounty.Status.Submitted,
                GitlawbBounty.Status.Open
            )
        );
        vm.prank(CREATOR);
        bounty.approveBounty(id);
    }
}
