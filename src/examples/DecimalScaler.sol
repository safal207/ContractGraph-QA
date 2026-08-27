// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

contract DecimalScaler {
    uint8 public constant ASSET_DECIMALS = 6;
    uint8 public constant PRICE_DECIMALS = 8;
    uint8 public constant WAD_DECIMALS = 18;

    function assetToWad(uint256 amount) external pure returns (uint256) {
        return amount * (10 ** (WAD_DECIMALS - ASSET_DECIMALS));
    }

    function priceToWad(uint256 price) external pure returns (uint256) {
        return price * (10 ** (WAD_DECIMALS - PRICE_DECIMALS));
    }
}
