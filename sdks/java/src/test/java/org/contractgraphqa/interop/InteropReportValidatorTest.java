package org.contractgraphqa.interop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

final class InteropReportValidatorTest {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private byte[] fixture() throws IOException {
        try (InputStream stream = getClass().getResourceAsStream("/pass-report.json")) {
            if (stream == null) throw new IOException("missing pass-report.json");
            return stream.readAllBytes();
        }
    }

    @Test
    void acceptsCompletePinnedReport() throws Exception {
        var summary = InteropReportValidator.validate(fixture());
        assertTrue(summary.valid());
        assertEquals(14, summary.passed());
        assertFalse(summary.mayAuthorizeAction());
    }

    @Test
    void rejectsAuthorityEscalation() throws Exception {
        ObjectNode report = (ObjectNode) MAPPER.readTree(fixture());
        ((ObjectNode) report.get("authority")).put("mayAuthorizeAction", true);
        assertRejected(report);
    }

    @Test
    void rejectsSuiteDrift() throws Exception {
        ObjectNode report = (ObjectNode) MAPPER.readTree(fixture());
        report.put("suiteSha256", "drift");
        assertRejected(report);
    }

    @Test
    void rejectsSideEffectClaimAndUnsafeAcceptance() throws Exception {
        ObjectNode report = (ObjectNode) MAPPER.readTree(fixture());
        ((ObjectNode) report.withArray("results").get(0)).put("sideEffectExecuted", true);
        assertRejected(report);
        report = (ObjectNode) MAPPER.readTree(fixture());
        ((ObjectNode) report.withArray("results").get(1)).put("observedSemantics", "UNSAFE_ACCEPTED");
        assertRejected(report);
    }

    @Test
    void rejectsMissingCaseAndUnknownField() throws Exception {
        ObjectNode report = (ObjectNode) MAPPER.readTree(fixture());
        report.withArray("results").remove(13);
        assertRejected(report);
        report = (ObjectNode) MAPPER.readTree(fixture());
        report.put("authorization", "ALLOW");
        assertRejected(report);
    }

    @Test
    void rejectsDuplicateKeys() throws Exception {
        String raw = new String(fixture(), StandardCharsets.UTF_8);
        byte[] ambiguous = ("{\"schema\":\"duplicate\"," + raw.stripLeading().substring(1))
                .getBytes(StandardCharsets.UTF_8);
        assertThrows(ConformanceReportException.class, () -> InteropReportValidator.validate(ambiguous));
    }

    private void assertRejected(JsonNode report) throws Exception {
        byte[] raw = MAPPER.writeValueAsBytes(report);
        assertThrows(ConformanceReportException.class, () -> InteropReportValidator.validate(raw));
    }
}
