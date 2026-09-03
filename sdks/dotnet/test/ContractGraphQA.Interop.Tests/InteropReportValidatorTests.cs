using System.Text;
using System.Text.Json.Nodes;
using ContractGraphQA.Interop;
using Xunit;

namespace ContractGraphQA.Interop.Tests;

public sealed class InteropReportValidatorTests
{
    private static byte[] Fixture() => File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "pass-report.json"));

    [Fact]
    public void AcceptsCompletePinnedReport()
    {
        var summary = InteropReportValidator.Validate(Fixture());
        Assert.True(summary.Valid);
        Assert.Equal(14, summary.Passed);
        Assert.False(summary.MayAuthorizeAction);
    }

    public static IEnumerable<object[]> SafetyDrift()
    {
        yield return [new Action<JsonObject>(report => report["authority"]!["mayAuthorizeAction"] = true)];
        yield return [new Action<JsonObject>(report => report["suiteSha256"] = "drift")];
        yield return [new Action<JsonObject>(report => report["counts"]!["passed"] = 13)];
        yield return [new Action<JsonObject>(report => report["results"]![0]!["sideEffectExecuted"] = true)];
        yield return [new Action<JsonObject>(report => report["results"]![1]!["observedSemantics"] = "UNSAFE_ACCEPTED")];
        yield return [new Action<JsonObject>(report => report["results"]!.AsArray().RemoveAt(13))];
        yield return [new Action<JsonObject>(report => report["authorization"] = "ALLOW")];
    }

    [Theory]
    [MemberData(nameof(SafetyDrift))]
    public void RejectsSafetyDrift(Action<JsonObject> mutate)
    {
        JsonObject report = JsonNode.Parse(Encoding.UTF8.GetString(Fixture()))!.AsObject();
        mutate(report);
        Assert.Throws<ConformanceReportException>(() => InteropReportValidator.Validate(report.ToJsonString()));
    }

    [Fact]
    public void RejectsDuplicateKeys()
    {
        string raw = Encoding.UTF8.GetString(Fixture()).TrimStart();
        string ambiguous = "{\"schema\":\"duplicate\"," + raw[1..];
        Assert.Throws<ConformanceReportException>(() => InteropReportValidator.Validate(ambiguous));
    }
}
