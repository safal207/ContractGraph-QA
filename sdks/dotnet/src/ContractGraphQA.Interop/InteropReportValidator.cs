using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace ContractGraphQA.Interop;

/// <summary>Strict validator for one passing cgqa-liminalqa-v0.1 conformance report.</summary>
public static class InteropReportValidator
{
    public const int MaxReportBytes = 1_048_576;
    private const string Schema = "org.contractgraph-qa.liminalqa-interop-conformance-result.v0.1";
    private const string SuiteId = "cgqa-liminalqa-v0.1";
    private const string SuiteVersion = "0.1.0";
    private const string SuiteSha256 = "562e2f9ae699f001b9ccf1b2b9f6dd30c435d53d668b5fd9a04ca15ca1e4faac";
    private const string ClaimBoundary = "Synthetic conformance verifies adapter behavior only for these pinned fixtures and mutations. It does not verify a production system, prove security or completeness, authorize an action, or replace independent replay against the exact subject.";
    private static readonly Regex SafeId = new("^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$", RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(100));

    private sealed record ContractPin(string ArtifactSchema, string ArtifactProfile, string OwnerRepository,
        string ProducerCommit, string SchemaSha256, string FixtureSha256);

    private static readonly IReadOnlyDictionary<string, ContractPin> ContractPins =
        new Dictionary<string, ContractPin>(StringComparer.Ordinal)
        {
            ["cgqa-evidence"] = new(
                "org.contractgraph-qa.liminalqa-evidence.v0.1",
                "org.contractgraph-qa.bounded-invariant-evidence.v0.1",
                "safal207/ContractGraph-QA",
                "bdf7ced074e3a7baf57cf89ac68be9674bd76a02",
                "53b0b4a0b1f4d77de26b8be9dbb90006ea0bd30c5cd3960a2f3e7d44d9664184",
                "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce"),
            ["liminal-candidates"] = new(
                "org.liminalqa.cgqa-candidates.v0.1",
                "org.liminalqa.non-authoritative-candidate-seeds.v0.1",
                "safal207/LiminalQAengineer",
                "db9c85f678aafd6e28487e0679a9fb6c3ebfb0c3",
                "896e32921d41925a976fef5d0ba561a08bd1f2265a08bc9ccf5065a3238a4f60",
                "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3")
        };

    private sealed record CasePin(string Contract, string Category, string Semantics, string InputSha256);

    private static readonly IReadOnlyDictionary<string, CasePin> CasePins =
        new Dictionary<string, CasePin>(StringComparer.Ordinal)
        {
            ["cgqa-evidence-golden"] = new("cgqa-evidence", "golden", "VALID_NON_AUTHORIZING", "e1d5a14c5c1b75e2cfffaf87bf526fd61e141a0c5b7828de4f275e9792fda3ce"),
            ["cgqa-evidence-authority-escalation"] = new("cgqa-evidence", "authority_escalation", "INVALID_BLOCKED", "33eb3122738032c3ebc1043f5058bc7a9cc469c6ecff8ad0a602aaa3a80067ce"),
            ["cgqa-evidence-count-mismatch"] = new("cgqa-evidence", "semantic_mismatch", "INVALID_BLOCKED", "3f348306ba20fdb780b662ec3aadbdf8d1a805a1d81cb2eb66103824e9f8b95f"),
            ["cgqa-evidence-temporal-inversion"] = new("cgqa-evidence", "temporal_inversion", "INVALID_BLOCKED", "dbc7d64eda4aeb497bf360e10335896b3f9b4316973306e37a8a21134cc85ba8"),
            ["cgqa-evidence-unknown-authority-field"] = new("cgqa-evidence", "unknown_field", "INVALID_BLOCKED", "49d7eab11be2a4fc5b90776a9822156573ef5753bff25e674629fdb8e742edea"),
            ["cgqa-evidence-unsafe-causal-parent"] = new("cgqa-evidence", "unsafe_identifier", "INVALID_BLOCKED", "e50dfe383bbd2577b72dba043bbe129b6370b81ec8226d6fa9ed206bf6bf51af"),
            ["cgqa-evidence-duplicate-schema-key"] = new("cgqa-evidence", "ambiguous_json", "INVALID_BLOCKED", "6ff810788c268a93af16daa7a814cfe84616542951de92be8dbe79aabf3d41c9"),
            ["liminal-candidates-golden"] = new("liminal-candidates", "golden", "VALID_NON_AUTHORIZING", "60b794934959c30f9957d0e54de83d7760ac38b618b0676603d721daa8ef11d3"),
            ["liminal-candidates-authority-escalation"] = new("liminal-candidates", "authority_escalation", "INVALID_BLOCKED", "261570efc9e6c13d46686a6f5941ee7d39db620c4603cf30a64e0f0baae3abff"),
            ["liminal-candidates-unknown-authority-field"] = new("liminal-candidates", "unknown_field", "INVALID_BLOCKED", "1a3841322a8dae89e793f92cedcf341c5fafa4a70e308426d76f674434291941"),
            ["liminal-candidates-missing-independent-replay"] = new("liminal-candidates", "verification_weakening", "INVALID_BLOCKED", "8030649160511f62065f4ba33d703fb4dcbf96bc25480d8fa9c7d4e85d715423"),
            ["liminal-candidates-debt-mismatch"] = new("liminal-candidates", "semantic_mismatch", "INVALID_BLOCKED", "172a1567897dc4a78deaf2c9f50bc6634e59d2d671ab23d414ca8b4a089f8185"),
            ["liminal-candidates-unsafe-causal-parent"] = new("liminal-candidates", "unsafe_identifier", "INVALID_BLOCKED", "61b8e74f52248e50fc90e0765b6cc0449ea5b588cb6aa525d148dcb9ac447960"),
            ["liminal-candidates-duplicate-schema-key"] = new("liminal-candidates", "ambiguous_json", "INVALID_BLOCKED", "9bf53f54b15a2eb09731c28dfffc5ba39f7c04b0d5fa4d076f300f8107ae2d40")
        };

