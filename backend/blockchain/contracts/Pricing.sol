// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Pricing {
    struct PriceRecord {
        uint256 id;
        uint256 basePrice;
        uint256 dynamicPrice;
        uint256 timestamp;
    }

    mapping(uint256 => PriceRecord) public prices;
    uint256 public nextId;

    event PriceSet(uint256 id, uint256 basePrice, uint256 dynamicPrice);

    function setPrice(uint256 basePrice, uint256 dynamicPrice) public {
        prices[nextId] = PriceRecord(nextId, basePrice, dynamicPrice, block.timestamp);
        emit PriceSet(nextId, basePrice, dynamicPrice);
        nextId++;
    }

    function getPrice(uint256 id) public view returns (PriceRecord memory) {
        return prices[id];
    }
}
