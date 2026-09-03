# ContractGraph-QA, LiminalQA, and PythiaLabs interoperability SDKs

These packages make the pinned evidence contract convenient from common
application languages. They validate a native conformance report; they do not
reimplement verdict logic, execute candidates, contact a target, or authorize
an action.

| Language | Directory | Package/API |
|---|---|---|
| TypeScript / JavaScript | [`typescript/`](typescript/) | `@contractgraph-qa/interop-report` |
| Go | [`go/`](go/) | `interop.ValidateJSON` |
| Java / JVM | [`java/`](java/) | `InteropReportValidator.validate` |
| C# / .NET | [`dotnet/`](dotnet/) | `InteropReportValidator.Validate` |

Python, Rust, and Elixir native runners are documented in the
[SDK release matrix](../docs/SDK_RELEASE.md).

[Download the public interoperability SDK v0.1.0 bundle](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0),
including checksums and an offline attestation. Go users can install the tagged
module directly:

```bash
go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0
```

The TypeScript/JavaScript `.tgz`, JVM JAR/POM, and .NET `.nupkg` are public
release assets; npm, Maven Central, and nuget.org publication is still pending.

Start in
[English](../docs/i18n/en/GETTING_STARTED.md),
[简体中文](../docs/i18n/zh-CN/GETTING_STARTED.md),
[हिन्दी](../docs/i18n/hi/GETTING_STARTED.md),
[Español](../docs/i18n/es/GETTING_STARTED.md), or
[العربية](../docs/i18n/ar/GETTING_STARTED.md).

All four implementations pin the same suite SHA-256 and 14 input digests,
reject duplicate JSON keys and unknown fields, cap input at 1 MiB, and return
`mayAuthorizeAction=false` even after successful validation.