    public sealed record Implementation(string Name, string Version, string Language);

    /// <summary>A passing summary remains evidence-only and never authorizes an action.</summary>
    public sealed record Summary(bool Valid, string SuiteId, Implementation Implementation, int Passed,
        bool MayAuthorizeAction, string ClaimBoundary);

    public static Summary Validate(string raw) => Validate(Encoding.UTF8.GetBytes(raw));

    public static Summary Validate(byte[] raw)
    {
        if (raw.Length > MaxReportBytes) throw Invalid("json", $"must not exceed {MaxReportBytes} bytes");
        try
        {
            using JsonDocument document = JsonDocument.Parse(raw, new JsonDocumentOptions
            {
                AllowTrailingCommas = false,
                CommentHandling = JsonCommentHandling.Disallow,
                MaxDepth = 64
            });
            RejectDuplicateKeys(document.RootElement, "report");
            return ValidateRoot(document.RootElement);
        }
        catch (ConformanceReportException)
        {
            throw;
        }
        catch (JsonException exception)
        {
            throw new ConformanceReportException("json: invalid JSON", exception);
        }
    }

    private static Summary ValidateRoot(JsonElement report)
    {
        RequireObject(report, "report");
        ExactProperties(report, ["schema", "reportId", "suiteId", "suiteVersion", "suiteSha256", "implementation",
            "status", "counts", "contractPins", "results", "authority", "claimBoundary"], "report");
        EqualText(report, "schema", Schema, "schema");
        string reportId = Text(report, "reportId", "reportId");
        if (!SafeId.IsMatch(reportId)) throw Invalid("reportId", "must be a safe identifier");
        EqualText(report, "suiteId", SuiteId, "suiteId");
        EqualText(report, "suiteVersion", SuiteVersion, "suiteVersion");
        EqualText(report, "suiteSha256", SuiteSha256, "suiteSha256");
        EqualText(report, "status", "PASS", "status");
        EqualText(report, "claimBoundary", ClaimBoundary, "claimBoundary");

        JsonElement implementation = Property(report, "implementation", "implementation");
        RequireObject(implementation, "implementation");
        ExactProperties(implementation, ["name", "version", "language"], "implementation");
        var identity = new Implementation(
            Text(implementation, "name", "implementation.name"),
            Text(implementation, "version", "implementation.version"),
            Text(implementation, "language", "implementation.language"));

        JsonElement counts = Property(report, "counts", "counts");
        RequireObject(counts, "counts");
        ExactProperties(counts, ["total", "passed", "failed"], "counts");
        EqualInt(counts, "total", 14, "counts.total");
        EqualInt(counts, "passed", 14, "counts.passed");
        EqualInt(counts, "failed", 0, "counts.failed");

        JsonElement authority = Property(report, "authority", "authority");
        RequireObject(authority, "authority");
        ExactProperties(authority, ["classification", "mayAuthorizeAction"], "authority");
        EqualText(authority, "classification", "conformance_evidence_only", "authority.classification");
        EqualBoolean(authority, "mayAuthorizeAction", false, "authority.mayAuthorizeAction");
        ValidateContractPins(Property(report, "contractPins", "contractPins"));
        ValidateResults(Property(report, "results", "results"));
        return new Summary(true, SuiteId, identity, 14, false, ClaimBoundary);
    }

