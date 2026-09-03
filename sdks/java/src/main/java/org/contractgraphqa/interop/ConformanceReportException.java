package org.contractgraphqa.interop;

/** Raised when a conformance report is ambiguous, incomplete, or drifts from v0.1. */
public final class ConformanceReportException extends Exception {
    public ConformanceReportException(String message) {
        super(message);
    }

    public ConformanceReportException(String message, Throwable cause) {
        super(message, cause);
    }
}
