// Repository-owned synthetic subject used only by the TSSE adapter fixture.
pragma solidity ^0.8.20;

contract PaymentCoordinator {
    enum Phase { Created, Authorized, Settled }

    Phase public phase;
    uint256 public locked;
    uint256 public moved;

    function authorize(uint256 amount) external {
        require(phase == Phase.Created, "phase");
        phase = Phase.Authorized;
        locked = amount;
    }

    function settle() external {
        require(phase == Phase.Authorized, "phase");
        phase = Phase.Settled;
        moved = locked;
        locked = 0;
    }
}
