// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

interface VmResultCapture {
    function writeFile(string calldata path, string calldata data) external;
}

/// @notice Test-only helper that writes a deterministic v0.8-compatible explorer-result JSON file.
/// @dev The output path should be limited by Foundry fs_permissions. No production contract calls are made here.
abstract contract DirectResultCaptureHarness {
    VmResultCapture internal constant vmResultCapture =
        VmResultCapture(address(uint160(uint256(keccak256("hevm cheat code")))));

    struct CaptureMetadata {
        string adapterId;
        string scopeId;
        string manifestSha256;
        string findingId;
        string invariantId;
        string replay;
        uint256 exploredCandidates;
        string notes;
    }

    struct CaptureStep {
        string actionId;
        bool includeParameter;
        uint256 parameter;
        string preState;
        string postState;
        string effect;
    }

    function _writeExplorerResult(
        string memory outputPath,
        CaptureMetadata memory metadata,
        CaptureStep[] memory steps
    ) internal {
        require(bytes(outputPath).length > 0, "capture output path missing");
        require(bytes(metadata.adapterId).length > 0, "capture adapter id missing");
        require(bytes(metadata.scopeId).length > 0, "capture scope id missing");
        require(bytes(metadata.manifestSha256).length == 64, "capture manifest sha must be hex64");
        require(bytes(metadata.findingId).length > 0, "capture finding id missing");
        require(bytes(metadata.invariantId).length > 0, "capture invariant id missing");
        require(bytes(metadata.replay).length > 0, "capture replay missing");
        require(steps.length > 0, "capture path empty");

        string memory json = string.concat(
            "{\n",
            "  \"adapterId\": ",
            _jsonString(metadata.adapterId),
            ",\n",
            "  \"scopeId\": ",
            _jsonString(metadata.scopeId),
            ",\n",
            "  \"manifestSha256\": ",
            _jsonString(metadata.manifestSha256),
            ",\n",
            "  \"findingId\": ",
            _jsonString(metadata.findingId),
            ",\n",
            "  \"invariantId\": ",
            _jsonString(metadata.invariantId),
            ",\n",
            "  \"replay\": ",
            _jsonString(metadata.replay),
            ",\n",
            "  \"exploredCandidates\": ",
            _uintToString(metadata.exploredCandidates),
            ",\n",
            "  \"notes\": ",
            _jsonString(metadata.notes),
            ",\n",
            "  \"path\": [\n"
        );

        for (uint256 i = 0; i < steps.length; i++) {
            CaptureStep memory step = steps[i];
            require(bytes(step.actionId).length > 0, "capture action id missing");
            require(bytes(step.preState).length > 0, "capture pre-state missing");
            require(bytes(step.postState).length > 0, "capture post-state missing");
            require(bytes(step.effect).length > 0, "capture effect missing");

            json = string.concat(
                json,
                "    {\n",
                "      \"actionId\": ",
                _jsonString(step.actionId),
                ",\n"
            );
            if (step.includeParameter) {
                json = string.concat(
                    json,
                    "      \"parameter\": ",
                    _uintToString(step.parameter),
                    ",\n"
                );
            }
            json = string.concat(
                json,
                "      \"preState\": ",
                _jsonString(step.preState),
                ",\n",
                "      \"postState\": ",
                _jsonString(step.postState),
                ",\n",
                "      \"effect\": ",
                _jsonString(step.effect),
                "\n    }"
            );
            if (i + 1 < steps.length) {
                json = string.concat(json, ",");
            }
            json = string.concat(json, "\n");
        }

        json = string.concat(json, "  ]\n}\n");
        vmResultCapture.writeFile(outputPath, json);
    }

    function _jsonString(string memory value) internal pure returns (string memory) {
        return string.concat("\"", _escapeJson(value), "\"");
    }

    function _escapeJson(string memory value) internal pure returns (string memory) {
        bytes memory input = bytes(value);
        bytes memory output = new bytes(input.length * 6);
        uint256 out;
        bytes16 hexSymbols = "0123456789abcdef";

        for (uint256 i = 0; i < input.length; i++) {
            uint8 c = uint8(input[i]);
            if (c == 0x22 || c == 0x5c) {
                output[out++] = "\\";
                output[out++] = bytes1(c);
            } else if (c == 0x08) {
                output[out++] = "\\";
                output[out++] = "b";
            } else if (c == 0x0c) {
                output[out++] = "\\";
                output[out++] = "f";
            } else if (c == 0x0a) {
                output[out++] = "\\";
                output[out++] = "n";
            } else if (c == 0x0d) {
                output[out++] = "\\";
                output[out++] = "r";
            } else if (c == 0x09) {
                output[out++] = "\\";
                output[out++] = "t";
            } else if (c < 0x20) {
                output[out++] = "\\";
                output[out++] = "u";
                output[out++] = "0";
                output[out++] = "0";
                output[out++] = hexSymbols[c >> 4];
                output[out++] = hexSymbols[c & 0x0f];
            } else {
                output[out++] = bytes1(c);
            }
        }

        assembly ("memory-safe") {
            mstore(output, out)
        }
        return string(output);
    }

    function _uintToString(uint256 value) internal pure returns (string memory) {
        if (value == 0) return "0";

        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }

        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits--;
            buffer[digits] = bytes1(uint8(48 + value % 10));
            value /= 10;
        }
        return string(buffer);
    }
}
