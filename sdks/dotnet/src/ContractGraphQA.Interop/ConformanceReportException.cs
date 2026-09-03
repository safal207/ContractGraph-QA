namespace ContractGraphQA.Interop;

/// <summary>Raised when a conformance report is ambiguous, incomplete, or drifts from v0.1.</summary>
public sealed class ConformanceReportException : Exception
{
    public ConformanceReportException(string message) : base(message) { }

    public ConformanceReportException(string message, Exception innerException)
        : base(message, innerException) { }
}
