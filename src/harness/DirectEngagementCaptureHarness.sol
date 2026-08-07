// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {DirectResultCaptureHarness} from "./DirectResultCaptureHarness.sol";

/// @notice Test-only deterministic writer for v1.2 engagement-result JSON.
abstract contract DirectEngagementCaptureHarness is DirectResultCaptureHarness {
    struct EngagementCaptureMetadata {
        string engagementId;
        string adapterId;
        string scopeId;
        string manifestSha256;
        string searchRunId;
        string replay;
    }

    struct EngagementCheckCapture {
        string invariantId;
        string status;
        bool includeFindingId;
        string findingId;
        uint256 exploredCandidates;
        string notes;
        CaptureStep[] path;
    }

    function _writeEngagementResult(
        string memory outputPath,
        EngagementCaptureMetadata memory metadata,
        EngagementCheckCapture[] memory checks
    ) internal {
        require(bytes(outputPath).length > 0, "engagement output path missing");
        require(bytes(metadata.engagementId).length > 0, "engagement id missing");
        require(bytes(metadata.adapterId).length > 0, "engagement adapter id missing");
        require(bytes(metadata.scopeId).length > 0, "engagement scope id missing");
        _requireLowercaseSha256(metadata.manifestSha256);
        require(bytes(metadata.searchRunId).length > 0, "search run id missing");
        require(bytes(metadata.replay).length > 0, "engagement replay missing");
        require(checks.length > 0, "engagement checks empty");

        string memory json = string.concat(
            "{\n",
            "  \"schemaVersion\": 1,\n",
            "  \"engagementId\": ", _jsonString(metadata.engagementId), ",\n",
            "  \"adapterId\": ", _jsonString(metadata.adapterId), ",\n",
            "  \"scopeId\": ", _jsonString(metadata.scopeId), ",\n",
            "  \"manifestSha256\": ", _jsonString(metadata.manifestSha256), ",\n",
            "  \"searchRunId\": ", _jsonString(metadata.searchRunId), ",\n",
            "  \"replay\": ", _jsonString(metadata.replay), ",\n",
            "  \"checks\": [\n"
        );

        for (uint256 i = 0; i < checks.length; i++) {
            json = string.concat(json, _renderEngagementCheck(checks[i]));
            if (i + 1 < checks.length) json = string.concat(json, ",");
            json = string.concat(json, "\n");
        }

        json = string.concat(json, "  ]\n}\n");
        vmResultCapture.writeFile(outputPath, json);
    }

    function _renderEngagementCheck(EngagementCheckCapture memory check)
        internal
        pure
        returns (string memory json)
    {
        require(bytes(check.invariantId).length > 0, "check invariant id missing");
        require(_validStatus(check.status), "invalid engagement check status");
        require(bytes(check.notes).length > 0, "check notes missing");

        bool violated = keccak256(bytes(check.status)) == keccak256(bytes("violated"));
        require(check.includeFindingId == violated, "finding id/status mismatch");
        require((check.path.length > 0) == violated, "path/status mismatch");
        if (violated) require(bytes(check.findingId).length > 0, "finding id missing");

        json = string.concat(
            "    {\n",
            "      \"invariantId\": ", _jsonString(check.invariantId), ",\n",
            "      \"status\": ", _jsonString(check.status), ",\n"
        );
        if (check.includeFindingId) {
            json = string.concat(
                json, "      \"findingId\": ", _jsonString(check.findingId), ",\n"
            );
        }
        json = string.concat(
            json,
            "      \"exploredCandidates\": ", _uintToString(check.exploredCandidates), ",\n",
            "      \"notes\": ", _jsonString(check.notes)
        );

        if (violated) {
            json = string.concat(json, ",\n      \"path\": [\n");
            for (uint256 i = 0; i < check.path.length; i++) {
                json = string.concat(json, _renderCaptureStep(check.path[i]));
                if (i + 1 < check.path.length) json = string.concat(json, ",");
                json = string.concat(json, "\n");
            }
            json = string.concat(json, "      ]\n    }");
        } else {
            json = string.concat(json, "\n    }");
        }
    }

    function _renderCaptureStep(CaptureStep memory step) internal pure returns (string memory json) {
        require(bytes(step.actionId).length > 0, "capture action id missing");
        require(bytes(step.preState).length > 0, "capture pre-state missing");
        require(bytes(step.postState).length > 0, "capture post-state missing");
        require(bytes(step.effect).length > 0, "capture effect missing");

        json = string.concat(
            "        {\n",
            "          \"actionId\": ", _jsonString(step.actionId), ",\n"
        );
        if (step.includeParameter) {
            json = string.concat(
                json, "          \"parameter\": ", _uintToString(step.parameter), ",\n"
            );
        }
        json = string.concat(
            json,
            "          \"preState\": ", _jsonString(step.preState), ",\n",
            "          \"postState\": ", _jsonString(step.postState), ",\n",
            "          \"effect\": ", _jsonString(step.effect), "\n",
            "        }"
        );
    }

    function _validStatus(string memory status) internal pure returns (bool) {
        bytes32 digest = keccak256(bytes(status));
        return digest == keccak256(bytes("violated"))
            || digest == keccak256(bytes("not_found_within_bound"))
            || digest == keccak256(bytes("inconclusive"));
    }
}
