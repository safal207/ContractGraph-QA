# ContractGraph-QA interop report adapter for .NET

The .NET 8 library validates the exact `cgqa-liminalqa-v0.1` passing report
with no runtime dependency outside `System.Text.Json`. Duplicate keys,
unknown fields, pin drift, missing cases, side-effect claims, and authority
escalation fail closed.

The following command will work after nuget.org publication:

```bash
dotnet add package ContractGraphQA.Interop --version 0.1.0
```

```csharp
var summary = InteropReportValidator.Validate(reportBytes);
Console.WriteLine(summary.Passed);             // 14
Console.WriteLine(summary.MayAuthorizeAction); // False
```

For v0.1.0, use the public `.nupkg` as a local package source:

```bash
mkdir -p vendor/contractgraph
curl -fL https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/ContractGraphQA.Interop.0.1.0.nupkg \
  -o vendor/contractgraph/ContractGraphQA.Interop.0.1.0.nupkg
dotnet add <PROJECT> package ContractGraphQA.Interop \
  --version 0.1.0 --source vendor/contractgraph
```

The package is not listed on nuget.org yet. From a repository checkout,
you can alternatively reference
`sdks/dotnet/src/ContractGraphQA.Interop/ContractGraphQA.Interop.csproj`.
The companion CLI accepts a file or stdin. A valid result remains evidence
only and cannot authorize an action.
