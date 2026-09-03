# ContractGraph-QA interop report adapter for TypeScript and JavaScript

This dependency-free package validates a completed `cgqa-liminalqa-v0.1`
conformance report. It pins all 14 cases, both producer contracts, the suite
digest, and the non-authority boundary. Ambiguous JSON, unknown fields, suite
drift, missing cases, side-effect claims, and `UNSAFE_ACCEPTED` are rejected.

Install the public v0.1.0 GitHub package:

```bash
npm install --save-dev https://github.com/safal207/ContractGraph-QA/releases/download/interop-sdk-v0.1.0/contractgraph-qa-interop-report-0.1.0.tgz
cgqa liminalqa-conformance | npx cgqa-report-validate
```

Library use:

```ts
import {readFile} from "node:fs/promises";
import {validateConformanceReportJson} from "@contractgraph-qa/interop-report";

const summary = validateConformanceReportJson(await readFile("report.json", "utf8"));
console.log(summary.passed); // 14
console.log(summary.mayAuthorizeAction); // false
```

The package is not listed in the npm registry yet. From a repository checkout,
you can alternatively run `npm install ./sdks/typescript`.

A valid summary is conformance evidence only. It never grants permission to
run a candidate or perform an external action.
