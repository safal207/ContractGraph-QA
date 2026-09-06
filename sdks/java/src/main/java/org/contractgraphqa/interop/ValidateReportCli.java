package org.contractgraphqa.interop;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;

/** Minimal stdin/file CLI for local CI integration. */
public final class ValidateReportCli {
    private ValidateReportCli() {}

    public static void main(String[] args) {
        try {
            byte[] raw = read(args);
            var summary = InteropReportValidator.validate(raw);
            System.out.println(new ObjectMapper().writeValueAsString(summary));
        } catch (Exception exception) {
            System.err.println("cgqa-report-validate: " + exception.getMessage());
            System.exit(2);
        }
    }

    private static byte[] read(String[] args) throws IOException {
        if (args.length > 1) throw new IOException("usage: cgqa-report-validate [report.json]");
        if (args.length == 0) return bounded(System.in);
        Path path = Path.of(args[0]);
        if (Files.isSymbolicLink(path) || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("input must be a non-symlink regular file");
        }
        if (Files.size(path) > InteropReportValidator.MAX_REPORT_BYTES) throw new IOException("input is too large");
        try (InputStream stream = Files.newInputStream(path)) {
            return bounded(stream);
        }
    }

    private static byte[] bounded(InputStream stream) throws IOException {
        byte[] raw = stream.readNBytes(InteropReportValidator.MAX_REPORT_BYTES + 1);
        if (raw.length > InteropReportValidator.MAX_REPORT_BYTES) throw new IOException("input is too large");
        return raw;
    }
}
