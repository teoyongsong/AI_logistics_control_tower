// hardhat.config.mjs
import "@nomicfoundation/hardhat-toolbox";

export default {
  solidity: "0.8.20",
  networks: {
    mumbai: {
      url: "https://polygon-mumbai.infura.io/v3/YOUR_INFURA_PROJECT_ID",
      accounts: ["0xYOUR_PRIVATE_KEY"]
    }
  }
};
