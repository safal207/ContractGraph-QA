# Interoperability SDK release guide

The SDKs are thin consumers of the pinned `cgqa-liminalqa-v0.1` conformance
report. They make the ContractGraph-QA, LiminalQA, and PythiaLabs evidence
boundary convenient in common application ecosystems without creating new
verdict owners.

## Ecosystem matrix

| Ecosystem | Source | Package coordinate | Minimum runtime | Current state |
|---|---|---|---|---|
| Python | `contractgraph_qa` | `contractgraph-qa` | Python 3.11 | Published native reference runner |
| Rust | LiminalQA `limctl` | repository crate/workspace | Rust stable | Native conformance runner in draft PR |
| Elixir | PythiaLabs Mix task | repository Mix project | Project-supported Elixir/OTP | Native conformance runner in draft PR |
| TypeScript / JavaScript | [`sdks/typescript`](../sdks/typescript/) | `@contractgraph-qa/interop-report` | Node 18 | Registry-ready, not yet published |
| Go | [`sdks/go`](../sdks/go/) | `github.com/safal207/ContractGraph-QA/sdks/go` | Go 1.22 | Module-ready, not yet tagged |
| Java / JVM | [`sdks/java`](../sdks/java/) | `io.github.safal207:contractgraph-interop` | Java 17 | Artifact-ready; Central publisher profile not configured |
| C# / .NET | [`sdks/dotnet`](../sdks/dotnet/) | `ContractGraphQA.Interop` | .NET 8 | NuGet-ready, not yet published |

“Registry-ready” means source, public API, CLI where applicable, metadata,
negative tests, packaging checks, documentation, and CI exist. It does not
mean an external registry accepted a package. Publishing requires a separate
credentialed release action and is intentionally excluded from pull-request CI.

## Local verification

```bash
python -m unittest tools.tests.test_sdk_portability

cd sdks/typescript
npm test
npm pack --dry-run

cd ../go
go test ./...

cd ../java
mvn --batch-mode --no-transfer-progress verify

cd ../dotnet
dotnet test test/ContractGraphQA.Interop.Tests/ContractGraphQA.Interop.Tests.csproj \
  --configuration Release
dotnet pack src/ContractGraphQA.Interop/ContractGraphQA.Interop.csproj \
  --configuration Release --no-restore
```

The `SDK Portability` GitHub workflow runs these checks on pull requests.
It has read-only repository permissions and never publishes a package.

## Release commands after explicit authorization

These commands are documentation, not actions performed by pull-request CI:

```bash
# npm
cd sdks/typescript
npm publish --access public

# Go (submodule tag created at the repository root)
git tag sdks/go/v0.1.0 <verified-merge-commit>
git push origin sdks/go/v0.1.0

# Maven artifact; configure signing and a Central publisher before upload
mvn -f sdks/java/pom.xml verify

# NuGet
dotnet nuget push sdks/dotnet/src/ContractGraphQA.Interop/bin/Release/*.nupkg \
  --source https://api.nuget.org/v3/index.json --api-key "$NUGET_API_KEY"
```

Before any release, bind the decision to one exact commit, confirm the full
CI conclusion on that commit, inspect the produced archive, and publish from a
protected environment. Never expose registry credentials to untrusted PR code.

## Versioning rule

SDK `0.1.x` supports only suite `cgqa-liminalqa-v0.1` and rejects any other
suite version or digest. A changed canonical suite requires a new explicit
consumer profile and migration notes; an SDK must not silently accept it.

A passing SDK result remains `conformance_evidence_only` with
`mayAuthorizeAction=false`. No package in this matrix is an action gate.
