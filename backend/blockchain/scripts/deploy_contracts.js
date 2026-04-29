// scripts/deploy_contracts.js
const hre = require("hardhat");

async function main() {
  // Compile contracts
  await hre.run("compile");

  // Deploy Claims contract
  const Claims = await hre.ethers.getContractFactory("Claims");
  const claims = await Claims.deploy();
  await claims.deployed();
  console.log("Claims contract deployed to:", claims.address);

  // Deploy Pricing contract
  const Pricing = await hre.ethers.getContractFactory("Pricing");
  const pricing = await Pricing.deploy();
  await pricing.deployed();
  console.log("Pricing contract deployed to:", pricing.address);

  // Deploy CarbonCredits contract
  const CarbonCredits = await hre.ethers.getContractFactory("CarbonCredits");
  const carbonCredits = await CarbonCredits.deploy();
  await carbonCredits.deployed();
  console.log("CarbonCredits contract deployed to:", carbonCredits.address);
}

// Run deployment
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
