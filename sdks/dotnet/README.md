# ContractGraph-QA interop report adapter for .NET

The .NET 8 library validates the exact `cgqa-liminalqa-v0.1` passing report
with no runtime dependency outside `System.Text.Json`. Duplicate keys,
unknown fields, pin drift, missing cases, side-effect claims, and authority
escalation fail closed.

After NuGet publication:

```bash
dotnet add package ContractGraphQA.Interop --version 0.1.0
```

```csharp
var summary = InteropReportValidator.Validate(reportBytes);
Console.WriteLine(summary.Passed);             // 14
Console.WriteLine(summary.MayAuthorizeAction); // False
```

Until publication, reference
`sdks/dotnet/src/ContractGraphQA.Interop/ContractGraphQA.Interop.csproj`.
The companion CLI accepts a file or stdin. A valid result remains evidence
only and cannot authorize an action.
