// SPDX-License-Identifier: MIT
// Upstream: https://github.com/Gitlawb/contracts
// Pinned commit: b60de4973c568b34975c20f18cde1afd71a59f1b
// Source path: src/GitlawbBounty.sol
pragma solidity ^0.8.24;

import {IERC20} from "lib/forge-std/src/interfaces/IERC20.sol";

/// @title GitlawbBounty
/// @notice Token-powered bounty marketplace for AI agents on Base L2.
contract GitlawbBounty {
    enum Status {
        Open,
        Claimed,
        Submitted,
        Completed,
        Cancelled,
        Disputed
    }

    struct Bounty {
        address creator;
        uint256 amount;
        string repoOwner;
        string repoName;
        string issueId;
        string title;
        string claimantDid;
        address claimantAddress;
        string prId;
        Status status;
        uint256 createdAt;
        uint256 claimedAt;
        uint256 submittedAt;
        uint256 completedAt;
        uint256 deadline;
    }

    IERC20 public immutable token;
    address public treasury;
    address public owner;
    uint256 public protocolFeeBps;
    uint256 public nextBountyId;
    uint256 public defaultDeadline;

    mapping(uint256 => Bounty) public bounties;
    mapping(bytes32 => uint256) public agentEarnings;
    mapping(bytes32 => uint256) public agentCompletedCount;
    uint256 public totalPaidOut;
    uint256 public totalFeesCollected;

    event BountyCreated(uint256 indexed bountyId, address indexed creator, uint256 amount, string repoOwner, string repoName, string issueId, string title);
    event BountyClaimed(uint256 indexed bountyId, string claimantDid, address indexed claimantAddress);
    event BountySubmitted(uint256 indexed bountyId, string prId);
    event BountyCompleted(uint256 indexed bountyId, address indexed claimant, uint256 payout, uint256 fee);
    event BountyCancelled(uint256 indexed bountyId);
    event BountyDisputed(uint256 indexed bountyId);
    event TreasuryUpdated(address indexed newTreasury);
    event FeeUpdated(uint256 newFeeBps);

    error NotOwner();
    error NotBountyCreator(uint256 bountyId);
    error InvalidAmount();
    error InvalidStatus(uint256 bountyId, Status expected, Status actual);
    error DeadlineExceeded(uint256 bountyId);
    error DeadlineNotExceeded(uint256 bountyId);
    error TransferFailed();
    error ZeroAddress();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyBountyCreator(uint256 bountyId) {
        if (msg.sender != bounties[bountyId].creator) revert NotBountyCreator(bountyId);
        _;
    }

    modifier inStatus(uint256 bountyId, Status expected) {
        Status actual = bounties[bountyId].status;
        if (actual != expected) revert InvalidStatus(bountyId, expected, actual);
        _;
    }

    constructor(address _token, address _treasury) {
        token = IERC20(_token);
        treasury = _treasury;
        owner = msg.sender;
        protocolFeeBps = 500;
        defaultDeadline = 7 days;
    }

    function createBounty(
        uint256 amount,
        string calldata repoOwner,
        string calldata repoName,
        string calldata issueId,
        string calldata title
    ) external returns (uint256 bountyId) {
        if (amount == 0) revert InvalidAmount();
        bool ok = token.transferFrom(msg.sender, address(this), amount);
        if (!ok) revert TransferFailed();
        bountyId = nextBountyId++;
        bounties[bountyId] = Bounty({
            creator: msg.sender,
            amount: amount,
            repoOwner: repoOwner,
            repoName: repoName,
            issueId: issueId,
            title: title,
            claimantDid: "",
            claimantAddress: address(0),
            prId: "",
            status: Status.Open,
            createdAt: block.timestamp,
            claimedAt: 0,
            submittedAt: 0,
            completedAt: 0,
            deadline: defaultDeadline
        });
        emit BountyCreated(bountyId, msg.sender, amount, repoOwner, repoName, issueId, title);
    }

    function claimBounty(uint256 bountyId, string calldata agentDid)
        external
        inStatus(bountyId, Status.Open)
    {
        Bounty storage b = bounties[bountyId];
        b.claimantDid = agentDid;
        b.claimantAddress = msg.sender;
        b.claimedAt = block.timestamp;
        b.status = Status.Claimed;
        emit BountyClaimed(bountyId, agentDid, msg.sender);
    }

    function submitBounty(uint256 bountyId, string calldata prId)
        external
        inStatus(bountyId, Status.Claimed)
    {
        Bounty storage b = bounties[bountyId];
        require(msg.sender == b.claimantAddress, "only claimant");
        if (block.timestamp > b.claimedAt + b.deadline) revert DeadlineExceeded(bountyId);
        b.prId = prId;
        b.submittedAt = block.timestamp;
        b.status = Status.Submitted;
        emit BountySubmitted(bountyId, prId);
    }

    function approveBounty(uint256 bountyId)
        external
        onlyBountyCreator(bountyId)
        inStatus(bountyId, Status.Submitted)
    {
        Bounty storage b = bounties[bountyId];
        uint256 fee = (b.amount * protocolFeeBps) / 10000;
        uint256 payout = b.amount - fee;
        b.status = Status.Completed;
        b.completedAt = block.timestamp;
        bool ok1 = token.transfer(b.claimantAddress, payout);
        if (!ok1) revert TransferFailed();
        if (fee > 0) {
            bool ok2 = token.transfer(treasury, fee);
            if (!ok2) revert TransferFailed();
        }
        bytes32 didHash = keccak256(bytes(b.claimantDid));
        agentEarnings[didHash] += payout;
        agentCompletedCount[didHash] += 1;
        totalPaidOut += payout;
        totalFeesCollected += fee;
        emit BountyCompleted(bountyId, b.claimantAddress, payout, fee);
    }

    function cancelBounty(uint256 bountyId)
        external
        onlyBountyCreator(bountyId)
        inStatus(bountyId, Status.Open)
    {
        Bounty storage b = bounties[bountyId];
        b.status = Status.Cancelled;
        bool ok = token.transfer(b.creator, b.amount);
        if (!ok) revert TransferFailed();
        emit BountyCancelled(bountyId);
    }

    function disputeBounty(uint256 bountyId) external {
        Bounty storage b = bounties[bountyId];
        if (b.status != Status.Claimed && b.status != Status.Submitted) {
            revert InvalidStatus(bountyId, Status.Claimed, b.status);
        }
        if (block.timestamp <= b.claimedAt + b.deadline) {
            revert DeadlineNotExceeded(bountyId);
        }
        b.status = Status.Open;
        b.claimantDid = "";
        b.claimantAddress = address(0);
        b.prId = "";
        b.claimedAt = 0;
        b.submittedAt = 0;
        emit BountyDisputed(bountyId);
    }

    function getBountyCore(uint256 bountyId) external view returns (
        address creator,
        uint256 amount,
        string memory title,
        Status status,
        uint256 createdAt,
        uint256 deadline
    ) {
        Bounty storage b = bounties[bountyId];
        return (b.creator, b.amount, b.title, b.status, b.createdAt, b.deadline);
    }

    function getBountyClaim(uint256 bountyId) external view returns (
        string memory claimantDid,
        address claimantAddress,
        string memory prId,
        string memory repoOwner,
        string memory repoName,
        string memory issueId
    ) {
        Bounty storage b = bounties[bountyId];
        return (b.claimantDid, b.claimantAddress, b.prId, b.repoOwner, b.repoName, b.issueId);
    }

    function getAgentStats(string calldata agentDid) external view returns (uint256 earnings, uint256 completedCount) {
        bytes32 didHash = keccak256(bytes(agentDid));
        return (agentEarnings[didHash], agentCompletedCount[didHash]);
    }

    function getProtocolStats() external view returns (uint256 totalBounties, uint256 _totalPaidOut, uint256 _totalFeesCollected) {
        return (nextBountyId, totalPaidOut, totalFeesCollected);
    }

    function setTreasury(address _treasury) external onlyOwner {
        if (_treasury == address(0)) revert ZeroAddress();
        treasury = _treasury;
        emit TreasuryUpdated(_treasury);
    }

    function setProtocolFee(uint256 _feeBps) external onlyOwner {
        require(_feeBps <= 1000, "fee too high");
        protocolFeeBps = _feeBps;
        emit FeeUpdated(_feeBps);
    }

    function setDefaultDeadline(uint256 _seconds) external onlyOwner {
        require(_seconds >= 1 hours, "deadline too short");
        defaultDeadline = _seconds;
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        owner = newOwner;
    }
}
