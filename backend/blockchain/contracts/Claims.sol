// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Claims {
    struct Claim {
        uint256 id;
        address customer;
        string description;
        bool approved;
    }

    mapping(uint256 => Claim) public claims;
    uint256 public nextId;

    event ClaimSubmitted(uint256 id, address customer, string description);
    event ClaimApproved(uint256 id);

    function submitClaim(string memory description) public {
        claims[nextId] = Claim(nextId, msg.sender, description, false);
        emit ClaimSubmitted(nextId, msg.sender, description);
        nextId++;
    }

    function approveClaim(uint256 id) public {
        // TODO: Add role-based access (e.g., only admin can approve)
        claims[id].approved = true;
        emit ClaimApproved(id);
    }
}
