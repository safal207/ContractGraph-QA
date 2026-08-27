// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {DecimalScaler} from "../src/examples/DecimalScaler.sol";

contract DecimalScalerTest {
    DecimalScaler internal scaler;

    function setUp() public {
        scaler = new DecimalScaler();
    }

    function testAssetDecimalsScaleToWad() public view {
        assert(scaler.assetToWad(1_000_000) == 1 ether);
    }

    function testPriceDecimalsScaleToWad() public view {
        assert(scaler.priceToWad(200_000_000) == 2 ether);
    }
}