    private static void ValidateContractPins(JsonElement pins)
    {
        if (pins.ValueKind != JsonValueKind.Array || pins.GetArrayLength() != ContractPins.Count)
            throw Invalid("contractPins", "must contain both pinned contracts");
        var seen = new HashSet<string>(StringComparer.Ordinal);
        int index = 0;
        foreach (JsonElement pin in pins.EnumerateArray())
        {
            string path = $"contractPins[{index++}]";
            RequireObject(pin, path);
            ExactProperties(pin, ["id", "artifactSchema", "artifactProfile", "ownerRepository", "producerCommit", "schemaSha256", "fixtureSha256"], path);
            string id = Text(pin, "id", path + ".id");
            if (!ContractPins.TryGetValue(id, out ContractPin? expected) || !seen.Add(id))
                throw Invalid(path + ".id", "must identify one unique pinned contract");
            ContractPin pinned = expected!;
            EqualText(pin, "artifactSchema", pinned.ArtifactSchema, path + ".artifactSchema");
            EqualText(pin, "artifactProfile", pinned.ArtifactProfile, path + ".artifactProfile");
            EqualText(pin, "ownerRepository", pinned.OwnerRepository, path + ".ownerRepository");
            EqualText(pin, "producerCommit", pinned.ProducerCommit, path + ".producerCommit");
            EqualText(pin, "schemaSha256", pinned.SchemaSha256, path + ".schemaSha256");
            EqualText(pin, "fixtureSha256", pinned.FixtureSha256, path + ".fixtureSha256");
        }
    }

    private static void ValidateResults(JsonElement results)
    {
        if (results.ValueKind != JsonValueKind.Array || results.GetArrayLength() != CasePins.Count)
            throw Invalid("results", "must contain all 14 pinned case results");
        var seen = new HashSet<string>(StringComparer.Ordinal);
        int index = 0;
        foreach (JsonElement result in results.EnumerateArray())
        {
            string path = $"results[{index++}]";
            RequireObject(result, path);
            ExactProperties(result, ["id", "contract", "category", "status", "expectedSemantics", "observedSemantics", "inputSha256", "diagnostic", "sideEffectExecuted"], path);
            string id = Text(result, "id", path + ".id");
            if (!CasePins.TryGetValue(id, out CasePin? expected) || !seen.Add(id))
                throw Invalid(path + ".id", "must identify one unique pinned case");
            CasePin pinned = expected!;
            EqualText(result, "contract", pinned.Contract, path + ".contract");
            EqualText(result, "category", pinned.Category, path + ".category");
            EqualText(result, "status", "PASS", path + ".status");
            EqualText(result, "expectedSemantics", pinned.Semantics, path + ".expectedSemantics");
            EqualText(result, "observedSemantics", pinned.Semantics, path + ".observedSemantics");
            EqualText(result, "inputSha256", pinned.InputSha256, path + ".inputSha256");
            _ = Text(result, "diagnostic", path + ".diagnostic");
            EqualBoolean(result, "sideEffectExecuted", false, path + ".sideEffectExecuted");
        }
    }

    private static void RejectDuplicateKeys(JsonElement value, string path)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in value.EnumerateObject())
            {
                if (!keys.Add(property.Name)) throw Invalid(path, $"duplicate object key {JsonSerializer.Serialize(property.Name)}");
                RejectDuplicateKeys(property.Value, path + "." + property.Name);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
        {
            int index = 0;
            foreach (JsonElement item in value.EnumerateArray()) RejectDuplicateKeys(item, $"{path}[{index++}]");
        }
    }

    private static void ExactProperties(JsonElement value, string[] expected, string path)
    {
        var actual = value.EnumerateObject().Select(property => property.Name).ToHashSet(StringComparer.Ordinal);
        if (!actual.SetEquals(expected)) throw Invalid(path, "has an unexpected or missing field");
    }

    private static JsonElement Property(JsonElement value, string name, string path)
    {
        if (!value.TryGetProperty(name, out JsonElement result)) throw Invalid(path, "is required");
        return result;
    }

    private static string Text(JsonElement value, string name, string path)
    {
        JsonElement property = Property(value, name, path);
        if (property.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(property.GetString()))
            throw Invalid(path, "must be a non-blank string");
        return property.GetString()!;
    }

    private static void EqualText(JsonElement value, string name, string expected, string path)
    {
        if (!string.Equals(Text(value, name, path), expected, StringComparison.Ordinal))
            throw Invalid(path, "does not match the v0.1 pin");
    }

    private static void EqualInt(JsonElement value, string name, int expected, string path)
    {
        JsonElement property = Property(value, name, path);
        if (property.ValueKind != JsonValueKind.Number || !property.TryGetInt32(out int actual) || actual != expected)
            throw Invalid(path, $"must equal {expected}");
    }

    private static void EqualBoolean(JsonElement value, string name, bool expected, string path)
    {
        JsonElement property = Property(value, name, path);
        if (property.ValueKind is not (JsonValueKind.True or JsonValueKind.False) || property.GetBoolean() != expected)
            throw Invalid(path, $"must equal {expected.ToString().ToLowerInvariant()}");
    }

    private static void RequireObject(JsonElement value, string path)
    {
        if (value.ValueKind != JsonValueKind.Object) throw Invalid(path, "must be an object");
    }

    private static ConformanceReportException Invalid(string path, string message) => new($"{path}: {message}");
}
