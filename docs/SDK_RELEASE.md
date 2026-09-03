# Interoperability SDK release guide

The SDKs are thin consumers of the pinned `cgqa-liminalqa-v0.1` conformance
report. They make the ContractGraph-QA, LiminalQA, and PythiaLabs evidence
boundary convenient in common application ecosystems without creating new
verdict owners.

## Ecosystem matrix

| Ecosystem | Source | Package coordinate | Minimum runtime | Current state |
|---|---|---|---|---|
| Python | `contractgraph_qa` | `contractgraph-qa` | Python 3.11 | Published native reference runner |
| Rust | LiminalQA `limctl` | repository crate/workspace | Rust stable | Native conformance runner merged in LiminalQA |
| Elixir | PythiaLabs Mix task | repository Mix project | Project-supported Elixir/OTP | Native conformance runner merged in PythiaLabs |
| TypeScript / JavaScript | [`sdks/typescript`](../sdks/typescript/) | `@contractgraph-qa/interop-report` | Node 18 | Public v0.1.0 GitHub package; npm registry pending |
| Go | [`sdks/go`](../sdks/go/) | `github.com/safal207/ContractGraph-QA/sdks/go` | Go 1.22 | Public Go module and GitHub archive at v0.1.0 |
| Java / JVM | [`sdks/java`](../sdks/java/) | `io.github.safal207:contractgraph-interop` | Java 17 | Public v0.1.0 JAR/POM bundle; Maven Central pending |
| C# / .NET | [`sdks/dotnet`](../sdks/dotnet/) | `ContractGraphQA.Interop` | .NET 8 | Public v0.1.0 NuGet package file; nuget.org pending |

“Registry-ready” means source, public API, CLI where applicable, metadata,
negative tests, packaging checks, documentation, and CI exist. It does not
mean an external registry accepted a package. Publishing requires a separate
credentialed release action and is intentionally excluded from pull-request CI.

## Public v0.1.0 release

The immutable SDK source is commit
[`de7c765243dc86226b8554757ef1f9419c194a4c`](https://github.com/safal207/ContractGraph-QA/commit/de7c765243dc86226b8554757ef1f9419c194a4c).
The release workflow built that subject, attached checksums and an offline
attestation, created annotated tags `interop-sdk-v0.1.0` and
`sdks/go/v0.1.0`, and then downloaded the public assets again before
completing.

[Download interoperability SDK v0.1.0](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0)

The Go module is available through the public module proxy:

```bash
go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0
```

TypeScript/JavaScript, JVM, and .NET consumers can download the `.tgz`, JAR
and POM, or `.nupkg` from the release page. Download `SHA256SUMS` alongside
the selected artifact and verify its SHA-256 before use. The release page is
the public distribution channel for those three ecosystems until their
official registries are configured.

Examples for installing directly from the public bundle:

```bash
# TypeScript / JavaScript
npm install https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-qa-interop-report-0.1.0.tgz

# JVM: download the JAR and POM, then install the coordinate locally
curl -fLO https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-interop-0.1.0.jar
curl -fLO https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-interop-0.1.0.pom
mvn install:install-file \
  -Dfile=contractgraph-interop-0.1.0.jar \
  -DpomFile=contractgraph-interop-0.1.0.pom

# .NET: download to a local package source, then replace <PROJECT>
mkdir -p vendor/contractgraph
curl -fL https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/ContractGraphQA.Interop.0.1.0.nupkg \
  -o vendor/contractgraph/ContractGraphQA.Interop.0.1.0.nupkg
dotnet add <PROJECT> package ContractGraphQA.Interop \
  --version 0.1.0 --source vendor/contractgraph

# Verify every release artifact present in the current directory
curl -fLO https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
```

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

## Remaining official registry transitions

The GitHub release and Go module are published. The following coordinates are
reserved in the package metadata but are **not** published to their official
registries yet:

- npm: `@contractgraph-qa/interop-report@0.1.0` requires ownership of the
  `@contractgraph-qa` scope and a trusted publisher or publish token.
- Maven Central: `io.github.safal207:contractgraph-interop:0.1.0` requires a
  verified Central namespace, publisher token, signing, and Central-complete
  release artifacts.
- NuGet: `ContractGraphQA.Interop@0.1.0` requires the package owner and a
  scoped nuget.org API key or trusted publishing configuration.

Before any registry release, bind the decision to the same exact SDK source,
confirm the full CI conclusion, inspect the produced archive, and publish from
a protected environment. Never expose registry credentials to untrusted PR
code, and never infer registry publication from the GitHub bundle alone.

## Versioning rule

SDK `0.1.x` supports only suite `cgqa-liminalqa-v0.1` and rejects any other
suite version or digest. A changed canonical suite requires a new explicit
consumer profile and migration notes; an SDK must not silently accept it.

A passing SDK result remains `conformance_evidence_only` with
`mayAuthorizeAction=false`. No package in this matrix is an action gate.
