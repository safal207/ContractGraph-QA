package org.contractgraphqa.interop;

import com.fasterxml.jackson.core.JsonFactory;
import com.fasterxml.jackson.core.StreamReadConstraints;
import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/** Strict validator for one passing cgqa-liminalqa-v0.1 conformance report. */
public final class InteropReportValidator {
    public static final int MAX_REPORT_BYTES = 1_048_576;
    private static final String SCHEMA = "org.contractgraph-qa.liminalqa-interop-conformance-result.v0.1";
    private static final String SUITE_ID = "cgqa-liminalqa-v0.1";
    private static final String SUITE_VERSION = "0.1.0";
    private static final String SUITE_SHA256 = "562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac";
    private static final String CLAIM_BOUNDARY = "Synthetic conformance verifies adapter behavior only for these pinned fixtures and mutations. It does not verify a production system, prove security or completeness, authorize an action, or replace independent replay against the exact subject.";
    private static final Pattern SAFE_ID = Pattern.compile("^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$");

    private static final ObjectMapper MAPPER = new ObjectMapper(
            JsonFactory.builder()
                    .streamReadConstraints(StreamReadConstraints.builder()
                            .maxNestingDepth(64)
                            .maxDocumentLength(MAX_REPORT_BYTES)
                            .build())
                    .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION)
                    .build())
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private record ContractPin(String artifactSchema, String artifactProfile, String ownerRepository,
                               String producerCommit, String schemaSha256, String fixtureSha256) {}

    private static final Map<String, ContractPin> CONTRACT_PINS = Map.of(
            "cgqa-evidence", new ContractPin(
                    "org.contractgraph-qa.liminalqa-evidence.v0.1",
                    "org.contractgraph-qa.bounded-invariant-evidence.v0.1",
                    "safal207/ContractGraph-QA",
                    "bdf7ced074e3a7baf57cf89ac68be9674bd76a02",
                    "53b0b4a0b1f4d77de26b8be9dbb90006ea0bd30c5cd3960a2f3e7d44d9664184",
                    "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce"),
            "liminal-candidates", new ContractPin(
                    "org.liminalqa.cgqa-candidates.v0.1",
                    "org.liminalqa.non-authoritative-candidate-seeds.v0.1",
                    "safal207/LiminalQAengineer",
                    "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3",
                    "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60",
                    "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3"));

    private record CasePin(String contract, String category, String semantics, String inputSha256) {}

    private static final Map<String, CasePin> CASE_PINS = Map.ofEntries(
            Map.entry("cgqa-evidence-golden", new CasePin("cgqa-evidence", "golden", "VALID_NON_AUTHORIZING", "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce")),
            Map.entry("cgqa-evidence-authority-escalation", new CasePin("cgqa-evidence", "authority_escalation", "INVALID_BLOCKED", "33eb3122738032c3ebc1043f5058bc7a9cc469c6ecff8ad0a602aaa3a80067ce")),
            Map.entry("cgqa-evidence-count-mismatch", new CasePin("cgqa-evidence", "semantic_mismatch", "INVALID_BLOCKED", "3f348306ba20fdb780b662ec3aadbdf8d1a805a1d81cb2eb66103824e9f8b95f")),
            Map.entry("cgqa-evidence-temporal-inversion", new CasePin("cgqa-evidence", "temporal_inversion", "INVALID_BLOCKED", "dbc7d64eda4aeb497bf360e10335896b3f9b4316973306e37a8a21134cc85ba8")),
            Map.entry("cgqa-evidence-unknown-authority-field", new CasePin("cgqa-evidence", "unknown_field", "INVALID_BLOCKED", "49d7eab11be2a4fc5b90776a9822156573ef5753bff25e674629fdb8e742edea")),
            Map.entry("cgqa-evidence-unsafe-causal-parent", new CasePin("cgqa-evidence", "unsafe_identifier", "INVALID_BLOCKED", "e50dfe383bbd2577b72dba043bbe129b6370b81ec8226d6fa9ed206bf6bf51af")),
            Map.entry("cgqa-evidence-duplicate-schema-key", new CasePin("cgqa-evidence", "ambiguous_json", "INVALID_BLOCKED", "6ff810788c268a93af16daa7a814cfe84616542951de92be8dbe79aabf3d41c9")),
            Map.entry("liminal-candidates-golden", new CasePin("liminal-candidates", "golden", "VALID_NON_AUTHORIZING", "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3")),
            Map.entry("liminal-candidates-authority-escalation", new CasePin("liminal-candidates", "authority_escalation", "INVALID_BLOCKED", "261570efc9e6c13d46686a6f5941ee7d39db620c4603cf30a64e0f0baae3abff")),
            Map.entry("liminal-candidates-unknown-authority-field", new CasePin("liminal-candidates", "unknown_field", "INVALID_BLOCKED", "1a3841322a8dae89e793f92cedcf341c5fafa4a70e308426d76f674434291941")),
            Map.entry("liminal-candidates-missing-independent-replay", new CasePin("liminal-candidates", "verification_weakening", "INVALID_BLOCKED", "8030649160511f62065f4ba33d703fb4dcbf96bc25480d8fa9c7d4e85d715423")),
            Map.entry("liminal-candidates-debt-mismatch", new CasePin("liminal-candidates", "semantic_mismatch", "INVALID_BLOCKED", "172a1567897dc4a78deaf2c9f50bc6634e59d2d671ab23d414ca8b4a089f8185")),
            Map.entry("liminal-candidates-unsafe-causal-parent", new CasePin("liminal-candidates", "unsafe_identifier", "INVALID_BLOCKED", "61b8e74f52248e50fc90e0765b6cc0449ea5b588cb6aa525d148dcb9ac447960")),
            Map.entry("liminal-candidates-duplicate-schema-key", new CasePin("liminal-candidates", "ambiguous_json", "INVALID_BLOCKED", "9bf53f54b15a2eb09731c28dfffc5ba39f7c04b0d5fa4d076f300f8107ae2d40")));

    public record Implementation(String name, String version, String language) {}

    /** A passing summary remains evidence-only and never authorizes an action. */
    public record Summary(boolean valid, String suiteId, Implementation implementation, int passed,
                          boolean mayAuthorizeAction, String claimBoundary) {}

    private InteropReportValidator() {}

    public static Summary validate(String raw) throws ConformanceReportException {
        return validate(raw.getBytes(StandardCharsets.UTF_8));
    }

    public static Summary validate(byte[] raw) throws ConformanceReportException {
        if (raw.length > MAX_REPORT_BYTES) {
            throw invalid("json", "must not exceed " + MAX_REPORT_BYTES + " bytes");
        }
        final JsonNode report;
        try {
            report = MAPPER.readTree(raw);
        } catch (IOException exception) {
            throw new ConformanceReportException("json: invalid or ambiguous JSON", exception);
        }
        object(report, "report");
        exactFields(report, Set.of("schema", "reportId", "suiteId", "suiteVersion", "suiteSha256",
                "implementation", "status", "counts", "contractPins", "results", "authority", "claimBoundary"), "report");
        equalText(report.get("schema"), SCHEMA, "schema");
        String reportId = text(report.get("reportId"), "reportId");
        if (!SAFE_ID.matcher(reportId).matches()) throw invalid("reportId", "must be a safe identifier");
        equalText(report.get("suiteId"), SUITE_ID, "suiteId");
        equalText(report.get("suiteVersion"), SUITE_VERSION, "suiteVersion");
        equalText(report.get("suiteSha256"), SUITE_SHA256, "suiteSha256");
        equalText(report.get("status"), "PASS", "status");
        equalText(report.get("claimBoundary"), CLAIM_BOUNDARY, "claimBoundary");

        JsonNode implementation = object(report.get("implementation"), "implementation");
        exactFields(implementation, Set.of("name", "version", "language"), "implementation");
        Implementation identity = new Implementation(
                text(implementation.get("name"), "implementation.name"),
                text(implementation.get("version"), "implementation.version"),
                text(implementation.get("language"), "implementation.language"));

        JsonNode counts = object(report.get("counts"), "counts");
        exactFields(counts, Set.of("total", "passed", "failed"), "counts");
        equalInt(counts.get("total"), 14, "counts.total");
        equalInt(counts.get("passed"), 14, "counts.passed");
        equalInt(counts.get("failed"), 0, "counts.failed");

        JsonNode authority = object(report.get("authority"), "authority");
        exactFields(authority, Set.of("classification", "mayAuthorizeAction"), "authority");
        equalText(authority.get("classification"), "conformance_evidence_only", "authority.classification");
        equalBoolean(authority.get("mayAuthorizeAction"), false, "authority.mayAuthorizeAction");
        validateContractPins(report.get("contractPins"));
        validateResults(report.get("results"));
        return new Summary(true, SUITE_ID, identity, 14, false, CLAIM_BOUNDARY);
    }

    private static void validateContractPins(JsonNode node) throws ConformanceReportException {
        if (node == null || !node.isArray() || node.size() != CONTRACT_PINS.size()) {
            throw invalid("contractPins", "must contain both pinned contracts");
        }
        Set<String> seen = new HashSet<>();
        for (int index = 0; index < node.size(); index++) {
            String path = "contractPins[" + index + "]";
            JsonNode pin = object(node.get(index), path);
            exactFields(pin, Set.of("id", "artifactSchema", "artifactProfile", "ownerRepository",
                    "producerCommit", "schemaSha256", "fixtureSha256"), path);
            String id = text(pin.get("id"), path + ".id");
            ContractPin expected = CONTRACT_PINS.get(id);
            if (expected == null || !seen.add(id)) throw invalid(path + ".id", "must identify one unique pinned contract");
            equalText(pin.get("artifactSchema"), expected.artifactSchema(), path + ".artifactSchema");
            equalText(pin.get("artifactProfile"), expected.artifactProfile(), path + ".artifactProfile");
            equalText(pin.get("ownerRepository"), expected.ownerRepository(), path + ".ownerRepository");
            equalText(pin.get("producerCommit"), expected.producerCommit(), path + ".producerCommit");
            equalText(pin.get("schemaSha256"), expected.schemaSha256(), path + ".schemaSha256");
            equalText(pin.get("fixtureSha256"), expected.fixtureSha256(), path + ".fixtureSha256");
        }
    }

    private static void validateResults(JsonNode node) throws ConformanceReportException {
        if (node == null || !node.isArray() || node.size() != CASE_PINS.size()) {
            throw invalid("results", "must contain all 14 pinned case results");
        }
        Set<String> seen = new HashSet<>();
        for (int index = 0; index < node.size(); index++) {
            String path = "results[" + index + "]";
            JsonNode result = object(node.get(index), path);
            exactFields(result, Set.of("id", "contract", "category", "status", "expectedSemantics",
                    "observedSemantics", "inputSha256", "diagnostic", "sideEffectExecuted"), path);
            String id = text(result.get("id"), path + ".id");
            CasePin expected = CASE_PINS.get(id);
            if (expected == null || !seen.add(id)) throw invalid(path + ".id", "must identify one unique pinned case");
            equalText(result.get("contract"), expected.contract(), path + ".contract");
            equalText(result.get("category"), expected.category(), path + ".category");
            equalText(result.get("status"), "PASS", path + ".status");
            equalText(result.get("expectedSemantics"), expected.semantics(), path + ".expectedSemantics");
            equalText(result.get("observedSemantics"), expected.semantics(), path + ".observedSemantics");
            equalText(result.get("inputSha256"), expected.inputSha256(), path + ".inputSha256");
            text(result.get("diagnostic"), path + ".diagnostic");
            equalBoolean(result.get("sideEffectExecuted"), false, path + ".sideEffectExecuted");
        }
    }

    private static JsonNode object(JsonNode node, String path) throws ConformanceReportException {
        if (node == null || !node.isObject()) throw invalid(path, "must be an object");
        return node;
    }

    private static void exactFields(JsonNode node, Set<String> expected, String path) throws ConformanceReportException {
        Set<String> actual = new HashSet<>();
        Iterator<String> fields = node.fieldNames();
        fields.forEachRemaining(actual::add);
        if (!actual.equals(expected)) throw invalid(path, "has an unexpected or missing field");
    }

    private static String text(JsonNode node, String path) throws ConformanceReportException {
        if (node == null || !node.isTextual() || node.textValue().isBlank()) {
            throw invalid(path, "must be a non-blank string");
        }
        return node.textValue();
    }

    private static void equalText(JsonNode node, String expected, String path) throws ConformanceReportException {
        if (!text(node, path).equals(expected)) throw invalid(path, "does not match the v0.1 pin");
    }

    private static void equalInt(JsonNode node, int expected, String path) throws ConformanceReportException {
        if (node == null || !node.isIntegralNumber() || !node.canConvertToInt() || node.intValue() != expected) {
            throw invalid(path, "must equal " + expected);
        }
    }

    private static void equalBoolean(JsonNode node, boolean expected, String path) throws ConformanceReportException {
        if (node == null || !node.isBoolean() || node.booleanValue() != expected) {
            throw invalid(path, "must equal " + expected);
        }
    }

    private static ConformanceReportException invalid(String path, String message) {
        return new ConformanceReportException(path + ": " + message);
    }
}
