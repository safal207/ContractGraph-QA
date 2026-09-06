# ContractGraph-QA interoperability: five-minute guide

English · [简体中文](../zh-CN/GETTING_STARTED.md) · [हिन्दी](../hi/GETTING_STARTED.md) · [Español](../es/GETTING_STARTED.md) · [العربية](../ar/GETTING_STARTED.md)

ContractGraph-QA, LiminalQA, and PythiaLabs form an evidence-first safety
stack for stateful and high-risk agent workflows. Each project keeps its own
verdict authority; the adapters exchange strict JSON evidence without turning
a report into permission to act.

## What each project contributes

| Project | Role | Does not claim |
|---|---|---|
| ContractGraph-QA | Bounded state/action search, exact-subject evidence, replay inputs | Exhaustive correctness or action authority |
| LiminalQA | Bi-temporal QA context and non-authoritative replay/debt candidates | A verified CGQA finding or LTP continuity verdict |
| PythiaLabs | Fresh deterministic authorization gate using external evidence as advisory context | That external evidence alone can return `ALLOW` |

## Run the pinned contract

From a ContractGraph-QA checkout:

```bash
python -m pip install .
cgqa liminalqa-conformance > report.json
```

A passing report contains all 14 golden and fail-closed vectors and always
records:

```json
{"status":"PASS","counts":{"total":14,"passed":14,"failed":0},"authority":{"classification":"conformance_evidence_only","mayAuthorizeAction":false}}
```

The full object also pins the suite SHA-256, both producer contracts, every
case ID and input digest, `sideEffectExecuted=false`, and the claim boundary.

## Validate in your application language

The repository ships thin report adapters. They validate the native runner's
evidence; they intentionally do not reimplement CGQA/LiminalQA verdict logic.

```bash
# TypeScript / JavaScript (Node 18+)
node sdks/typescript/bin/cgqa-report-validate.js report.json

# Go 1.22+
cd sdks/go
go run ./cmd/cgqa-report-validate ../../report.json

# Java 17+
mvn -q -f sdks/java/pom.xml exec:java \
  -Dexec.args=report.json

# .NET 8+
dotnet run --project sdks/dotnet/src/ContractGraphQA.Interop.Cli -- report.json
```

Package-manager coordinates and local-reference examples are in the
[SDK release guide](../../SDK_RELEASE.md). Python is the ContractGraph-QA
reference runner; Rust is the LiminalQA native runner; Elixir is the
PythiaLabs native runner.

[SDK v0.1.0 is publicly downloadable from GitHub](https://github.com/safal207/ContractGraph-QA/releases/tag/interop-sdk-v0.1.0),
and the Go module is available with
`go get github.com/safal207/ContractGraph-QA/sdks/go@v0.1.0`. The `.tgz`,
JAR/POM, and `.nupkg` are release assets; npm, Maven Central, and nuget.org
listings are not published yet.

## What fails closed

Every consumer rejects:

- duplicate JSON keys and malformed input;
- unknown fields at security-critical boundaries;
- a changed suite, schema, fixture, producer, case, or mutation digest;
- missing, duplicated, failed, or `UNSAFE_ACCEPTED` cases;
- `mayAuthorizeAction=true` or any reported side effect;
- a missing or changed non-claim boundary.

Input is limited to 1 MiB and validation performs no network request,
candidate execution, database write, or target-system action.

## Use the evidence correctly

A valid report means only that one implementation behaved correctly for the
pinned synthetic vectors. Before a real action, preserve the exact subject and
causal identity, replay against current evidence, and run the active Pythia or
operator authorization gate. `PASS` is never permission.

For the complete protocol, see [ContractGraph-QA ↔ LiminalQA interop](../../LIMINALQA_INTEROP.md).
