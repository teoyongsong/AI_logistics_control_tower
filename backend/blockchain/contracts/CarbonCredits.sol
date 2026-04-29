// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CarbonCredits {
    struct Credit {
        uint256 id;
        address holder;
        uint256 amount;
    }

    mapping(uint256 => Credit) public credits;
    uint256 public nextId;

    event CreditIssued(uint256 id, address holder, uint256 amount);
    event CreditTransferred(uint256 id, address from, address to, uint256 amount);

    function issueCredit(address holder, uint256 amount) public {
        credits[nextId] = Credit(nextId, holder, amount);
        emit CreditIssued(nextId, holder, amount);
        nextId++;
    }

    function transferCredit(uint256 id, address to, uint256 amount) public {
        require(credits[id].holder == msg.sender, "Not credit owner");
        require(credits[id].amount >= amount, "Insufficient credits");

        credits[id].amount -= amount;
        credits[nextId] = Credit(nextId, to, amount);
        emit CreditTransferred(id, msg.sender, to, amount);
        nextId++;
    }
}
